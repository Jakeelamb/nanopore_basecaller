#pragma once

#include <json.hpp>
#include <openssl/evp.h>

#include <bit>
#include <cmath>
#include <cstdint>
#include <array>
#include <iomanip>
#include <limits>
#include <sstream>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace targeting_mechanism {
#ifndef TARGETING_SOURCE_CUT_SHA256
#error "The isolated mechanism source census must be pinned by the admitted build"
#endif
using Json = nlohmann::json;
using Strings = std::set<std::string>;
inline void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::invalid_argument(message);
    }
}
inline std::size_t natural(const Json& value) {
    require(value.is_number_unsigned() ||
                    (value.is_number_integer() && value.get<std::int64_t>() >= 0),
            "Nonnegative integer required");
    return value.get<std::size_t>();
}
inline std::string dna(const Json& value) {
    const auto text = value.get<std::string>();
    require(text.size() <= 108 && text.find_first_not_of("ACGT") == std::string::npos,
            "Center exceeds canonical 0..108 bound");
    return text;
}
inline Strings centers(const Json& rows, const std::string& field) {
    require(rows.is_array() && rows.size() <= 128, "Finalist census exceeds beam128");
    Strings result;
    for (const auto& row : rows) {
        require(result.insert(dna(row.at(field))).second, "Duplicate finalist center");
    }
    return result;
}
inline std::string hash_text(const std::string& text) {
    std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
    unsigned count{};
    require(EVP_Digest(text.data(), text.size(), digest.data(), &count, EVP_sha256(), nullptr) ==
                            1 &&
                    count == 32,
            "SHA256 failed");
    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (unsigned i = 0; i < count; ++i) {
        output << std::setw(2) << static_cast<unsigned>(digest[i]);
    }
    return output.str();
}

// Layout is the read-only original context_decoder/src/main.cpp::phase_trace.
// No decoder, likelihood, potential, or decision implementation is linked here.
class TraceReader {
    std::string_view bytes_;
    std::size_t offset_{};

public:
    explicit TraceReader(std::string_view bytes) : bytes_(bytes) {
        constexpr std::string_view header = "guarded-phase-trace/2\n";
        require(bytes_.starts_with(header), "Original guarded trace format differs");
        offset_ = header.size();
    }
    std::uint64_t integer() {
        require(bytes_.size() - offset_ >= 8, "Truncated trace integer");
        std::uint64_t value{};
        for (unsigned shift = 0; shift < 64; shift += 8) {
            value |= static_cast<std::uint64_t>(static_cast<unsigned char>(bytes_[offset_++]))
                     << shift;
        }
        return value;
    }
    double real(bool finite) {
        const auto value = std::bit_cast<double>(integer());
        require(!std::isnan(value) && value != std::numeric_limits<double>::infinity() &&
                        (!finite || std::isfinite(value)),
                "Invalid trace mass/potential/rank");
        return value;
    }
    void vector(std::size_t expected) {
        require(expected <= 128 && integer() == expected, "Trace phase-vector geometry differs");
        for (std::size_t i = 0; i < expected; ++i) {
            static_cast<void>(real(false));
        }
    }
    std::string sequence() {
        const auto size = integer();
        require(size <= 108 && size <= bytes_.size() - offset_, "Trace center byte bound differs");
        const auto result = std::string(bytes_.substr(offset_, static_cast<std::size_t>(size)));
        offset_ += static_cast<std::size_t>(size);
        return dna(Json(result));
    }
    std::vector<Strings> search(const Json& saved,
                                std::size_t steps,
                                std::size_t left,
                                std::size_t right) {
        require(steps > 0 && steps <= 256 && integer() == steps &&
                        saved.at("trace").size() == steps,
                "Trace timestep count/expanded geometry differs");
        std::vector<Strings> sets;
        bool any_pruned = false;
        for (std::size_t i = 0; i < steps; ++i) {
            const auto& row = saved.at("trace").at(i);
            require(integer() == i + 1 && natural(row.at("timestep")) == i + 1,
                    "Trace timestep order differs");
            const auto generated = integer(), merged = integer(), pruned = integer();
            require(generated == natural(row.at("generated")) &&
                            merged == natural(row.at("merged")) &&
                            pruned == natural(row.at("pruned")) && generated >= merged,
                    "Trace/JSON work census differs");
            vector(left);
            const auto count = integer();
            require(count <= 128 && merged >= count && pruned <= merged - count &&
                            row.at("retained_centers").size() == count,
                    "Trace retained/pruned census differs");
            Strings retained;
            double previous_rank = std::numeric_limits<double>::infinity();
            std::string previous_center;
            for (std::size_t j = 0; j < count; ++j) {
                const auto center = sequence();
                require(center == row.at("retained_centers").at(j).get<std::string>() &&
                                retained.insert(center).second,
                        "Actual trace/JSON center or uniqueness differs");
                static_cast<void>(real(false));
                vector(right);
                static_cast<void>(real(true));
                static_cast<void>(real(true));
                const auto rank = real(true);
                require(rank < previous_rank ||
                                (rank == previous_rank && (j == 0 || previous_center < center)),
                        "Actual retained rank/lexical tie order differs");
                previous_rank = rank;
                previous_center = center;
            }
            any_pruned = any_pruned || pruned != 0;
            sets.push_back(std::move(retained));
        }
        require(saved.at("pruned") == any_pruned, "Search pruning flag differs from actual steps");
        for (const auto& center : centers(saved.at("finalists"), "center")) {
            require(sets.back().contains(center), "Finalist absent actual terminal retained set");
        }
        return sets;
    }
    void end() const { require(offset_ == bytes_.size(), "Trace has trailing bytes/extra search"); }
};

