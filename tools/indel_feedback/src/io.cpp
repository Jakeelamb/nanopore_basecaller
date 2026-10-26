#include "indel_feedback/core.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <set>

namespace indel_feedback {
namespace {
void exact(const Json &value, std::initializer_list<const char *> fields) {
  require(value.is_object() && value.size() == fields.size(),
          "unknown/missing request fields");
  for (const auto *field : fields) {
    require(value.contains(field), std::string("missing field ") + field);
  }
}
std::map<std::string, std::string> metadata(const fs::path &path) {
  require(fs::file_size(path) <= 8U * 1024U * 1024U, "metadata size bound");
  std::ifstream input(path);
  std::map<std::string, std::string> result;
  std::string line;
  while (std::getline(input, line)) {
    const auto row = split(line);
    require(row.size() == 2 && !row[0].empty() &&
                line.find('\r') == std::string::npos &&
                result.emplace(row[0], row[1]).second,
            "DGM metadata malformed");
  }
  require(input.eof() && result.at("format") == "DGM1",
          "DGM metadata format/read");
  return result;
}
double finite(const std::string &text) {
  std::size_t used{};
  const auto value = std::stod(text, &used);
  require(used == text.size() && std::isfinite(value),
          "nonfinite/invalid score");
  return value;
}
double half(std::uint16_t bits) {
  const auto sign = (bits & 0x8000U) == 0 ? 1.0 : -1.0;
  const auto exponent = static_cast<int>((bits >> 10U) & 31U);
  const auto fraction = static_cast<double>(bits & 1023U);
  require(exponent != 31, "nonfinite DGS half");
  return exponent == 0
             ? sign * std::ldexp(fraction, -24)
             : sign * std::ldexp(1.0 + fraction / 1024.0, exponent - 15);
}
Frame frame(const Json &request, const Json &binding) {
  check_pin(binding.at("input_tensor"));
  check_pin(request.at("tensor_metadata"));
  const auto meta =
      metadata(request.at("tensor_metadata").at("path").get<std::string>());
  require(meta.at("read_id") == binding.at("read_id") &&
              natural(meta.at("chunk_index")) ==
                  binding.at("chunk_index").get<std::size_t>(),
          "foreign metadata parent/chunk");
  const fs::path tensor_path(
      binding.at("input_tensor").at("path").get<std::string>());
  require(tensor_path.filename() == meta.at("score_file"),
          "DGM tensor filename differs");
  std::ifstream tensor(tensor_path, std::ios::binary);
  std::string line;
  require(static_cast<bool>(std::getline(tensor, line)), "DGS header absent");
  const auto header = split(line);
  require(header.size() == 15 && header[0] == "DGS1" && header[2] == "1024" &&
              header[3] == "4" && header[4] == "6",
          "DGS geometry differs");
  require(
      header[13] == meta.at("token") && header[12] == meta.at("time_offset") &&
          header[1] == meta.at("T") && header[2] == meta.at("C") &&
          tensor_path.filename() == header[13] + "_s" + header[14] + ".scores",
      "DGS/DGM producer geometry differs");
  const auto total = natural(header[1]);
  require(total >= 1 && total <= 1000000 &&
              fs::file_size(tensor_path) ==
                  line.size() + 1 + total * 1024U * 2U,
          "DGS payload size differs");
  const auto &availability = binding.at("availability");
  exact(availability, {"kind", "row_begin", "row_end", "available_row_end",
                       "chunk_lookahead", "signal_geometry"});
  require(availability.at("kind") == "released-score-block" &&
              availability.at("chunk_lookahead") == "whole_chunk" &&
              availability.at("signal_geometry").is_null(),
          "replay availability differs");
  const auto begin = availability.at("row_begin").get<std::size_t>(),
             end = availability.at("row_end").get<std::size_t>();
  require(begin < end &&
              end <= availability.at("available_row_end").get<std::size_t>() &&
              availability.at("available_row_end").get<std::size_t>() <=
                  total &&
              end - begin <= 256,
          "unavailable/out-of-bounds rows");
  const auto initial = request.at("initial_context").get<std::string>();
  dna(initial);
  require(initial.size() == 4, "initial context length differs");
  std::size_t state{};
  for (const auto symbol : initial) {
    state = state * 4U + std::string("ACGT").find(symbol);
  }
  const auto clamp = finite(header[11]);
  require(clamp == 0 || clamp == 5, "DGS clamp differs");
  Frame result{end - begin, 4, state, finite(header[5]), {}};
  tensor.seekg(
      static_cast<std::streamoff>(line.size() + 1 + begin * 1024U * 2U));
  result.scores.reserve(result.timesteps * 1024U);
  for (std::size_t i = 0; i < result.timesteps * 1024U; ++i) {
    std::array<unsigned char, 2> bytes{};
    tensor.read(reinterpret_cast<char *>(bytes.data()), 2);
    require(tensor.gcount() == 2, "truncated DGS rows");
    const auto bits =
        static_cast<std::uint16_t>(static_cast<unsigned int>(bytes[0]) |
                                   (static_cast<unsigned int>(bytes[1]) << 8U));
    const auto value = half(bits);
    result.scores.push_back(clamp == 0 ? value
                                       : std::clamp(value, -clamp, clamp));
  }
  validate(result);
  return result;
}
Json edit_json(const Edit &edit, const std::string &native) {
  const auto reference = native.substr(edit.begin, edit.end - edit.begin);
  if (reference == edit.replacement) {
    return Json::array();
  }
  return Json::array({{{"query_begin", edit.begin},
                       {"query_end", edit.end},
                       {"reference", reference},
                       {"alternate", edit.replacement}}});
}
} // namespace
Json propose_request(const Json &request) {
  exact(request, {"schema", "batch_pin", "expected_batch_sha256",
                  "expected_binding", "tensor_metadata", "initial_context",
                  "native_query_begin", "native_query_end"});
  require(request.at("schema") == "indel-proposal-request/1",
          "proposal request schema differs");
  check_pin(request.at("batch_pin"));
  require(request.at("batch_pin").at("sha256") ==
              request.at("expected_batch_sha256"),
          "independent batch hash differs");
  const auto batch =
      read_json(request.at("batch_pin").at("path").get<std::string>());
  require(batch.at("schema") == "feedback-next/1" &&
              batch.at("kind") == "candidate-batch" &&
              batch.at("binding") == request.at("expected_binding"),
          "foreign/stale expected binding");
  const auto &binding = batch.at("binding");
  require(binding.at("orientation") == "forward" ||
              binding.at("orientation") == "reverse",
          "orientation differs");
  for (const auto &field :
       {"location_producer", "reference_free_producer", "identity_input"}) {
    check_pin(binding.at(field));
  }
  const auto native = batch.at("native").at("sequence").get<std::string>();
  const auto quality = batch.at("native").at("quality").get<std::string>();
  require(batch.at("native").at("scope") == "available_input_segment" &&
              native.size() == quality.size(),
          "available native identity differs");
  const auto identity =
      read_json(binding.at("identity_input").at("path").get<std::string>());
  require(identity.at("read_id") == binding.at("read_id") &&
              identity.at("chunk_index") == binding.at("chunk_index") &&
              identity.at("sequence") == native &&
              identity.at("quality") == quality &&
              identity.at("query_begin") == request.at("native_query_begin") &&
              identity.at("query_end") == request.at("native_query_end"),
          "identity input parent/chunk/segment differs");
  const auto scores = frame(request, binding);
  const auto meta =
      metadata(request.at("tensor_metadata").at("path").get<std::string>());
  const auto query_begin = request.at("native_query_begin").get<std::size_t>(),
             query_end = request.at("native_query_end").get<std::size_t>();
  require(query_begin >= 4 && query_begin < query_end &&
              query_end - query_begin == native.size() &&
              query_end <= meta.at("SEQ").size() &&
              meta.at("SEQ").substr(query_begin, native.size()) == native &&
              meta.at("SEQ").substr(query_begin - 4, 4) ==
                  request.at("initial_context"),
          "DGM available native segment/context differs");
  std::vector<std::size_t> emissions;
  const auto &moves = meta.at("MOVES");
  require(moves.size() == natural(meta.at("T")), "DGM MOVES/T differs");
  for (std::size_t i = 0; i < moves.size(); ++i) {
    require(moves[i] == '0' || moves[i] == '1', "DGM MOVES nonbinary");
    if (moves[i] == '1') {
      emissions.push_back(i);
    }
  }
  require(
      emissions.size() == meta.at("SEQ").size() &&
          query_end < emissions.size() &&
          emissions[query_begin] ==
              binding.at("availability").at("row_begin").get<std::size_t>() &&
          emissions[query_end] ==
              binding.at("availability").at("row_end").get<std::size_t>(),
      "native segment/released score row geometry differs");
  std::set<std::string> original_sequences;
  std::set<std::string> original_ids;
  for (const auto &candidate : batch.at("candidates")) {
    const auto sequence = candidate.at("sequence").get<std::string>();
    require(
        original_sequences.insert(sequence).second &&
            original_ids.insert(candidate.at("id").get<std::string>()).second,
        "duplicate original sequence/ID");
    const auto score = likelihood(scores, sequence);
    require(std::isfinite(score) &&
                std::abs(score -
                         candidate.at("neural_log_likelihood").get<double>()) <=
                    1e-10 * std::max(1.0, std::abs(score)),
            "original candidate likelihood differs");
  }
  require(original_sequences.contains(native) &&
              original_ids.contains(
                  batch.at("reference_free_candidate_id").get<std::string>()) &&
              original_ids.contains(
                  batch.at("union_nn_candidate_id").get<std::string>()),
          "original native/free/union role absent");
  Json output = Json::array();
  std::size_t impossible{};
  for (const auto &proposal : proposals(scores, native)) {
    if (!std::isfinite(proposal.neural_log_likelihood)) {
      ++impossible;
      continue;
    }
    if (original_sequences.contains(proposal.sequence)) {
      continue;
    }
    const auto rebuilt =
        apply_edits(native, quality, {proposal.edit}, true, false);
    require(rebuilt.first == proposal.sequence,
            "proposal edit does not reconstruct sequence");
    output.push_back({{"id", "indel-" + digest(proposal.sequence)},
                      {"sequence", proposal.sequence},
                      {"neural_log_likelihood", proposal.neural_log_likelihood},
                      {"edits", edit_json(proposal.edit, native)},
                      {"mechanism", proposal.mechanism},
                      {"eligibility_reasons", Json::array()}});
  }
  check_pin(request.at("batch_pin"));
  check_pin(binding.at("input_tensor"));
  check_pin(request.at("tensor_metadata"));
  for (const auto &field :
       {"location_producer", "reference_free_producer", "identity_input"}) {
    check_pin(binding.at(field));
  }
  return {
      {"schema", "indel-proposals/1"},
      {"target_schema", "feedback-next/1"},
      {"arm", "available-segment-indel-v1"},
      {"source_batch", request.at("batch_pin")},
      {"binding", binding},
      {"reference_free_candidate_id", batch.at("reference_free_candidate_id")},
      {"original_candidates_unchanged", batch.at("candidates")},
      {"new_candidates", output},
      {"impossible_sequences_excluded", impossible},
      {"context_cost_status", "F1 computes from its frozen location panels "
                              "before feedback-next/1 merge"},
      {"raw_current_dwell_claim", false},
      {"request", request}};
}
} // namespace indel_feedback
