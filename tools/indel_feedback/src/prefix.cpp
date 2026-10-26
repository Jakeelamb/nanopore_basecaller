#include "indel_feedback/core.h"

#include <algorithm>
#include <cstdint>
#include <set>

namespace indel_feedback {
namespace {
void exact_prefix(const Json &value,
                  std::initializer_list<const char *> fields) {
  require(value.is_object() && value.size() == fields.size(),
          "prefix field census differs");
  for (const auto *field : fields) {
    require(value.contains(field),
            std::string("missing prefix field ") + field);
  }
}
std::string text(const Json &value) {
  require(value.is_string(), "prefix string required");
  return value.get<std::string>();
}
std::size_t index(const Json &value) {
  require(value.is_number_unsigned() ||
              (value.is_number_integer() && value.get<std::int64_t>() >= 0),
          "prefix nonnegative integer required");
  return value.get<std::size_t>();
}
void hash_shape(const Json &value) {
  const auto hash = text(value);
  require(hash.size() == 64 && std::all_of(hash.begin(), hash.end(),
                                           [](char c) {
                                             return (c >= '0' && c <= '9') ||
                                                    (c >= 'a' && c <= 'f');
                                           }),
          "prefix SHA256 shape differs");
}
void stat_pin(const Json &value) {
  exact_prefix(value, {"path", "size", "sha256"});
  hash_shape(value.at("sha256"));
  const fs::path path(text(value.at("path")));
  require(path.is_absolute() && !fs::is_symlink(path) &&
              fs::is_regular_file(path) && fs::canonical(path) == path &&
              fs::file_size(path) == index(value.at("size")),
          "prefix pinned file metadata differs");
}
Json consumed_json(const Json &value) {
  stat_pin(value);
  require(index(value.at("size")) <= 8U * 1024U * 1024U,
          "prefix metadata exceeds 8MiB");
  check_pin(value);
  const auto result = read_json(text(value.at("path")));
  check_pin(value);
  return result;
}
void validate_availability(const Json &value) {
  exact_prefix(value, {"kind", "row_begin", "row_end", "available_row_end",
                       "chunk_lookahead", "signal_geometry"});
  require(text(value.at("kind")) == "released-score-block" &&
              text(value.at("chunk_lookahead")) == "whole_chunk" &&
              value.at("signal_geometry").is_null() &&
              index(value.at("row_begin")) == 0 &&
              index(value.at("row_end")) ==
                  index(value.at("available_row_end")),
          "prefix consumed availability differs");
}
void validate_binding(const Json &binding) {
  exact_prefix(binding,
               {"source_sha256", "plan_sha256", "input_tensor", "read_id",
                "parent_index", "chunk_index", "block_index", "availability",
                "previous_state_sha256", "prefix_sha256", "prefix_length",
                "orientation", "location_producer", "reference_free_producer",
                "identity_input"});
  for (const auto *field : {"source_sha256", "plan_sha256",
                            "previous_state_sha256", "prefix_sha256"}) {
    hash_shape(binding.at(field));
  }
  require(!text(binding.at("read_id")).empty(), "empty prefix read ID");
  for (const auto *field :
       {"parent_index", "chunk_index", "block_index", "prefix_length"}) {
    static_cast<void>(index(binding.at(field)));
  }
  require(text(binding.at("orientation")) == "forward" ||
              text(binding.at("orientation")) == "reverse",
          "prefix orientation differs");
  validate_availability(binding.at("availability"));
  for (const auto *field : {"input_tensor", "location_producer",
                            "reference_free_producer", "identity_input"}) {
    stat_pin(binding.at(field));
  }
}
void validate_descriptor(const Json &descriptor, const Json &binding) {
  exact_prefix(descriptor, {"schema", "prior", "state_length", "row_begin",
                            "row_end", "available_row_end", "source_sha256",
                            "plan_sha256", "input_tensor", "producers"});
  require(text(descriptor.at("schema")) == "consumed-prefix-descriptor/1" &&
              text(descriptor.at("prior")) == "uniform-all-states" &&
              index(descriptor.at("state_length")) >= 1 &&
              index(descriptor.at("state_length")) <= 4,
          "prefix prior descriptor differs");
  for (const auto *field : {"row_begin", "row_end", "available_row_end"}) {
    require(index(descriptor.at(field)) ==
                index(binding.at("availability").at(field)),
            "prefix descriptor consumed endpoint differs");
  }
  for (const auto *field : {"source_sha256", "plan_sha256", "input_tensor"}) {
    require(descriptor.at(field) == binding.at(field),
            "prefix descriptor source/tensor differs");
  }
  exact_prefix(
      descriptor.at("producers"),
      {"location_producer", "reference_free_producer", "identity_input"});
  for (const auto *field :
       {"location_producer", "reference_free_producer", "identity_input"}) {
    require(descriptor.at("producers").at(field) == binding.at(field),
            "prefix descriptor producer set differs");
  }
}
void validate_identity(const Json &identity, const Json &binding,
                       const std::string &sequence,
                       const std::string &quality) {
  exact_prefix(identity,
               {"schema", "kind", "quality_status", "source_sha256",
                "plan_sha256", "input_tensor", "read_id", "parent_index",
                "chunk_index", "block_index", "availability",
                "previous_state_sha256", "prefix_sha256", "prefix_length",
                "orientation", "sequence", "quality"});
  require(text(identity.at("schema")) == "feedback-prefix-identity/1" &&
              text(identity.at("kind")) == "pipeline-free-input" &&
              text(identity.at("quality_status")) == "uncalibrated",
          "prefix identity schema differs; completed DGM identity forbidden");
  for (const auto *field :
       {"source_sha256", "plan_sha256", "input_tensor", "read_id",
        "parent_index", "chunk_index", "block_index", "availability",
        "previous_state_sha256", "prefix_sha256", "prefix_length",
        "orientation"}) {
    require(identity.at(field) == binding.at(field),
            "prefix identity binding differs");
  }
  require(text(identity.at("sequence")) == sequence &&
              text(identity.at("quality")) == quality &&
              sequence.size() == index(binding.at("prefix_length")) &&
              digest(sequence) == text(binding.at("prefix_sha256")) &&
              std::all_of(quality.begin(), quality.end(),
                          [](char c) { return c == '!'; }),
          "prefix identity sequence/quality/endpoint differs");
}
} // namespace

PrefixNomination nominate_prefix(const std::string &available_prefix,
                                 std::size_t consumed_rows,
                                 const std::vector<std::string> &originals) {
  PrefixNomination result;
  result.tail_end = available_prefix.size();
  result.tail_begin =
      available_prefix.size() > 32 ? available_prefix.size() - 32 : 0;
  if (available_prefix.empty() || available_prefix.size() > 512) {
    result.arm_exclusions.push_back("full-prefix-length-outside-1..512");
  }
  if (consumed_rows == 0 || consumed_rows > 2048) {
    result.arm_exclusions.push_back("consumed-rows-outside-1..2048");
  }
  if (!result.arm_exclusions.empty()) {
    result.status = PrefixNominationStatus::excluded;
    return result;
  }
  dna(available_prefix);
  const std::set<std::string> original_set(originals.begin(), originals.end());
  std::map<std::string, UnscoredProposal> unique;
  const auto put = [&](Edit edit, const std::string &mechanism) {
    ++result.visited;
    auto sequence = available_prefix;
    sequence.replace(edit.begin, edit.end - edit.begin, edit.replacement);
    if (sequence.empty()) {
      ++result.excluded;
      result.exclusions.push_back({{"reason", "empty-result"},
                                   {"mechanism", mechanism},
                                   {"query_begin", edit.begin},
                                   {"query_end", edit.end}});
      return;
    }
    require(sequence.size() <= 514,
            "prefix reconstruction exceeds declared result bound");
    ++result.eligible;
    if (original_set.contains(sequence)) {
      ++result.duplicate;
      ++result.original_duplicates;
      return;
    }
    if (!unique
             .emplace(sequence,
                      UnscoredProposal{sequence, std::move(edit), mechanism})
             .second) {
      ++result.duplicate;
    }
  };
  for (std::size_t position = result.tail_begin; position < result.tail_end;
       ++position) {
    put({position, position + 1, ""}, "single-deletion");
  }
  for (std::size_t position = result.tail_begin; position <= result.tail_end;
       ++position) {
    for (const auto base : std::string("ACGT")) {
      put({position, position, std::string(1, base)}, "single-insertion");
    }
  }
  auto begin = result.tail_begin;
  while (begin < result.tail_end) {
    auto end = begin + 1;
    while (end < result.tail_end &&
           available_prefix[end] == available_prefix[begin]) {
      ++end;
    }
    const auto length = end - begin;
    if (begin == result.tail_begin && begin > 0 &&
        available_prefix[begin - 1] == available_prefix[begin]) {
      ++result.visited;
      ++result.excluded;
      result.exclusions.push_back({{"reason", "left-open-run"},
                                   {"mechanism", "run-length-plus-minus-two"},
                                   {"query_begin", begin},
                                   {"query_end", end}});
    } else if (length >= 2) {
      for (std::size_t replacement = 1; replacement <= 6; ++replacement) {
        const auto difference =
            replacement > length ? replacement - length : length - replacement;
        if (difference > 0 && difference <= 2) {
          put({begin, end, std::string(replacement, available_prefix[begin])},
              "run-length-plus-minus-two");
        }
      }
    }
    begin = end;
  }
  result.unique = unique.size();
  if (unique.size() > 512) {
    result.status = PrefixNominationStatus::excluded;
    result.arm_exclusions.push_back("new-unique-proposals-exceed-512");
  } else {
    for (auto &[sequence, proposal] : unique) {
      static_cast<void>(sequence);
      result.proposals.push_back(std::move(proposal));
    }
  }
  require(result.visited == result.eligible + result.excluded &&
              result.eligible == result.unique + result.duplicate,
          "prefix nomination count conservation differs");
  return result;
}

Json nominate_prefix_request(const Json &request) {
  exact_prefix(request, {"schema", "mode", "batch_pin", "expected_batch_sha256",
                         "expected_binding", "scoring_descriptor",
                         "expected_scoring_descriptor"});
  require(text(request.at("schema")) == "indel-prefix-nomination-request/1" &&
              text(request.at("mode")) == "consumed-prefix-unscored-v1",
          "prefix nomination mode differs");
  hash_shape(request.at("expected_batch_sha256"));
  require(text(request.at("batch_pin").at("sha256")) ==
              text(request.at("expected_batch_sha256")),
          "prefix independent batch hash differs");
  const auto batch = consumed_json(request.at("batch_pin"));
  exact_prefix(batch, {"schema", "kind", "binding", "native",
                       "reference_free_candidate_id", "union_nn_candidate_id",
                       "locations", "candidates"});
  require(text(batch.at("schema")) == "feedback-next/1" &&
              text(batch.at("kind")) == "candidate-batch",
          "prefix normalized batch schema differs");
  require(batch.at("binding") == request.at("expected_binding"),
          "prefix independently expected binding differs");
  const auto &binding = batch.at("binding");
  validate_binding(binding);
  require(request.at("scoring_descriptor") ==
              request.at("expected_scoring_descriptor"),
          "prefix independently expected descriptor differs");
  validate_descriptor(request.at("scoring_descriptor"), binding);
  exact_prefix(batch.at("native"), {"sequence", "quality", "scope"});
  require(text(batch.at("native").at("scope")) == "available_input_segment",
          "prefix native scope differs");
  const auto sequence = text(batch.at("native").at("sequence"));
  const auto quality = text(batch.at("native").at("quality"));
  dna(sequence);
  require(sequence.size() == quality.size() &&
              std::all_of(quality.begin(), quality.end(),
                          [](char c) { return c >= '!' && c <= '~'; }),
          "prefix native quality differs");
  validate_identity(consumed_json(binding.at("identity_input")), binding,
                    sequence, quality);
  require(batch.at("candidates").is_array() &&
              !batch.at("candidates").empty() &&
              batch.at("candidates").size() <= 4096 &&
              batch.at("locations").is_array(),
          "prefix original candidate census differs");
  const auto free_id = text(batch.at("reference_free_candidate_id"));
  const auto union_id = text(batch.at("union_nn_candidate_id"));
  std::set<std::string> ids, sequences;
  std::vector<std::string> originals;
  Json free = nullptr;
  for (const auto &candidate : batch.at("candidates")) {
    exact_prefix(candidate,
                 {"id", "sequence", "neural_log_likelihood", "context_cost",
                  "location_ids", "edits", "eligibility_reasons"});
    const auto id = text(candidate.at("id"));
    const auto original = text(candidate.at("sequence"));
    require(!id.empty() && ids.insert(id).second &&
                sequences.insert(original).second,
            "prefix duplicate original ID/sequence");
    dna(original);
    originals.push_back(original);
    if (id == free_id) {
      free = {{"id", id},
              {"sequence", original},
              {"source_batch_sha256", request.at("expected_batch_sha256")}};
    }
  }
  require(!free.is_null() && ids.contains(union_id) &&
              sequences.contains(sequence),
          "prefix genuine free/union/native role absent");
  const auto nomination = nominate_prefix(
      sequence, index(binding.at("availability").at("row_end")), originals);
  Json proposals_json = Json::array();
  for (const auto &proposal : nomination.proposals) {
    const auto &edit = proposal.edit;
    const auto id = "prefix-indel-" + digest(proposal.sequence);
    require(!ids.contains(id), "prefix proposal ID collides with original");
    proposals_json.push_back(
        {{"id", id},
         {"sequence", proposal.sequence},
         {"edit",
          {{"query_begin", edit.begin},
           {"query_end", edit.end},
           {"reference", sequence.substr(edit.begin, edit.end - edit.begin)},
           {"alternate", edit.replacement}}},
         {"mechanism", proposal.mechanism}});
  }
  check_pin(request.at("batch_pin"));
  check_pin(binding.at("identity_input"));
  return {{"schema", "indel-prefix-proposals/1"},
          {"mode", "consumed-prefix-unscored-v1"},
          {"scoring_status", "unscored"},
          {"status", nomination.status == PrefixNominationStatus::ready
                         ? "ready"
                         : "excluded"},
          {"source_batch", request.at("batch_pin")},
          {"binding", binding},
          {"scoring_descriptor", request.at("scoring_descriptor")},
          {"reference_free_candidate", free},
          {"tail",
           {{"query_begin", nomination.tail_begin},
            {"query_end", nomination.tail_end},
            {"selection", "deterministic-last-32-available-bases"}}},
          {"limits",
           {{"maximum_full_prefix_bases", 512},
            {"maximum_consumed_rows", 2048},
            {"maximum_tail_bases", 32},
            {"maximum_new_unique_proposals", 512},
            {"minimum_result_bases", 1},
            {"maximum_result_bases", 514}}},
          {"counts",
           {{"visited", nomination.visited},
            {"eligible", nomination.eligible},
            {"unique", nomination.unique},
            {"duplicate", nomination.duplicate},
            {"excluded", nomination.excluded},
            {"original_duplicates", nomination.original_duplicates}}},
          {"arm_exclusions", nomination.arm_exclusions},
          {"exclusions", nomination.exclusions},
          {"proposals", proposals_json}};
}
} // namespace indel_feedback
