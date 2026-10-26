#include "context_policy/protocol.h"
#include "compiled_sources.h"

#include <openssl/evp.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>

namespace context_policy {
namespace {
void require(bool condition, const char* message) {
    if (!condition) {
        throw std::invalid_argument(message);
    }
}
void keys(const Json& value, std::initializer_list<const char*> names) {
    require(value.is_object() && value.size() == names.size(), "object field census mismatch");
    for (const char* name : names) {
        require(value.contains(name), "missing required field");
    }
}
std::string str(const Json& value) {
    require(value.is_string(), "expected string");
    const auto result = value.get<std::string>();
    require(!result.empty() && result.size() <= 4096, "empty or overlong string");
    return result;
}
void hash_value(const Json& value) {
    const auto s = str(value);
    require(s.size() == 64 && std::all_of(s.begin(), s.end(), [](char c) {
                return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
            }), "invalid SHA256");
}
std::uint64_t natural(const Json& value) {
    require(value.is_number_unsigned() || (value.is_number_integer() && value.get<std::int64_t>() >= 0),
            "expected unsigned integer");
    return value.get<std::uint64_t>();
}
double real(const Json& value) {
    require(value.is_number(), "expected real number");
    const double result = value.get<double>();
    require(std::isfinite(result), "nonfinite real number");
    return result;
}
void pin(const Json& value) {
    keys(value, {"path", "size", "sha256"});
    const auto path = str(value.at("path"));
    require(path.starts_with('/'), "pin path is not absolute");
    static_cast<void>(natural(value.at("size")));
    hash_value(value.at("sha256"));
}
std::vector<std::string> strings(const Json& value) {
    require(value.is_array() && value.size() <= 4096, "expected bounded array");
    std::vector<std::string> result;
    for (const auto& item : value) {
        result.push_back(str(item));
    }
    return result;
}
void binding(const Json& value) {
    keys(value, {"source_sha256", "plan_sha256", "input_tensor", "read_id", "parent_index",
                 "chunk_index", "block_index", "availability", "previous_state_sha256", "prefix_sha256",
                 "prefix_length", "orientation", "location_producer", "reference_free_producer",
                 "identity_input"});
    for (const auto* name : {"source_sha256", "plan_sha256", "previous_state_sha256", "prefix_sha256"}) {
        hash_value(value.at(name));
    }
    pin(value.at("input_tensor"));
    pin(value.at("location_producer"));
    pin(value.at("reference_free_producer"));
    pin(value.at("identity_input"));
    static_cast<void>(str(value.at("read_id")));
    for (const auto* name : {"parent_index", "chunk_index", "block_index", "prefix_length"}) {
        static_cast<void>(natural(value.at(name)));
    }
    const auto orientation = str(value.at("orientation"));
    require(orientation == "forward" || orientation == "reverse", "invalid orientation");
    const auto& available = value.at("availability");
    keys(available, {"kind", "row_begin", "row_end", "available_row_end", "chunk_lookahead",
                     "signal_geometry"});
    require(available.at("kind") == "released-score-block" &&
                available.at("chunk_lookahead") == "whole_chunk" &&
                available.at("signal_geometry").is_null(), "unsupported availability kind");
    require(natural(available.at("row_begin")) <= natural(available.at("row_end")) &&
                natural(available.at("row_end")) <= natural(available.at("available_row_end")),
            "unavailable score endpoint");
}
Batch batch_from(const Json& value) {
    keys(value, {"schema", "kind", "binding", "native", "reference_free_candidate_id",
                 "union_nn_candidate_id", "locations", "candidates"});
    require(value.at("schema") == "feedback-next/1" && value.at("kind") == "candidate-batch",
            "foreign candidate schema");
    binding(value.at("binding"));
    keys(value.at("native"), {"sequence", "quality", "scope"});
    require(value.at("native").at("scope") == "available_input_segment", "unavailable identity input");
    Batch result;
    result.native_sequence = value.at("native").at("sequence").get<std::string>();
    result.native_quality = value.at("native").at("quality").get<std::string>();
    result.reference_free_candidate_id = str(value.at("reference_free_candidate_id"));
    result.union_nn_candidate_id = str(value.at("union_nn_candidate_id"));
    require(value.at("locations").is_array() && value.at("locations").size() <= 64,
            "invalid location array");
    for (const auto& location : value.at("locations")) {
        keys(location, {"id", "contig", "strand", "query_begin", "query_end", "reference_begin",
                        "reference_end", "confidence"});
        keys(location.at("confidence"), {"feature", "value", "meaning"});
        require(location.at("confidence").at("feature") == "declared-location-support" &&
                    location.at("confidence").at("meaning") == "bounded_support_not_probability",
                "unknown location confidence semantics");
        static_cast<void>(str(location.at("contig")));
        require(location.at("strand") == "+" || location.at("strand") == "-", "invalid strand");
        require(natural(location.at("query_begin")) <= natural(location.at("query_end")) &&
                    natural(location.at("query_end")) <= natural(value.at("binding").at("prefix_length")),
                "location reads unavailable prefix");
        require(natural(location.at("reference_begin")) <= natural(location.at("reference_end")),
                "invalid reference interval");
        result.locations.push_back({str(location.at("id")), real(location.at("confidence").at("value"))});
    }
    require(value.at("candidates").is_array() && value.at("candidates").size() <= 4096,
            "invalid candidate array");
    for (const auto& item : value.at("candidates")) {
        keys(item, {"id", "sequence", "neural_log_likelihood", "context_cost", "location_ids", "edits",
                    "eligibility_reasons"});
        const auto sequence = item.at("sequence").get<std::string>();
        require(sequence.size() <= 4096, "overlong candidate");
        require(item.at("edits").is_array() && item.at("edits").size() <= 4096, "invalid edits");
        std::size_t cursor = 0;
        std::string reconstructed;
        for (const auto& edit : item.at("edits")) {
            keys(edit, {"operation", "query_position", "reference", "alternate"});
            const auto op = str(edit.at("operation"));
            require(op == "SNV" || op == "INS" || op == "DEL", "unknown edit operation");
            require(natural(edit.at("query_position")) <= result.native_sequence.size(),
                    "edit exceeds native extent");
            require(edit.at("reference").is_string() && edit.at("alternate").is_string(),
                    "invalid edit alleles");
            const auto reference = edit.at("reference").get<std::string>();
            const auto alternate = edit.at("alternate").get<std::string>();
            const auto position = natural(edit.at("query_position"));
            const auto dna = [](const std::string& text) {
                return std::all_of(text.begin(), text.end(), [](char base) {
                    return base == 'A' || base == 'C' || base == 'G' || base == 'T';
                });
            };
            require(dna(reference) && dna(alternate), "non-DNA edit alleles");
            require((op == "SNV" && reference.size() == 1 && alternate.size() == 1 && reference != alternate) ||
                        (op == "INS" && reference.empty() && !alternate.empty()) ||
                        (op == "DEL" && !reference.empty() && alternate.empty()), "invalid edit shape");
            require(position >= cursor && reference.size() <= result.native_sequence.size() - position &&
                        result.native_sequence.substr(position, reference.size()) == reference,
                    "overlapping or mismatched edit");
            reconstructed += result.native_sequence.substr(cursor, position - cursor);
            reconstructed += alternate;
            cursor = position + reference.size();
        }
        reconstructed += result.native_sequence.substr(cursor);
        require(reconstructed == sequence, "edit list does not reconstruct candidate");
        result.candidates.push_back({str(item.at("id")), sequence,
                                     real(item.at("neural_log_likelihood")), real(item.at("context_cost")),
                                     strings(item.at("location_ids")), strings(item.at("eligibility_reasons"))});
    }
    return result;
}
Policy policy_from(const Json& value) {
    keys(value, {"mode", "maximum_context_weight", "maximum_neural_deficit", "minimum_objective_margin",
                 "parameter_status", "quality_status"});
    require(value.at("parameter_status") == "predeclared_unfitted" &&
                value.at("quality_status") == "uncalibrated", "unsupported calibration claim");
    const auto mode = str(value.at("mode"));
    require(mode == "disabled" || mode == "prior-none" || mode == "fixed" || mode == "adaptive",
            "unknown policy mode");
    const auto selected_mode = mode == "disabled" ? Mode::disabled :
                               mode == "prior-none" ? Mode::prior_none :
                               mode == "fixed" ? Mode::fixed : Mode::adaptive;
    return {selected_mode, real(value.at("maximum_context_weight")),
            real(value.at("maximum_neural_deficit")), real(value.at("minimum_objective_margin"))};
}
}
Json parse(const std::string& bytes) {
    std::vector<std::set<std::string>> objects;
    return Json::parse(bytes, [&](int, Json::parse_event_t event, Json& value) {
        if (event == Json::parse_event_t::object_start) {
            objects.emplace_back();
        } else if (event == Json::parse_event_t::key) {
            require(objects.back().insert(value.get<std::string>()).second, "duplicate JSON key");
        } else if (event == Json::parse_event_t::object_end) {
            objects.pop_back();
        }
        return true;
    });
}
std::string digest(const std::string& bytes) {
    std::array<unsigned char, EVP_MAX_MD_SIZE> hash{};
    unsigned int size = 0;
    require(EVP_Digest(bytes.data(), bytes.size(), hash.data(), &size, EVP_sha256(), nullptr) == 1,
            "SHA256 failed");
    std::ostringstream result;
    result << std::hex << std::setfill('0');
    for (unsigned int i = 0; i < size; ++i) {
        result << std::setw(2) << static_cast<unsigned int>(hash[i]);
    }
    return result.str();
}
Json decide_request(const Json& request, const std::string& batch_bytes) {
    keys(request, {"schema", "batch_pin", "expected_binding", "expected_batch_sha256", "policy"});
    require(request.at("schema") == "feedback-next/1", "foreign request schema");
    pin(request.at("batch_pin"));
    hash_value(request.at("expected_batch_sha256"));
    const auto hash = digest(batch_bytes);
    require(batch_bytes.size() <= 8388608 && batch_bytes.size() == natural(request.at("batch_pin").at("size")) &&
                hash == request.at("batch_pin").at("sha256") && hash == request.at("expected_batch_sha256"),
            "foreign or stale candidate batch hash");
    const auto input = parse(batch_bytes);
    const auto batch = batch_from(input);
    binding(request.at("expected_binding"));
    require(input.at("binding") == request.at("expected_binding"), "foreign or stale batch binding");
    const auto policy = policy_from(request.at("policy"));
    const auto result = decide(batch, policy);
    Json assessments = Json::array();
    for (const auto& item : result.assessments) {
        assessments.push_back({{"candidate_id", item.candidate_id}, {"objective", item.objective},
                               {"neural_deficit", item.neural_deficit}, {"reasons", item.reasons}});
    }
    return {{"schema", "feedback-next/1"}, {"kind", "policy-decision"}, {"batch_sha256", hash},
            {"reference_free_candidate_id", batch.reference_free_candidate_id},
            {"union_nn_candidate_id", batch.union_nn_candidate_id},
            {"binding", input.at("binding")}, {"policy_sha256", digest(request.at("policy").dump())},
            {"selected_candidate_id", result.selected_candidate_id}, {"sequence", result.sequence},
            {"quality", result.quality}, {"reason", result.reason},
            {"effective_context_weight", result.context_weight}, {"confidence", "uncalibrated"},
            {"assessments", assessments}};
}
void verify_source_file(const std::string& path, std::uintmax_t size, const std::string& sha256) {
        std::ifstream input(path, std::ios::binary | std::ios::ate);
        require(input.good() && input.tellg() >= 0, "compiled source unavailable");
        require(static_cast<std::uintmax_t>(input.tellg()) == size && size <= 8388608,
                "compiled source size changed");
        input.seekg(0);
        const std::string bytes{std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
        require(digest(bytes) == sha256, "compiled source hash changed");
}
void verify_compiled_sources() {
    require(std::filesystem::current_path() == std::filesystem::path(source_root_path),
            "compiled source root differs from cwd");
    for (const auto& source : compiled_sources) {
        verify_source_file(source.path, source.size, source.sha256);
    }
}
}
