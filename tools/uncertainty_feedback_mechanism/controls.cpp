#include "mechanism.h"

#include <functional>
#include <iostream>

namespace {
using namespace targeting_mechanism;
void integer(std::string& raw, std::uint64_t value) {
    for (unsigned shift = 0; shift < 64; shift += 8) {
        raw.push_back(static_cast<char>((value >> shift) & 255U));
    }
}
void real(std::string& raw, double value) { integer(raw, std::bit_cast<std::uint64_t>(value)); }
void vector(std::string& raw, std::size_t count) {
    integer(raw, count);
    for (std::size_t i = 0; i < count; ++i) {
        real(raw, 0.0);
    }
}
struct Fixture {
    Json native;
    Json request;
    std::string raw;
};
Fixture fixture(bool enabled = true,
                bool accept = true,
                bool terminal_only = false,
                bool potential_only = false) {
    const bool changed = enabled && !potential_only;
    const Json original = {
            {"path", "/immutable/phase-trace.bin"}, {"size", 1}, {"sha256", "fixture"}};
    Json outcome = {{"schema", "guarded-outcome/2"},
                    {"context_enabled", enabled},
                    {"native", {{"sequence", "A"}}},
                    {"reference_free", {{"sequence", "A"}}},
                    {"final_rerank_winner", {{"sequence", enabled ? "A" : ""}}},
                    {"context_winner", {{"sequence", enabled ? (changed ? "C" : "A") : ""}}},
                    {"final_rerank", {{"sequence", "A"}}},
                    {"selected", {{"sequence", changed && accept ? "C" : "A"}}},
                    {"gate", enabled && accept ? "context_selected" : "objective_margin_fallback"},
                    {"final_rerank_gate", "objective_margin_fallback"},
                    {"reference_free_abstained", false},
                    {"final_rerank_abstained", false},
                    {"abstained", false},
                    {"partial_search_differences", changed ? (terminal_only ? 1 : 2) : 0}};
    Json candidates = Json::array({{{"choice", {{"sequence", "A"}}},
                                    {"native", true},
                                    {"free_finalist", true},
                                    {"conditioned_finalist", !changed}}});
    if (changed) {
        candidates.push_back({{"choice", {{"sequence", "C"}}},
                              {"native", false},
                              {"free_finalist", false},
                              {"conditioned_finalist", true}});
    }
    outcome["candidates"] = candidates;
    std::string raw = "guarded-phase-trace/2\n";
    for (unsigned beam = 0; beam < 2; ++beam) {
        integer(raw, 3);
        Json trace = Json::array();
        for (std::size_t step = 1; step <= 3; ++step) {
            const std::string center =
                    changed && beam == 1 && step >= (terminal_only ? 3U : 2U) ? "C" : "A";
            integer(raw, step);
            integer(raw, 1);
            integer(raw, 1);
            integer(raw, 0);
            vector(raw, 1);
            integer(raw, 1);
            integer(raw, center.size());
            raw += center;
            real(raw, 0.0);
            vector(raw, 4);
            real(raw, enabled && beam == 1 ? -1.0 : 0.0);
            real(raw, 0.0);
            real(raw, 0.0);
            trace.push_back({{"timestep", step},
                             {"generated", 1},
                             {"merged", 1},
                             {"pruned", 0},
                             {"retained_centers", Json::array({center})}});
        }
        const std::string finalist = changed && beam == 1 ? "C" : "A";
        outcome[beam == 0 ? "reference_free_escape" : "conditioned_search"] = {
                {"trace", trace},
                {"pruned", false},
                {"center_bound_reached", false},
                {"finalists", Json::array({{{"center", finalist}}})}};
    }
    return {{{"schema", "context-decoder-guarded-frame/2"},
             {"phase_trace", original},
             {"retained_rust_scalar_bit_comparisons", 1},
             {"binding",
              {{"expanded_t_start", "0"},
               {"expanded_t_end", "3"},
               {"left_guard", "C"},
               {"right_guard", "ACGT"},
               {"native_center", "A"}}},
             {"outcome", outcome}},
            {{"query_index", 0},
             {"native_result", Json::object()},
             {"validated_case", Json::object()},
             {"trace_descriptor", {{"storage", {{"original", original}}}}},
             {"timesteps", 3},
             {"context_enabled", enabled},
             {"context_availability", enabled ? "usable" : "missing"},
             {"projected_graph_panel_strings", Json::array({"A", "C", "G"})},
             {"actual_decoder_context_strings", enabled ? Json::array({"A", "G"}) : Json::array()},
             {"context_exclusion", enabled ? "" : "native_reference_guard_mismatch"}},
            raw};
}
Json run(const Fixture& value) { return observe(value.native, value.request, value.raw); }
std::vector<std::string> passed;
void check(bool condition, const std::string& name) {
    require(condition, "Control failed: " + name);
    passed.push_back(name);
}
void rejects(const std::string& name, const std::function<void(Fixture&)>& change) {
    auto value = fixture();
    change(value);
    try {
        static_cast<void>(run(value));
    } catch (const std::exception&) {
        passed.push_back(name);
        return;
    }
    throw std::runtime_error("Rejection control accepted: " + name);
}
void rank_case(const std::string& name,
               const std::vector<std::string>& names,
               const std::vector<double>& ranks,
               bool reject) {
    std::string raw = "guarded-phase-trace/2\n";
    integer(raw, 1);
    integer(raw, 1);
    integer(raw, names.size());
    integer(raw, names.size());
    integer(raw, 0);
    vector(raw, 1);
    integer(raw, names.size());
    for (std::size_t i = 0; i < names.size(); ++i) {
        integer(raw, names[i].size());
        raw += names[i];
        real(raw, -std::numeric_limits<double>::infinity());
        vector(raw, 4);
        real(raw, 0.0);
        real(raw, 0.0);
        real(raw, ranks.at(i));
    }
    const Json saved = {{"trace", Json::array({{{"timestep", 1},
                                                {"generated", names.size()},
                                                {"merged", names.size()},
                                                {"pruned", 0},
                                                {"retained_centers", names}}})},
                        {"pruned", false},
                        {"finalists", Json::array()}};
    bool failed = false;
    try {
        TraceReader reader(raw);
        static_cast<void>(reader.search(saved, 1, 1, 4));
        reader.end();
    } catch (const std::exception&) {
        failed = true;
    }
    check(failed == reject, name);
}
void controls() {
    const auto positive = run(fixture());
    check(positive.at("conditioned_only_candidate_count") == 1 &&
                  positive.at("proposed_novel_winner") == true &&
                  positive.at("accepted_novel_winner") == true &&
                  positive.at("projected_graph_panel_membership")[0].at(
                          "present_in_same_frame_H") == true &&
                  positive.at("projected_graph_panel_membership")[2].at("present_in_actual_U") ==
                          false &&
                  positive.at("graph_panel_membership_is_not_a_candidate_origin") == true,
          "same-frame-novel-origin-proposed-and-accepted");
    check(positive.at("first_nonterminal_changed_step") == 2 &&
                  positive.at("nonterminal_changed_steps") == 1 &&
                  positive.at("all_step_differences") == 2,
          "first-nonterminal-set-difference-and-terminal-exclusion");
    const auto rejected = run(fixture(true, false));
    check(rejected.at("proposed_novel_winner") == true &&
                  rejected.at("accepted_novel_winner") == false,
          "proposed-novel-winner-separated-from-accepted");
    const auto terminal = run(fixture(true, false, true));
    check(terminal.at("first_nonterminal_changed_step").is_null() &&
                  terminal.at("nonterminal_changed_steps") == 0 &&
                  terminal.at("all_step_differences") == 1,
          "terminal-only-difference-does-not-count");
    const auto disabled = run(fixture(false));
    check(disabled.at("conditioned_only_candidate_count") == 0 &&
                  disabled.at("nonterminal_changed_steps") == 0 &&
                  disabled.at("choices").at("context_winner").at("applicable") == false,
          "missing-context-genuine-free-copy-proposal-not-applicable");
    const auto potential = run(fixture(true, true, false, true));
    check(potential.at("nonterminal_changed_steps") == 0 &&
                  potential.at("conditioned_only_candidate_count") == 0,
          "potential-only-differences-do-not-count-as-search-changes");
    auto repeated = fixture();
    repeated.request["projected_graph_panel_strings"].push_back("A");
    repeated.request["actual_decoder_context_strings"].push_back("A");
    const auto repeated_result = run(repeated);
    check(repeated_result.at("projected_graph_panel_input_rows") == 4 &&
                  repeated_result.at("projected_graph_panel_unique_strings") == 3 &&
                  repeated_result.at("conditioned_only_candidate_count") == 1,
          "repeated-context-source-strings-preserve-set-membership-and-row-counts");
    auto native = fixture();
    native.native["outcome"]["native"]["sequence"] = "G";
    native.native["binding"]["native_center"] = "G";
    native.native["outcome"]["candidates"][0]["native"] = false;
    native.native["outcome"]["candidates"].push_back({{"choice", {{"sequence", "G"}}},
                                                      {"native", true},
                                                      {"free_finalist", false},
                                                      {"conditioned_finalist", false}});
    check(run(native).at("H") == Json(Strings{"A", "G"}),
          "native-remains-in-H-without-free-origin");
    auto bound = fixture();
    bound.native["outcome"]["conditioned_search"]["center_bound_reached"] = true;
    bound.native["outcome"]["abstained"] = true;
    bound.native["outcome"]["selected"]["sequence"] = "A";
    bound.native["outcome"]["gate"] = "conditioned_center_bound_abstain";
    check(run(bound).at("conditioned_center_bound_reached") == true &&
                  run(bound).at("accepted_novel_winner") == false,
          "bound-and-abstention-preserved");
    rejects("truncated-trace-rejected", [](auto& value) { value.raw.pop_back(); });
    rejects("trailing-trace-rejected", [](auto& value) { value.raw += 'x'; });
    rejects("sample-format-rejected",
            [](auto& value) { value.raw = "sample-guarded-exact-trace/1\n" + value.raw; });
    rejects("wrong-expanded-steps-rejected", [](auto& value) { value.request["timesteps"] = 4; });
    rejects("wrong-phase-vector-geometry-rejected",
            [](auto& value) { value.native["binding"]["left_guard"] = "CC"; });
    rejects("actual-center-JSON-disagreement-rejected", [](auto& value) {
        value.native["outcome"]["conditioned_search"]["trace"][1]["retained_centers"][0] = "G";
    });
    rejects("work-census-disagreement-rejected", [](auto& value) {
        value.native["outcome"]["conditioned_search"]["trace"][1]["generated"] = 2;
    });
    rejects("pruning-flag-disagreement-rejected",
            [](auto& value) { value.native["outcome"]["conditioned_search"]["pruned"] = true; });
    rejects("finalist-absent-terminal-rejected", [](auto& value) {
        value.native["outcome"]["conditioned_search"]["finalists"][0]["center"] = "G";
    });
    rejects("origin-flag-disagreement-rejected",
            [](auto& value) { value.native["outcome"]["candidates"][1]["free_finalist"] = true; });
    rejects("candidate-omission-rejected",
            [](auto& value) { value.native["outcome"]["candidates"].erase(1); });
    rejects("duplicate-candidate-rejected", [](auto& value) {
        value.native["outcome"]["candidates"].push_back(value.native["outcome"]["candidates"][0]);
    });
    rejects("winner-absent-U-rejected",
            [](auto& value) { value.native["outcome"]["context_winner"]["sequence"] = "G"; });
    rejects("wrong-availability-rejected",
            [](auto& value) { value.request["context_availability"] = "missing"; });
    rejects("legacy-aggregate-disagreement-rejected",
            [](auto& value) { value.native["outcome"]["partial_search_differences"] = 0; });
    rejects("missing-original-scalar-rejected",
            [](auto& value) { value.native["retained_rust_scalar_bit_comparisons"] = 0; });
    rejects("changed-original-trace-Pin-rejected",
            [](auto& value) { value.native["phase_trace"]["sha256"] = "changed"; });
    rank_case("lexical-rank-tie-preserved", {"A", "C"}, {1.0, 1.0}, false);
    rank_case("wrong-lexical-rank-tie-rejected", {"C", "A"}, {1.0, 1.0}, true);
    rank_case("ascending-rank-order-rejected", {"A", "C"}, {0.0, 1.0}, true);
    rank_case("nonfinite-rank-rejected", {"A"}, {std::numeric_limits<double>::quiet_NaN()}, true);
    rank_case("center-symbol-bound-rejected", {std::string(109, 'A')}, {1.0}, true);
    rank_case("duplicate-retained-center-rejected", {"A", "A"}, {1.0, 1.0}, true);
    check(hash_text("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
          "set-hash-known-answer");
}
}
int main() {
    try {
        controls();
        std::cout << targeting_mechanism::Json{{"schema", "targeting-mechanism-controls/1"},
                                               {"compiled_observer_source_manifest_sha256",
                                                TARGETING_SOURCE_CUT_SHA256},
                                               {"passed", passed},
                                               {"count", passed.size()},
                                               {"skips", 0}}
                             .dump()
                  << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
