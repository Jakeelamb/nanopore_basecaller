#include "prefix_feedback/feedback.h"

#include "compiled_sources.h"
#include "context_decoder/io.h"

#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>

namespace prefix_feedback {
namespace {
constexpr char uuid[] = "7214d805-8331-49aa-af61-478be074d7a6";
std::size_t number(const std::string& text) {
    std::size_t value{};
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    require(result.ec == std::errc{} && result.ptr == text.data() + text.size(),
            "invalid unsigned integer");
    return value;
}
bool dna(const std::string& text) {
    return std::all_of(text.begin(), text.end(), [](char base) {
        return std::string("ACGT").find(base) != std::string::npos;
    });
}
std::string reverse_complement(std::string text) {
    std::reverse(text.begin(), text.end());
    for (auto& base : text) {
        base = std::string("TGCA").at(std::string("ACGT").find(base));
    }
    return text;
}
void file_pin(const context_decoder::Fields& fields, const std::string& key) {
    const std::filesystem::path path(fields.at(key + "_path"));
    require(path.is_absolute() && std::filesystem::is_regular_file(path),
            "absolute pinned file required");
    require(std::filesystem::file_size(path) == number(fields.at(key + "_size")),
            "input size differs");
    require(context_decoder::sha256(path) == fields.at(key + "_sha256"), "input SHA256 differs");
}
std::string choice(const context_decoder::Choice& value) {
    std::ostringstream out;
    out << std::setprecision(17) << "{\"sequence\":" << context_decoder::quote(value.sequence)
        << ",\"signal_likelihood\":" << value.signal_likelihood
        << ",\"objective\":" << value.objective << '}';
    return out.str();
}
}

void require(bool condition, const char* message) {
    if (!condition) {
        throw std::invalid_argument(message);
    }
}
void preserve_committed(const std::string& committed, const std::string& revision) {
    require(revision.starts_with(committed), "committed bases cannot be overwritten");
}
void Session::admit(std::size_t next_horizon, bool reset_encoder) {
    require(reset_encoder, "v1 requires an explicit reset encoder at each horizon");
    require((horizon == 0 && next_horizon == 4096) || (horizon == 4096 && next_horizon == 12288),
            "admitted horizons must advance once through4096 then12288");
    horizon = next_horizon;
    encoder_reset = reset_encoder;
}
void Session::revise(const std::string& sequence, std::size_t irreversible_bases) {
    require(horizon != 0 && dna(sequence), "revision requires admitted horizon and DNA");
    require(irreversible_bases == 0,
            "bounded prefix redecode v1 permits zero irreversible commits");
    preserve_committed(committed_prefix, sequence);
    revision = sequence;
}
std::vector<double> read_pfs(const std::filesystem::path& path, std::size_t horizon) {
    require(horizon == 4096 || horizon == 12288, "unadmitted PFS1 horizon");
    require(std::endian::native == std::endian::little && sizeof(float) == 4 &&
                    std::numeric_limits<float>::is_iec559,
            "PFS1 requires IEEE little endian float32");
    std::ifstream input(path, std::ios::binary);
    require(input.good(), "cannot read PFS1");
    const auto valid = horizon - 10;
    const auto padded = ((valid + 5) / 6) * 6;
    const auto rows = padded / 6;
    std::ostringstream expected;
    expected << "PFS1\t" << rows << "\t1024\t4\t6\tcpu\tfloat32\t" << horizon << "\t10\t" << valid
             << '\t' << padded;
    std::string header;
    require(static_cast<bool>(std::getline(input, header)) && header == expected.str(),
            "PFS1 exact header mismatch; DGS1 is not accepted");
    std::vector<float> values(rows * 1024);
    input.read(reinterpret_cast<char*>(values.data()),
               static_cast<std::streamsize>(values.size() * sizeof(float)));
    require(input.gcount() == static_cast<std::streamsize>(values.size() * sizeof(float)) &&
                    input.peek() == std::char_traits<char>::eof(),
            "PFS1 exact payload size mismatch");
    std::vector<double> result;
    result.reserve(values.size());
    for (const float value : values) {
        require(std::isfinite(value) && std::abs(value) <= 5.000001F,
                "PFS1 nonfinite or outside declared native CPU clamp5");
        result.push_back(static_cast<double>(value));
    }
    return result;
}
Window load_window(const std::filesystem::path& packet, const std::string& expected_sha256) {
    require(context_decoder::sha256(packet) == expected_sha256, "window packet changed");
    const auto fields = context_decoder::fields(packet, "prefix-feedback-window/1");
    std::set<std::string> allowed{"parent",
                                  "qname",
                                  "horizon",
                                  "core_begin",
                                  "core_end",
                                  "row_begin",
                                  "row_end",
                                  "initial_context",
                                  "contig",
                                  "reference_begin",
                                  "reference_end",
                                  "reverse",
                                  "location_status",
                                  "selection_recipe",
                                  "context_status",
                                  "native_start",
                                  "local_start",
                                  "score_layout",
                                  "score_clamp",
                                  "padding_selection",
                                  "reference_sha256",
                                  "snapshot_sha256",
                                  "reference_index_custody"};
    for (const std::string key :
         {"native", "tensor", "metadata", "prefix_complete", "location_complete", "locations",
          "reference_context", "reference_index"}) {
        for (const std::string suffix : {"_path", "_size", "_sha256"}) {
            allowed.insert(key + suffix);
        }
        file_pin(fields, key);
    }
    std::set<std::string> actual;
    for (const auto& [key, value] : fields) {
        static_cast<void>(value);
        actual.insert(key);
    }
    require(actual == allowed, "unknown or missing window field");
    Window result;
    result.parent = fields.at("parent");
    result.horizon = number(fields.at("horizon"));
    require(result.horizon == 4096 || result.horizon == 12288, "unadmitted window horizon");
    result.qname = fields.at("qname");
    require(result.parent == uuid &&
                    result.qname == result.parent + "__H" + std::to_string(result.horizon),
            "window parent/QNAME/horizon mismatch");
    require(fields.at("location_status") == "located" &&
                    fields.at("context_status") == "reference_only" &&
                    fields.at("selection_recipe") == "quality_min20_then_sha256_tie_v1" &&
                    fields.at("native_start") == "uniform_native_cpu" &&
                    fields.at("local_start") == "condition_on_native4_matched_arms" &&
                    fields.at("score_layout") == "4*next+(previous>>6)" &&
                    fields.at("score_clamp") == "native_cpu_5" &&
                    fields.at("padding_selection") == "exclude_nominal_rows_past_H",
            "undeclared inference semantics");
    require(fields.at("reference_index_custody") ==
                            "individually_pinned_retained_index_no_producer_provenance_claim" &&
                    !std::filesystem::is_symlink(fields.at("reference_index_path")),
            "retained reference index custody mismatch");
    const auto native = context_decoder::fields(fields.at("native_path"), "prefix-native/1");
    require(native.size() == 6 && native.at("uuid") == result.parent &&
                    number(native.at("raw_horizon")) == result.horizon &&
                    native.at("initial_state") == "uniform_native_cpu",
            "native prefix identity mismatch");
    const auto& sequence = native.at("SEQ");
    result.native_prefix = sequence;
    const auto& quality = native.at("Q");
    const auto& moves = native.at("MOVES");
    require(dna(sequence) && !sequence.empty() && sequence.size() == quality.size(),
            "invalid native SEQ/Q");
    require(std::all_of(quality.begin(), quality.end(), [](char q) { return q >= 33 && q <= 126; }),
            "invalid native Q");
    require(moves.size() == ((result.horizon - 10 + 5) / 6) &&
                    std::all_of(moves.begin(), moves.end(),
                                [](char move) { return move == '0' || move == '1'; }),
            "invalid native MOVES");
    std::vector<std::size_t> emission_rows;
    for (std::size_t row = 0; row < moves.size(); ++row) {
        if (moves[row] == '1') {
            emission_rows.push_back(row);
        }
    }
    require(emission_rows.size() == sequence.size(), "MOVES emitted length mismatch");
    result.core_begin = number(fields.at("core_begin"));
    result.core_end = number(fields.at("core_end"));
    require(result.core_begin >= 14 && result.core_end == result.core_begin + 20 &&
                    result.core_end + 20 < sequence.size(),
            "core/guard boundary mismatch");
    const auto begin = result.core_begin - 10;
    const auto end = result.core_end + 20;
    result.row_begin = number(fields.at("row_begin"));
    result.row_end = number(fields.at("row_end"));
    require(result.row_begin == emission_rows[begin] && result.row_end == emission_rows[end] &&
                    result.row_end > result.row_begin && result.row_end - result.row_begin <= 128 &&
                    result.row_end * 6 + 10 <= result.horizon,
            "MOVES row interval or admitted-H padding boundary mismatch");
    const auto initial = sequence.substr(begin - 4, 4);
    require(fields.at("initial_context") == initial, "local initial native4 mismatch");
    std::size_t state{};
    for (const char base : initial) {
        state = state * 4 + std::string("ACGT").find(base);
    }
    auto payload = read_pfs(fields.at("tensor_path"), result.horizon);
    auto& window = result.guarded;
    window.scores = {result.row_end - result.row_begin, 4, state, 2.0,
                     std::vector<double>(
                             payload.begin() + static_cast<std::ptrdiff_t>(result.row_begin * 1024),
                             payload.begin() + static_cast<std::ptrdiff_t>(result.row_end * 1024))};
    window.left_guard = sequence.substr(begin, 10);
    window.native_center = sequence.substr(result.core_begin, 20);
    window.right_guard = sequence.substr(result.core_end, 20);
    std::ifstream context_file(fields.at("reference_context_path"));
    std::string line;
    const auto expected_region = ">" + fields.at("contig") + ":" +
                                 std::to_string(number(fields.at("reference_begin")) + 1) + "-" +
                                 fields.at("reference_end");
    require(static_cast<bool>(std::getline(context_file, line)) && line == expected_region,
            "faidx header/interval mismatch");
    std::string context;
    while (std::getline(context_file, line)) {
        context += line;
    }
    require(context.size() == 20 && dna(context), "faidx context must have20 canonical bases");
    require(fields.at("reverse") == "0" || fields.at("reverse") == "1", "invalid orientation");
    require(number(fields.at("reference_end")) == number(fields.at("reference_begin")) + 20,
            "reference interval mismatch");
    require(fields.at("reference_sha256").size() == 64 &&
                    fields.at("snapshot_sha256") ==
                            "f975ce48f4abde771809985dd6c67c19bd440c534984331388bf8d7639c21324",
            "reference identity mismatch");
    if (fields.at("reverse") == "1") {
        context = reverse_complement(context);
    }
    window.center_context = {context_decoder::Availability::usable, {context}};
    return result;
}
Session load_session(const std::filesystem::path& path,
                     const std::string& expected_sha256,
                     const Window& window) {
    require(context_decoder::sha256(path) == expected_sha256, "session input changed");
    const auto fields = context_decoder::fields(path, "prefix-feedback-session-input/1");
    std::set<std::string> allowed{"parent",
                                  "previous_horizon",
                                  "previous_revision",
                                  "committed_prefix",
                                  "current_horizon",
                                  "encoder_reset",
                                  "policy"};
    for (const std::string key : {"prior_complete", "prior_result", "prior_binding"}) {
        for (const std::string suffix : {"_path", "_size", "_sha256"}) {
            allowed.insert(key + suffix);
        }
    }
    std::set<std::string> actual;
    for (const auto& [key, value] : fields) {
        static_cast<void>(value);
        actual.insert(key);
    }
    require(actual == allowed && fields.at("parent") == window.parent &&
                    number(fields.at("current_horizon")) == window.horizon &&
                    fields.at("encoder_reset") == "1" &&
                    fields.at("policy") == "bounded_reset_zero_commits",
            "session parent/horizon/policy mismatch");
    file_pin(fields, "prior_binding");
    Session session;
    session.horizon = number(fields.at("previous_horizon"));
    session.revision = fields.at("previous_revision");
    session.committed_prefix = fields.at("committed_prefix");
    require(dna(session.revision) && dna(session.committed_prefix) &&
                    session.committed_prefix.empty(),
            "v1 prior session must have DNA and zero irreversible commits");
    preserve_committed(session.committed_prefix, session.revision);
    if (session.horizon == 0) {
        require(session.revision.empty(), "initial session revision must be empty");
        for (const std::string key : {"prior_complete", "prior_result"}) {
            require(fields.at(key + "_path") == "none" && fields.at(key + "_size") == "0" &&
                            fields.at(key + "_sha256") == std::string(64, '0'),
                    "initial session cannot claim a prior producer");
        }
    } else {
        require(!session.revision.empty(), "prior session revision is missing");
        file_pin(fields, "prior_complete");
        file_pin(fields, "prior_result");
    }
    session.admit(window.horizon, true);
    return session;
}
std::string decode(const Window& window, Session& session) {
    require(session.horizon == window.horizon && session.encoder_reset,
            "decoder did not admit the actual session horizon/reset");
    const context_decoder::GuardedPolicy policy{64, 0, 64, 0.5, 0.5, 0.5};
    const auto ordinary = context_decoder::decode_guarded(window.guarded, policy);
    auto missing = window.guarded;
    missing.center_context = {context_decoder::Availability::missing, {}};
    const auto fallback = context_decoder::decode_guarded(missing, policy);
    auto disabled = policy;
    disabled.context_weight = 0.0;
    const auto zero = context_decoder::decode_guarded(window.guarded, disabled);
    require(context_decoder::guarded_outcome_json(zero) ==
                    context_decoder::guarded_outcome_json(fallback),
            "disabled/missing identity differs");
    auto wrong = window.guarded;
    auto& wrong_sequence = wrong.center_context.sequences.front();
    for (auto& base : wrong_sequence) {
        base = std::string("CGTA").at(std::string("ACGT").find(base));
    }
    const auto wrong_result = context_decoder::decode_guarded(wrong, policy);
    std::set<std::string> escape{ordinary.native.sequence};
    for (const auto& candidate : ordinary.escape.finalists) {
        escape.insert(candidate.sequence);
    }
    std::size_t novel{};
    for (const auto& candidate : ordinary.conditioned.finalists) {
        novel += static_cast<std::size_t>(!escape.contains(candidate.sequence));
    }
    session.revise(window.native_prefix.substr(0, window.core_begin) + ordinary.selected.sequence +
                           window.native_prefix.substr(window.core_end),
                   0);
    std::ostringstream out;
    out << std::setprecision(17) << "{\"schema\":\"prefix-feedback-result/1\",\"parent\":"
        << context_decoder::quote(window.parent)
        << ",\"qname\":" << context_decoder::quote(window.qname)
        << ",\"horizon\":" << window.horizon
        << ",\"latency_seconds\":" << static_cast<double>(window.horizon) / 5000.0
        << ",\"irreversible_commits\":" << session.committed_prefix.size()
        << ",\"encoder_reset\":" << (session.encoder_reset ? "true" : "false")
        << ",\"streaming_state_continuity\":false"
        << ",\"session\":{\"schema\":\"prefix-feedback-session/1\",\"parent\":"
        << context_decoder::quote(window.parent) << ",\"horizon\":" << session.horizon
        << ",\"revision\":" << context_decoder::quote(session.revision)
        << ",\"committed_prefix\":" << context_decoder::quote(session.committed_prefix)
        << ",\"committed_quality\":\"\",\"encoder_reset\":"
        << (session.encoder_reset ? "true" : "false")
        << ",\"policy\":\"bounded_reset_zero_commits\"}"
        << ",\"context_novel_finalists\":" << novel << ",\"selected_absent_escape\":"
        << (!escape.contains(ordinary.selected.sequence) ? "true" : "false")
        << ",\"matched_reference_free\":" << choice(ordinary.reference_free)
        << ",\"final_rerank\":" << choice(ordinary.final_rerank)
        << ",\"partial_search\":" << context_decoder::guarded_outcome_json(ordinary)
        << ",\"wrong_context\":" << context_decoder::guarded_outcome_json(wrong_result)
        << ",\"missing_context\":" << context_decoder::guarded_outcome_json(fallback)
        << ",\"disabled_identity\":true,\"variant_safety_qualified\":false} ";
    return out.str();
}
std::string source_json() {
    std::ostringstream out;
    out << "[";
    bool first = true;
    for (const auto& source : compiled_sources) {
        require(context_decoder::sha256(source.path) == source.sha256 &&
                        std::filesystem::file_size(source.path) == source.size,
                "compiled source closure changed");
        out << (first ? "" : ",") << "{\"path\":" << context_decoder::quote(source.path)
            << ",\"size\":" << source.size
            << ",\"sha256\":" << context_decoder::quote(source.sha256) << '}';
        first = false;
    }
    require(context_decoder::sha256(compiler_path) == compiler_sha256 &&
                    context_decoder::sha256(formatter_path) == formatter_sha256,
            "compiler or formatter identity changed");
    out << ']';
    return out.str();
}
}