inline Json observe(const Json& native, const Json& request, const std::string& raw) {
    require(native.at("schema") == "context-decoder-guarded-frame/2" &&
                    native.at("phase_trace") ==
                            request.at("trace_descriptor").at("storage").at("original") &&
                    natural(native.at("retained_rust_scalar_bit_comparisons")) > 0,
            "Original result/trace/scalar join differs");
    const auto& binding = native.at("binding");
    const auto& outcome = native.at("outcome");
    require(outcome.at("schema") == "guarded-outcome/2", "Guarded outcome format differs");
    const auto steps = natural(request.at("timesteps"));
    require(std::stoull(binding.at("expanded_t_end").get<std::string>()) -
                                    std::stoull(
                                            binding.at("expanded_t_start").get<std::string>()) ==
                            steps &&
                    binding.at("native_center") == outcome.at("native").at("sequence"),
            "Expanded result geometry/native center differs");
    TraceReader trace(raw);
    const auto& free_search = outcome.at("reference_free_escape");
    const auto& source_search = outcome.at("conditioned_search");
    const auto free_sets =
            trace.search(free_search, steps, binding.at("left_guard").get<std::string>().size(),
                         binding.at("right_guard").get<std::string>().size());
    const auto source_sets =
            trace.search(source_search, steps, binding.at("left_guard").get<std::string>().size(),
                         binding.at("right_guard").get<std::string>().size());
    trace.end();
    auto h = centers(free_search.at("finalists"), "center");
    const auto native_center = dna(outcome.at("native").at("sequence"));
    h.insert(native_center);
    const auto free_finalists = centers(free_search.at("finalists"), "center");
    const auto source_finalists = centers(source_search.at("finalists"), "center");
    auto expected_union = h;
    expected_union.insert(source_finalists.begin(), source_finalists.end());
    Strings union_seen, novel;
    Json origins = Json::array();
    for (const auto& candidate : outcome.at("candidates")) {
        const auto center = dna(candidate.at("choice").at("sequence"));
        require(union_seen.insert(center).second &&
                        candidate.at("native") == (center == native_center) &&
                        candidate.at("free_finalist") == free_finalists.contains(center) &&
                        candidate.at("conditioned_finalist") == source_finalists.contains(center),
                "Candidate origin flags differ from actual same-frame finalists/native");
        const bool new_center = !h.contains(center);
        if (new_center) {
            novel.insert(center);
        }
        origins.push_back({{"sequence", center},
                           {"native", center == native_center},
                           {"free_finalist", free_finalists.contains(center)},
                           {"conditioned_finalist", source_finalists.contains(center)},
                           {"absent_same_frame_H", new_center}});
    }
    require(union_seen == expected_union,
            "Candidate U differs from current escape/native/source union");
    Strings panel, supplied;
    for (const auto& center : request.at("projected_graph_panel_strings")) {
        const auto text = center.get<std::string>();
        panel.insert(text);
    }
    for (const auto& center : request.at("actual_decoder_context_strings")) {
        const auto text = center.get<std::string>();
        require(panel.contains(text), "Actual decoder context string absent graph projection");
        supplied.insert(text);
    }
    Json panel_membership = Json::array();
    for (const auto& center : panel) {
        panel_membership.push_back(
                {{"sequence", center},
                 {"actually_supplied_as_decoder_context", supplied.contains(center)},
                 {"canonical_DNA", center.find_first_not_of("ACGT") == std::string::npos},
                 {"present_in_same_frame_H", h.contains(center)},
                 {"present_in_actual_U", union_seen.contains(center)},
                 {"native", center == native_center},
                 {"free_finalist", free_finalists.contains(center)},
                 {"conditioned_finalist", source_finalists.contains(center)}});
    }
    const bool enabled = outcome.at("context_enabled").get<bool>();
    require(request.at("context_enabled") == enabled &&
                    (request.at("context_availability") == "usable") == enabled &&
                    (!supplied.empty()) == enabled,
            "Qualified availability/enabled join differs at fixed nonzero weight");
    Json differences = Json::array();
    Json first = nullptr;
    std::size_t all_differences{};
    for (std::size_t i = 0; i < steps; ++i) {
        if (free_sets[i] == source_sets[i]) {
            continue;
        }
        ++all_differences;
        if (i + 1 == steps) {
            continue;
        }
        if (first.is_null()) {
            first = i + 1;
        }
        std::size_t free_only{}, source_only{};
        for (const auto& value : free_sets[i]) {
            if (!source_sets[i].contains(value)) {
                ++free_only;
            }
        }
        for (const auto& value : source_sets[i]) {
            if (!free_sets[i].contains(value)) {
                ++source_only;
            }
        }
        differences.push_back({{"step", i + 1},
                               {"free_size", free_sets[i].size()},
                               {"conditioned_size", source_sets[i].size()},
                               {"free_only_count", free_only},
                               {"conditioned_only_count", source_only},
                               {"free_set_sha256", hash_text(Json(free_sets[i]).dump())},
                               {"conditioned_set_sha256", hash_text(Json(source_sets[i]).dump())}});
    }
    require(natural(outcome.at("partial_search_differences")) == all_differences,
            "Legacy aggregate differs from all actual retained sets");
    if (!enabled) {
        require(free_sets == source_sets && novel.empty(),
                "Disabled context is not exact free copy");
    }
    Json choices = Json::object();
    for (const auto& role :
         {"reference_free", "final_rerank_winner", "final_rerank", "context_winner", "selected"}) {
        if (!enabled &&
            (std::string(role) == "context_winner" || std::string(role) == "final_rerank_winner")) {
            choices[role] = {{"applicable", false},
                             {"sequence", outcome.at(role).at("sequence")},
                             {"absent_same_frame_H", nullptr}};
            continue;
        }
        const auto center = dna(outcome.at(role).at("sequence"));
        require(union_seen.contains(center), "Actual proposed/accepted choice absent U");
        choices[role] = {{"applicable", true},
                         {"sequence", center},
                         {"absent_same_frame_H", !h.contains(center)}};
    }
    require(h.contains(dna(outcome.at("reference_free").at("sequence"))) &&
                    h.contains(dna(outcome.at("final_rerank").at("sequence"))) &&
                    (!enabled || h.contains(dna(outcome.at("final_rerank_winner").at("sequence")))),
            "Current escape/final-rerank choice leaves same-frame H");
    return {{"schema", "targeting-mechanism-case/1"},
            {"complete", true},
            {"compiled_observer_source_manifest_sha256", TARGETING_SOURCE_CUT_SHA256},
            {"query_index", request.at("query_index")},
            {"native_result", request.at("native_result")},
            {"validated_case", request.at("validated_case")},
            {"trace_descriptor", request.at("trace_descriptor")},
            {"novelty_baseline", "same-frame current escape finalists plus native H"},
            {"H", h},
            {"candidate_origins", origins},
            {"conditioned_only_strings", novel},
            {"projected_graph_panel_membership", panel_membership},
            {"projected_graph_panel_input_rows",
             request.at("projected_graph_panel_strings").size()},
            {"projected_graph_panel_unique_strings", panel.size()},
            {"actual_decoder_context_strings", supplied},
            {"actual_decoder_context_input_rows",
             request.at("actual_decoder_context_strings").size()},
            {"graph_panel_membership_is_not_a_candidate_origin", true},
            {"direct_graph_panel_candidate_insertion_in_original_decoder", false},
            {"conditioned_only_candidate_count", novel.size()},
            {"choices", choices},
            {"proposed_novel_winner",
             enabled && !h.contains(dna(outcome.at("context_winner").at("sequence")))},
            {"accepted_novel_winner", !h.contains(dna(outcome.at("selected").at("sequence")))},
            {"nonterminal_steps", steps - 1},
            {"nonterminal_changed_steps", differences.size()},
            {"first_nonterminal_changed_step", first},
            {"nonterminal_differences", differences},
            {"terminal_step_validated_and_excluded", true},
            {"all_step_differences", all_differences},
            {"selected_differs_from_final_rerank",
             outcome.at("selected").at("sequence") != outcome.at("final_rerank").at("sequence")},
            {"context_availability", request.at("context_availability")},
            {"context_exclusion", request.at("context_exclusion")},
            {"context_enabled", enabled},
            {"gate", outcome.at("gate")},
            {"final_rerank_gate", outcome.at("final_rerank_gate")},
            {"reference_free_pruned", free_search.at("pruned")},
            {"conditioned_pruned", source_search.at("pruned")},
            {"reference_free_center_bound_reached", free_search.at("center_bound_reached")},
            {"conditioned_center_bound_reached", source_search.at("center_bound_reached")},
            {"reference_free_abstained", outcome.at("reference_free_abstained")},
            {"final_rerank_abstained", outcome.at("final_rerank_abstained")},
            {"selected_abstained", outcome.at("abstained")},
            {"reference_free_finalists", free_finalists.size()},
            {"conditioned_finalists", source_finalists.size()},
            {"source_format", "guarded-phase-trace/2"},
            {"actual_trace_JSON_centers_and_work_census_equal", true},
            {"frozen_policy",
             {{"beam", 128},
              {"min_center", 0},
              {"max_center", 108},
              {"weight", 0.5},
              {"deficit", 0.5},
              {"margin", 0.5}}},
            {"scoring_or_policy_recomputed", false},
            {"decoder_replayed", false},
            {"truth_input", false},
            {"global_optimum_claim", false},
            {"full_wrong_context_arm_available", false},
            {"biological_promotion", false}};
}
}
