#include "context_policy/policy.h"
#include "context_policy/protocol.h"
#include "fixtures.h"

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>

namespace cp = context_policy;
namespace {
void check(bool value, const char *message) {
    if (!value) {
        throw std::runtime_error(message);
    }
}
void rejects(const std::function<void()> &action) {
    bool rejected = false;
    try {
        action();
    } catch (const std::invalid_argument &) {
        rejected = true;
    }
    check(rejected, "expected invalid input rejection");
}
cp::Batch base() {
    return {"AAAA",
            "IIII",
            "free",
            "free",
            {{"L0", 1.0}},
            {{"native", "AAAA", -2.0, 4.0, {"L0"}, {}},
             {"free", "AAAC", 0.0, 4.0, {"L0"}, {}},
             {"ref", "AAAT", -0.25, 0.0, {"L0"}, {}}}};
}
void separation() {
    const auto batch = base();
    const auto disabled = cp::decide(batch, {cp::Mode::disabled, 0.5, 0.5, 0.0});
    check(disabled.sequence == "AAAA" && disabled.quality == "IIII", "disabled identity");
    const auto none = cp::decide(batch, {cp::Mode::prior_none, 0.5, 0.5, 0.0});
    check(none.selected_candidate_id == "free" && none.quality == "!!!!", "prior none edits");
    auto stale = batch;
    stale.union_nn_candidate_id = "native";
    rejects([&] { static_cast<void>(cp::decide(stale, {})); });
    auto distinct = batch;
    distinct.candidates.back().neural_log_likelihood = 0.25;
    distinct.union_nn_candidate_id = "ref";
    distinct.locations.clear();
    for (auto &item : distinct.candidates) {
        item.context_cost = 0.0;
        item.location_ids.clear();
    }
    check(cp::decide(distinct, {}).selected_candidate_id == "free", "empty context genuine escape");
    check(cp::decide(distinct, {cp::Mode::prior_none, 0.5, 0.5, 0.0}).selected_candidate_id ==
              "ref",
          "union neural diagnostic distinct from genuine escape");
}
void runner_up() {
    auto batch = base();
    batch.candidates.back().neural_log_likelihood = -0.75;
    batch.candidates.push_back({"runner", "AAAG", -0.25, 2.0, {"L0"}, {}});
    check(cp::decide(batch, {}).selected_candidate_id == "runner", "eligible runner up");
    check(cp::decide(batch, {cp::Mode::fixed, 0.5, 0.5, 0.5}).selected_candidate_id == "free",
          "fixed top candidate fallback unchanged");
    batch.candidates.back().eligibility_reasons = {"producer_rejected"};
    check(cp::decide(batch, {}).selected_candidate_id == "free",
          "no eligible contextual candidate");
}
void fixed() {
    auto batch = base();
    batch.candidates[1].context_cost = 1.0;
    check(cp::decide(batch, {cp::Mode::fixed, 0.5, 0.5, 0.5}).selected_candidate_id == "free",
          "old one edit lower neural cannot clear margin");
    check(cp::decide(batch, {}).selected_candidate_id == "ref", "adaptive predeclared zero margin");
    rejects([&] { static_cast<void>(cp::decide(batch, {cp::Mode::fixed, 0.5, 0.5, 0.0})); });
}
void monotonic() {
    auto batch = base();
    double previous = 0.0;
    for (int step = 0; step <= 100; ++step) {
        batch.locations[0].support = static_cast<double>(step) / 100.0;
        const auto result = cp::decide(batch, {});
        check(result.context_weight >= previous && result.context_weight <= 0.5, "monotone weight");
        previous = result.context_weight;
    }
    batch.locations[0].support = 0.0;
    check(cp::decide(batch, {}).selected_candidate_id == "free", "zero trust escape");
    batch.locations[0].support = 1.0;
    batch.candidates.back().neural_log_likelihood = -0.500001;
    check(cp::decide(batch, {}).selected_candidate_id == "free", "strong signal escape");
    batch.candidates.back().neural_log_likelihood = -0.5;
    check(cp::decide(batch, {}).selected_candidate_id == "ref", "inclusive neural budget");
}
void novel() {
    for (const auto &sequence : {"AAAC", "AAAAC", "AAC"}) {
        auto batch = base();
        batch.candidates[1].sequence = sequence;
        batch.candidates.back().neural_log_likelihood = -0.75;
        check(cp::decide(batch, {}).sequence == sequence,
              "private SNV INS DEL strong signal survival");
    }
}
void wrong_inside_budget() {
    check(cp::decide(base(), {}).selected_candidate_id == "ref",
          "known limitation: wrong confident reference wins inside budget");
}
void ties() {
    auto batch = base();
    batch.candidates[2].neural_log_likelihood = 0.0;
    batch.candidates[2].context_cost = 4.0;
    check(cp::decide(batch, {}).selected_candidate_id == "free", "lexical exact tie");
    std::reverse(batch.candidates.begin(), batch.candidates.end());
    check(cp::decide(batch, {}).selected_candidate_id == "free", "permuted exact tie");
    batch.candidates[2].neural_log_likelihood = 0.0;
    batch.union_nn_candidate_id = "native";
    check(cp::decide(batch, {cp::Mode::prior_none, 0.5, 0.5, 0.0}).selected_candidate_id ==
              "native",
          "native wins neural tie");
}
void empty_context() {
    auto batch = base();
    batch.locations.clear();
    for (auto &candidate : batch.candidates) {
        candidate.location_ids.clear();
        candidate.context_cost = 0.0;
    }
    check(cp::decide(batch, {}).selected_candidate_id == "free", "empty context escapes");
}
void numerical_rejections() {
    auto batch = base();
    batch.candidates.back().neural_log_likelihood = std::numeric_limits<double>::quiet_NaN();
    rejects([&] { static_cast<void>(cp::decide(batch, {})); });
    batch = base();
    batch.candidates.back().context_cost = std::numeric_limits<double>::infinity();
    rejects([&] { static_cast<void>(cp::decide(batch, {})); });
    batch = base();
    batch.locations[0].support = -0.1;
    rejects([&] { static_cast<void>(cp::decide(batch, {})); });
    batch = base();
    batch.candidates.clear();
    rejects([&] { static_cast<void>(cp::decide(batch, {})); });
    batch = base();
    batch.candidates.back().id = "free";
    rejects([&] { static_cast<void>(cp::decide(batch, {})); });
    batch = base();
    batch.candidates.back().location_ids = {"foreign"};
    rejects([&] { static_cast<void>(cp::decide(batch, {})); });
}
// Independent exhaustive map oracle. Integer quarter-units avoid boundary-rounding ambiguity.
// It does not call production ranking, eligibility, or objective helpers.
void map_oracle() {
    std::size_t checked = 0;
    for (int support : {0, 1, 2}) {
        for (int signal : {-4, -3, -2, -1, 0}) {
            for (int cost : {0, 1, 2, 3, 4}) {
                for (bool blocked : {false, true}) {
                    auto batch = base();
                    batch.locations[0].support = static_cast<double>(support) / 2.0;
                    batch.candidates[2].neural_log_likelihood = static_cast<double>(signal) / 4.0;
                    batch.candidates[2].context_cost = static_cast<double>(cost);
                    if (blocked) {
                        batch.candidates[2].eligibility_reasons = {"blocked"};
                    }
                    std::map<std::string, cp::Candidate> candidates;
                    for (const auto &item : batch.candidates) {
                        candidates.emplace(item.id, item);
                    }
                    const double weight = static_cast<double>(support) / 4.0;
                    const double baseline = -weight * 4.0;
                    std::string expected = "free";
                    double best_score = baseline;
                    for (const auto &[id, item] : candidates) {
                        const double score =
                            item.neural_log_likelihood - weight * item.context_cost;
                        const bool eligible = item.eligibility_reasons.empty() &&
                                              item.neural_log_likelihood >= -0.5 &&
                                              score > baseline && weight > 0.0;
                        if (eligible && (score > best_score ||
                                         (score == best_score &&
                                          item.sequence < candidates.at(expected).sequence))) {
                            best_score = score;
                            expected = id;
                        }
                    }
                    const auto decision = cp::decide(batch, {});
                    check(decision.selected_candidate_id == expected, "independent map decision");
                    for (const auto &assessment : decision.assessments) {
                        const auto &item = candidates.at(assessment.candidate_id);
                        check(assessment.objective ==
                                  item.neural_log_likelihood - weight * item.context_cost,
                              "independent map objective");
                        const bool budget =
                            std::find(assessment.reasons.begin(), assessment.reasons.end(),
                                      "neural_budget_exceeded") != assessment.reasons.end();
                        check(budget == (item.neural_log_likelihood < -0.5),
                              "independent map budget");
                        std::vector<std::string> reasons = item.eligibility_reasons;
                        if (item.neural_log_likelihood < -0.5) {
                            reasons.push_back("neural_budget_exceeded");
                        }
                        const auto score = item.neural_log_likelihood - weight * item.context_cost;
                        if (score < baseline || (item.id != "free" && score <= baseline)) {
                            reasons.push_back("objective_margin_not_met");
                        }
                        std::sort(reasons.begin(), reasons.end());
                        check(assessment.reasons == reasons, "independent complete eligibility");
                    }
                    std::reverse(batch.candidates.begin(), batch.candidates.end());
                    check(cp::decide(batch, {}).selected_candidate_id == expected,
                          "map permutation");
                    ++checked;
                }
            }
        }
    }
    check(checked == 150, "oracle census");
}
void protocol_controls() {
    auto request = cp::test::fixture();
    check(cp::test::run(request).at("selected_candidate_id") == "ref", "protocol producer fixture");
    std::reverse(request["batch"]["candidates"].begin(), request["batch"]["candidates"].end());
    cp::test::reseal(request);
    check(cp::test::run(request).at("selected_candidate_id") == "ref",
          "candidate order invariance");
    request["batch"]["candidates"][0]["context_cost"] = 3.0;
    rejects([&] { static_cast<void>(cp::test::run(request)); });
    request = cp::test::fixture();
    request["batch"]["binding"]["previous_state_sha256"] = std::string(64, 'b');
    cp::test::reseal(request);
    rejects([&] { static_cast<void>(cp::test::run(request)); });
    request = cp::test::fixture();
    request["batch"]["binding"]["availability"]["row_end"] = 9;
    cp::test::reseal(request);
    request["expected_binding"] = request["batch"]["binding"];
    rejects([&] { static_cast<void>(cp::test::run(request)); });
    request = cp::test::fixture();
    request["batch"]["locations"][0]["query_end"] = 5;
    cp::test::reseal(request);
    rejects([&] { static_cast<void>(cp::test::run(request)); });
    request = cp::test::fixture();
    request["batch"]["schema"] = "feedback-next/999";
    cp::test::reseal(request);
    rejects([&] { static_cast<void>(cp::test::run(request)); });
    request = cp::test::fixture();
    request["batch"]["candidates"][0].erase("edits");
    cp::test::reseal(request);
    rejects([&] { static_cast<void>(cp::test::run(request)); });
    rejects([] { static_cast<void>(cp::parse("{\"a\":1,\"a\":2}")); });
}
void source_guard() {
    const auto path = std::filesystem::current_path() / "source-guard-fixture.txt";
    check(!std::filesystem::exists(path), "source guard fixture is not fresh");
    {
        std::ofstream file(path);
        file << "original";
    }
    cp::verify_source_file(path.string(), 8, cp::digest("original"));
    {
        std::ofstream file(path);
        file << "mutated!";
    }
    rejects([&] { cp::verify_source_file(path.string(), 8, cp::digest("original")); });
    std::filesystem::remove(path);
}
}
int main(int argc, char **argv) {
    const std::map<std::string, std::function<void()>> tests{
        {"separation", separation},
        {"runner_up", runner_up},
        {"fixed", fixed},
        {"monotonic", monotonic},
        {"novel", novel},
        {"wrong_inside_budget", wrong_inside_budget},
        {"ties", ties},
        {"empty_context", empty_context},
        {"numerical_rejections", numerical_rejections},
        {"map_oracle", map_oracle},
        {"protocol", protocol_controls},
        {"source_guard", source_guard}};
    try {
        check(argc == 2 && tests.contains(argv[1]), "unknown test name");
        tests.at(argv[1])();
        std::cout << argv[1] << " passed\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
