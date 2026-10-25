#include "context_model/model.h"
#include "context_model/runtime.h"
#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <numeric>
#include <sstream>
#include <stdexcept>

namespace context_model {
namespace {
struct Checks {
    std::size_t assertions{}, strings{}, histories{}, joint_pairs{};
    void expect(bool condition, const std::string &message) {
        ++assertions;
        context_study::require(condition, "model control: " + message);
    }
    void close(double actual, long double expected, const std::string &message) {
        expect(std::isfinite(actual) && std::isfinite(expected) &&
                   std::abs(static_cast<long double>(actual) - expected) <= 1e-10L,
               message);
    }
    void rejects(const std::function<void()> &action, const std::string &message) {
        bool rejected = false;
        try {
            action();
        } catch (const std::invalid_argument &) {
            rejected = true;
        }
        expect(rejected, message);
    }
};
struct History {
    long double mass{};
    std::size_t deletions{};
};
std::vector<std::string> strings(std::size_t maximum) {
    std::vector<std::string> result{""}, level{""};
    for (std::size_t n = 0; n < maximum; ++n) {
        std::vector<std::string> next;
        for (const auto &prefix : level)
            for (const auto base : std::string("ACGT"))
                next.push_back(prefix + base);
        result.insert(result.end(), next.begin(), next.end());
        level = std::move(next);
    }
    return result;
}
std::vector<History> histories(const std::string &source, const std::string &target,
                               const MutationRates &rates) {
    const auto insertion = static_cast<long double>(rates.insertion);
    const auto deletion = static_cast<long double>(rates.deletion);
    const auto substitution = static_cast<long double>(rates.substitution);
    std::vector<History> result;
    std::function<void(std::size_t, std::size_t, long double, std::size_t)> visit;
    visit = [&](std::size_t j, std::size_t n, long double mass, std::size_t deleted) {
        if (j == source.size() && n == target.size())
            result.push_back({mass * (1 - insertion), deleted});
        if (n < target.size())
            visit(j, n + 1, mass * insertion / 4, deleted);
        if (j < source.size()) {
            visit(j + 1, n, mass * (1 - insertion) * deletion, deleted + 1);
            if (n < target.size()) {
                const auto channel = source[j] == target[n] ? 1 - substitution : substitution / 3;
                visit(j + 1, n + 1, mass * (1 - insertion) * (1 - deletion) * channel, deleted);
            }
        }
    };
    visit(0, 0, 1, 0);
    return result;
}
long double sum(const std::vector<History> &values) {
    long double total{};
    for (const auto &value : values)
        total += value.mass;
    return total;
}
long double normalizer(const std::string &source, const ModelPolicy &policy) {
    long double result{};
    for (const auto &target : strings(policy.maximum_center))
        result += sum(histories(source, target, policy.rates));
    return result;
}
context_study::CandidateCase fixture(std::string native = "C") {
    context_study::CandidateCase input;
    input.id = "fixture/0";
    input.domain = "ordinary";
    input.parent = "parent0";
    input.contig = "chr1";
    input.ancestry = std::string(64, 'a');
    input.geometry = std::string(64, 'b');
    input.left = "A";
    input.right = "C";
    input.native = std::move(native);
    input.availability = "usable";
    input.paths = {"A"};
    input.reference_paths = input.paths;
    input.candidates.emplace(
        input.native, context_study::Candidate{input.native, 3, context_study::GuardedLogMass{0}});
    if (input.native != "A")
        input.candidates.emplace(
            "A", context_study::Candidate{"A", 2, context_study::GuardedLogMass{-0.1}});
    input.saved = context_study::replay(input);
    return input;
}
void probability_controls(Checks &check) {
    const ModelPolicy policy{4, {0.2, 0.3, 0.1}, 0.5};
    const auto context =
        ContextDistribution::weighted({{"AA", 0.3}, {"C", 0.7}}, std::string(64, 'a'));
    const auto targets = strings(policy.maximum_center);
    long double graph_sum{}, background_sum{}, mixture_sum{};
    for (const auto &source : {std::string(""), std::string("AA"), std::string("C")}) {
        const auto z = normalizer(source, policy);
        check.close(log_length_normalizer(source.size(), policy), std::log(z),
                    "length normalizer matches enumeration");
        long double conditional_sum{};
        for (const auto &target : targets) {
            const auto exact = histories(source, target, policy.rates);
            ++check.strings;
            check.histories += exact.size();
            check.close(log_sequence_mass(source, target, policy.rates), std::log(sum(exact)),
                        "all mutation histories match log DP");
            conditional_sum +=
                std::exp(static_cast<long double>(log_sequence_mass(source, target, policy.rates)) -
                         static_cast<long double>(log_length_normalizer(source.size(), policy)));
        }
        check.close(static_cast<double>(conditional_sum), 1, "conditioned source mass sums to one");
        check.expect(z < 1 && z > 0, "finite support has positive omitted raw mass");
    }
    for (const auto &target : targets) {
        const auto value = context_mass(target, context, policy);
        graph_sum += std::exp(static_cast<long double>(value.graph));
        background_sum += std::exp(static_cast<long double>(value.background));
        mixture_sum += std::exp(static_cast<long double>(value.mixture));
        check.expect(value.log_ratio >= std::log(policy.novel_mass) - 1e-12,
                     "novel component gives full support and log-ratio floor");
    }
    check.close(static_cast<double>(graph_sum), 1, "graph mixture is normalized");
    check.close(static_cast<double>(background_sum), 1, "background is normalized");
    check.close(static_cast<double>(mixture_sum), 1, "novel mixture is normalized");
    const auto repeated = histories("AA", "A", policy.rates);
    const auto largest =
        std::max_element(repeated.begin(), repeated.end(),
                         [](const auto &a, const auto &b) { return a.mass < b.mass; });
    check.expect(largest != repeated.end() && sum(repeated) > largest->mass * 1.5L,
                 "best-history mutation shortcut fails repeated-base deletion");
    const ModelPolicy zero_length{0, policy.rates, 0.5};
    check.close(context_mass("", context, zero_length).mixture, 0,
                "N zero supports only the empty string");
    check.expect(normalizer("AA", zero_length) < 0.2L,
                 "omitted length normalizer would fail unit total mass");
    auto disabled = policy;
    disabled.novel_mass = 1;
    for (const auto &target : targets)
        check.expect(context_mass(target, context, disabled).log_ratio == 0,
                     "epsilon one has exact zero context feature");
}
void alias_controls(Checks &check) {
    const auto provenance = std::string(64, 'a');
    const auto uniform = ContextDistribution::uniform({"AA", "C"}, provenance);
    const auto duplicate = ContextDistribution::uniform({"C", "AA", "C", "AA"}, provenance);
    const auto weighted = ContextDistribution::weighted({{"AA", 0.3}, {"C", 0.7}}, provenance);
    const auto split =
        ContextDistribution::weighted({{"C", 0.2}, {"AA", 0.3}, {"C", 0.5}}, provenance);
    const auto policy = fixed_policies().front();
    for (const auto &target : strings(2)) {
        const auto base = context_mass(target, uniform, policy).mixture;
        check.expect(base == context_mass(target, duplicate, policy).mixture,
                     "duplicate uniform path records cannot add votes");
        check.close(context_mass(target, weighted, policy).mixture,
                    context_mass(target, split, policy).mixture,
                    "authoritative mass splitting is invariant");
    }
    const auto naive = ContextDistribution::weighted({{"AA", 1.0 / 3}, {"C", 2.0 / 3}}, provenance);
    check.expect(std::abs(context_mass("C", naive, policy).mixture -
                          context_mass("C", uniform, policy).mixture) > 0.1,
                 "naive vote-per-record mutation is detected");
    check.rejects([&] { static_cast<void>(ContextDistribution::uniform({}, provenance)); },
                  "empty context rejects");
    check.rejects([&] { static_cast<void>(ContextDistribution::uniform({"A"}, "")); },
                  "missing provenance rejects");
    for (const auto mass : {-1.0, 0.0, std::numeric_limits<double>::infinity(),
                            std::numeric_limits<double>::quiet_NaN()})
        check.rejects(
            [&] { static_cast<void>(ContextDistribution::weighted({{"A", mass}}, provenance)); },
            "invalid component mass rejects");
    check.rejects(
        [&] { static_cast<void>(ContextDistribution::weighted({{"A", 0.5}}, provenance)); },
        "unnormalized authoritative masses reject");
    check.rejects(
        [&] {
            static_cast<void>(ContextDistribution::weighted(
                {{"A", 0.5, std::string(64, 'b')}, {"C", 0.5, std::string(64, 'b')}}, provenance));
        },
        "conflicting aliases of one biological component reject");
}
void decision_controls(Checks &check) {
    auto input = fixture();
    const auto policy = fixed_policies().front();
    const ContextInput context{ContextDistribution::uniform({"A"}, input.ancestry), "available",
                               input.id};
    const auto corrected = score_model(input, context, policy);
    check.expect(corrected.accepted.sequence == "A" && corrected.gate == "context_selected",
                 "positive novel mass does not guarantee private ALT protection");
    const auto preservation = ContextDistribution::uniform({"AC"}, input.ancestry);
    for (const auto &target : {"AT", "ACC", "A", "AAA"}) {
        const auto mass = context_mass(target, preservation, policy);
        check.expect(std::isfinite(mass.mixture) && mass.log_ratio >= std::log(0.5) - 1e-12,
                     "off-panel SNV indel and run-length strings retain positive support");
    }
    input.candidates.at("A").log_mass->value = 0.2;
    const auto none = score_model(input, {std::nullopt, "disabled", "."}, policy);
    check.expect(none.accepted.sequence == "A" && none.baseline.sequence == "A" &&
                     none.gate == "reference_free_fallback",
                 "None preserves matched signal winner and can differ from native");
    check.expect(none.accepted.sequence ==
                     context_study::replay(input).at("reference_free").sequence,
                 "None agrees with historical reference-free winner");
    for (const auto &value : none.candidates)
        check.expect(value.objective == value.signal && value.context.log_ratio == 0,
                     "None signal bytes and feature stay exact");
    input.escape_capped = true;
    const auto capped = score_model(input, context, policy);
    check.expect(capped.accepted.sequence == input.native && capped.baseline.sequence == "A" &&
                     capped.abstained && capped.gate == "center_bound_abstain",
                 "escape cap preserves native fallback");
    input.escape_capped = false;
    input.escape_empty = true;
    check.expect(score_model(input, context, policy).gate == "no_eligible_finalist_abstain",
                 "missing eligible finalists abstain");
    input = fixture("T");
    input.candidates.at("A").log_mass->value = 0;
    check.expect(score_model(input, {std::nullopt, "disabled", "."}, policy).raw.sequence == "T",
                 "native is preferred at an exact tie");
    input.candidates.at("T").log_mass->value = -1;
    input.candidates.emplace("G",
                             context_study::Candidate{"G", 2, context_study::GuardedLogMass{0}});
    check.expect(score_model(input, {std::nullopt, "disabled", "."}, policy).raw.sequence == "A",
                 "non-native tie is lexical");
    auto asymmetric = fixture("AAA");
    asymmetric.candidates.at("A").log_mass->value = 0;
    const ContextInput repeated{ContextDistribution::uniform({"AA"}, input.ancestry), "available",
                                input.id};
    const ModelPolicy different_channel{4, {0.02, 0.5, 0.1}, 0.5};
    check.expect(context_study::distance("AAA", "AA") == context_study::distance("A", "AA") &&
                     score_model(asymmetric, repeated, different_channel).raw.sequence == "A",
                 "marginal mutation channel distinguishes equal minimum edit distances");
    input = fixture();
    input.conditioned_capped = true;
    check.expect(!score_model(input, context, policy).abstained,
                 "primary native-plus-escape arm follows historical final-rerank cap semantics");
    context_study::Packet packet{std::string(64, 'a'), {fixture(), fixture("G"), fixture("T")}};
    for (std::size_t i = 0; i < packet.cases.size(); ++i) {
        packet.cases[i].id = "fixture/" + std::to_string(i);
        packet.cases[i].parent = "parent" + std::to_string(i);
        packet.cases[i].contig = "chr" + std::to_string(i);
    }
    const auto assignments = assign_contexts(packet);
    std::reverse(packet.cases.begin(), packet.cases.end());
    const auto reordered = assign_contexts(packet);
    for (const auto &item : packet.cases) {
        const auto &wrong = assignments.at(item.id).at("wrong");
        check.expect(wrong.distribution && wrong.donor != item.id &&
                         context_digest(wrong) == context_digest(reordered.at(item.id).at("wrong")),
                     "wrong donor is deterministic under input permutation");
        std::vector<std::pair<std::string, double>> expected;
        for (const auto &[sequence, candidate] : item.candidates)
            if ((candidate.origins &
                 (context_study::native_origin | context_study::escape_origin)) != 0)
                expected.emplace_back(sequence, candidate.log_mass->value);
        check.expect(assignments.at(item.id).size() == 4, "all four matched context arms execute");
        for (const auto &[arm, assigned] : assignments.at(item.id)) {
            static_cast<void>(arm);
            std::vector<std::pair<std::string, double>> actual;
            for (const auto &candidate : score_model(item, assigned, policy).candidates)
                actual.emplace_back(candidate.sequence, candidate.signal);
            check.expect(
                actual == expected,
                "each context arm preserves the complete sequence and exact signal census");
        }
    }
    const auto no_donor = assign_contexts({packet.manifest, {packet.cases.front()}});
    check.expect(!no_donor.begin()->second.at("wrong").distribution &&
                     no_donor.begin()->second.at("wrong").reason == "no_eligible_donor",
                 "unavailable wrong context falls back explicitly");
    auto missing = fixture();
    missing.paths.clear();
    missing.reference_paths.clear();
    const auto absent = assign_contexts({packet.manifest, {missing}});
    const auto disabled = score_model(missing, absent.at(missing.id).at("none"), policy);
    for (const auto *arm : {"graph", "reference"}) {
        const auto &assigned = absent.at(missing.id).at(arm);
        const auto fallback = score_model(missing, assigned, policy);
        check.expect(!assigned.distribution && fallback.candidates.size() == 2 &&
                         fallback.accepted.sequence == disabled.accepted.sequence,
                     "missing graph or reference keeps the same pool and disabled decision");
        for (std::size_t i = 0; i < fallback.candidates.size(); ++i)
            check.expect(fallback.candidates[i].sequence == disabled.candidates[i].sequence &&
                             fallback.candidates[i].signal == disabled.candidates[i].signal,
                         "missing context preserves every retained sequence and signal value");
    }
}
struct NeuralPath {
    std::string center;
    long double mass{};
    std::size_t stays{};
};
std::vector<NeuralPath> neural_paths(bool reverse) {
    std::vector<NeuralPath> result;
    const auto left = reverse ? 'G' : 'A', right = reverse ? 'T' : 'C';
    std::function<void(std::size_t, char, std::string, long double, std::size_t)> visit;
    visit = [&](std::size_t t, char state, std::string emitted, long double mass,
                std::size_t stays) {
        if (t == 4) {
            if (emitted.size() >= 2 && emitted.front() == left && emitted.back() == right)
                result.push_back({emitted.substr(1, emitted.size() - 2), mass, stays});
            return;
        }
        visit(t + 1, state, emitted, mass * (0.11L + static_cast<long double>(t) * 0.01L),
              stays + 1);
        for (const auto base : std::string("ACGT")) {
            const auto index = std::string("ACGT").find(base);
            const auto predecessor = std::string("ACGT").find(state);
            const auto weight = 0.13L + static_cast<long double>(index) * 0.023L +
                                static_cast<long double>(predecessor) * 0.007L +
                                static_cast<long double>(t) * 0.003L;
            visit(t + 1, base, emitted + base, mass * weight, stays);
        }
    };
    visit(0, 'A', "", 1, 0);
    return result;
}
long double interleavings(std::size_t stays, std::size_t deletions) {
    long double count = 1;
    for (std::size_t i = 1; i <= deletions; ++i)
        count *= static_cast<long double>(stays + i) / static_cast<long double>(i);
    return count;
}
void joint_controls(Checks &check) {
    const ModelPolicy policy{2, {0.12, 0.18, 0.08}, 0.5};
    bool silent_negative = false, map_negative = false;
    for (const auto reverse : {false, true}) {
        const auto first = context_study::oriented("AA", reverse);
        const auto second = context_study::oriented("C", reverse);
        const auto distribution =
            ContextDistribution::weighted({{first, 0.3}, {second, 0.7}}, std::string(64, 'a'));
        const auto neural = neural_paths(reverse);
        std::map<std::string, long double> signal, joint, wrong, largest;
        for (const auto &path : neural)
            signal[path.center] += path.mass;
        for (const auto &[center, mass] : signal) {
            const auto background = std::pow(0.25L, static_cast<long double>(center.size())) / 3;
            const auto late =
                std::log(mass) +
                static_cast<long double>(context_mass(center, distribution, policy).log_ratio);
            for (const auto &path : neural) {
                if (path.center != center)
                    continue;
                const auto novel = path.mass * 0.5L;
                joint[center] += novel;
                wrong[center] += novel;
                largest[center] = std::max(largest[center], novel);
                for (const auto &source : distribution.paths()) {
                    const auto z = normalizer(source.sequence, policy);
                    for (const auto &history : histories(source.sequence, center, policy.rates)) {
                        ++check.joint_pairs;
                        const auto contribution = path.mass * 0.5L *
                                                  static_cast<long double>(source.mass) *
                                                  history.mass / z / background;
                        joint[center] += contribution;
                        wrong[center] +=
                            contribution * interleavings(path.stays, history.deletions);
                        largest[center] = std::max(largest[center], contribution);
                    }
                }
            }
            check.close(static_cast<double>(std::log(joint.at(center))), late,
                        "independent joint history-pair sum equals late log mass");
            silent_negative = silent_negative || wrong.at(center) > joint.at(center) * 1.001L;
            map_negative = map_negative || largest.at(center) < joint.at(center) * 0.9L;
        }
        auto winner = signal.begin()->first, joint_winner = winner;
        const auto native = reverse ? std::string("T") : std::string("A");
        auto prefer = [&](long double score, const std::string &sequence, long double old,
                          const std::string &old_sequence) {
            return score > old ||
                   (score == old && ((sequence == native && old_sequence != native) ||
                                     ((sequence == native) == (old_sequence == native) &&
                                      sequence < old_sequence)));
        };
        std::map<std::string, long double> late_values;
        for (const auto &[center, mass] : signal) {
            late_values[center] =
                std::log(mass) +
                static_cast<long double>(context_mass(center, distribution, policy).log_ratio);
            if (prefer(late_values.at(center), center, late_values.at(winner), winner))
                winner = center;
            if (prefer(std::log(joint.at(center)), center, std::log(joint.at(joint_winner)),
                       joint_winner))
                joint_winner = center;
        }
        check.expect(winner == joint_winner, "joint and late exact raw winners agree");
        auto baseline = signal.begin()->first;
        for (const auto &[center, mass] : signal)
            if (prefer(mass, center, signal.at(baseline), baseline))
                baseline = center;
        const bool late_gate = std::log(signal.at(winner) / signal.at(baseline)) >= -0.5L &&
                               late_values.at(winner) - late_values.at(baseline) >= 0.5L;
        const bool joint_gate = std::log(signal.at(joint_winner) / signal.at(baseline)) >= -0.5L &&
                                std::log(joint.at(joint_winner) / joint.at(baseline)) >= 0.5L;
        check.expect(late_gate == joint_gate, "joint and late unchanged gate decisions agree");
    }
    check.expect(silent_negative, "wrong deletion-stay silent interleavings fail equality");
    check.expect(map_negative, "joint maximum-history shortcut fails marginal equality");
}
void rejection_controls(Checks &check) {
    for (const auto invalid : {0.0, 1.0, -0.1, std::numeric_limits<double>::quiet_NaN()}) {
        auto policy = fixed_policies().front();
        policy.rates.insertion = invalid;
        check.rejects([&] { validate(policy); }, "invalid mutation-rate endpoint rejects");
    }
    auto policy = fixed_policies().front();
    policy.novel_mass = 0;
    check.rejects([&] { validate(policy); }, "zero novelty mass rejects");
    policy = fixed_policies().front();
    policy.maximum_center = 109;
    check.rejects([&] { validate(policy); }, "undeclared maximum center rejects");
    auto input = fixture(std::string(109, 'A'));
    check.rejects(
        [&] {
            static_cast<void>(
                score_model(input, {std::nullopt, "disabled", "."}, fixed_policies().front()));
        },
        "out-of-support eligible candidate rejects before scoring");
    input = fixture();
    input.candidates.at("A").log_mass.reset();
    check.rejects([&] { static_cast<void>(candidate_digest(input)); },
                  "missing neural score rejects");
    check.rejects([&] { enforce_work({maximum_work_cells, 1}, maximum_work_cells); },
                  "overpriced model work rejects before DP");
    check.rejects(
        [&] { static_cast<void>(Work{std::numeric_limits<std::size_t>::max(), 1}.total()); },
        "overflowing work arithmetic rejects");
    const auto options = std::vector<std::string>{
        "--cases", "input", "--cases-sha256", std::string(64, 'a'), "--output", "out"};
    check.expect(parse_options("replay", options).size() == 3,
                 "exact inference option census accepts");
    for (const auto &extra :
         {std::string("--truth"), std::string("--model-rate"), std::string("--output")}) {
        auto malformed = options;
        malformed.push_back(extra);
        malformed.push_back("foreign");
        check.rejects([&] { static_cast<void>(parse_options("replay", malformed)); },
                      "truth tuning or duplicate option rejects");
    }
    auto excessive = options;
    excessive.insert(excessive.end(), {"--max-cells", "25000001"});
    check.rejects([&] { static_cast<void>(parse_options("replay", excessive)); },
                  "unpriced larger cap rejects");
    check.rejects(
        [&] {
            static_cast<void>(
                context_study::parse_candidates({std::string(64, 'a'), {{"TRUTH", "foreign"}}}));
        },
        "truth record cannot enter candidate parser");
    context_study::Record bad{"CASE",
                              "fixture",
                              "ordinary",
                              "parent",
                              "chr1",
                              "+",
                              "0",
                              "3",
                              "1",
                              "2",
                              "0",
                              "3",
                              "1",
                              "2",
                              "0",
                              "A",
                              "C",
                              "A",
                              "usable",
                              "0",
                              "0",
                              "0",
                              "0",
                              std::string(64, 'a'),
                              std::string(64, '0')};
    check.rejects(
        [&] { static_cast<void>(context_study::parse_candidates({std::string(64, 'a'), {bad}})); },
        "foreign geometry digest rejects");
}
}
std::string qualify() {
    Checks check;
    probability_controls(check);
    alias_controls(check);
    decision_controls(check);
    joint_controls(check);
    rejection_controls(check);
    return "{\"schema\":\"context-model-controls/1\",\"synthetic_only\":true,"
           "\"biological_qualification\":false,\"absolute_log_tolerance\":1e-10,\"assertions\":" +
           std::to_string(check.assertions) +
           ",\"enumerated_strings\":" + std::to_string(check.strings) +
           ",\"enumerated_mutation_histories\":" + std::to_string(check.histories) +
           ",\"joint_history_pairs\":" + std::to_string(check.joint_pairs) +
           ",\"joint_fixture_kmer_length\":1,\"joint_fixture_timesteps\":4,"
           "\"negative_controls\":{\"missing_length_normalizer\":true,\"best_history\":true,"
           "\"path_vote_count\":true,\"silent_interleavings\":true,\"joint_map\":true,"
           "\"novel_mass_not_variant_safety\":true}}";
}
}
