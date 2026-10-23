#include "context_decoder/controls.h"

#include "context_decoder/decoder.h"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>

namespace context_decoder {
namespace {
void expect(bool condition, const char* message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}
std::size_t oracle_distance(const std::string& a, const std::string& b) {
    std::vector<std::vector<std::size_t>> costs(a.size() + 1,
                                                std::vector<std::size_t>(b.size() + 1));
    for (std::size_t i = 0; i <= a.size(); ++i) {
        costs[i][0] = i;
    }
    for (std::size_t j = 0; j <= b.size(); ++j) {
        costs[0][j] = j;
    }
    for (std::size_t i = 1; i <= a.size(); ++i) {
        for (std::size_t j = 1; j <= b.size(); ++j) {
            costs[i][j] = std::min(
                    {costs[i - 1][j] + 1, costs[i][j - 1] + 1,
                     costs[i - 1][j - 1] + static_cast<std::size_t>(a[i - 1] != b[j - 1])});
        }
    }
    return costs.back().back();
}
std::map<std::string, long double> enumerate(const Frame& frame) {
    std::map<std::string, long double> sums;
    const auto states = std::size_t{1} << (2 * frame.state_length);
    std::function<void(std::size_t, std::size_t, std::string, long double)> visit;
    visit = [&](std::size_t time, std::size_t state, std::string sequence,
                long double log_probability) {
        if (time == frame.timesteps) {
            sums[sequence] += std::exp(log_probability);
            return;
        }
        visit(time + 1, state, sequence,
              log_probability + static_cast<long double>(frame.stay_score));
        for (std::size_t base = 0; base < 4; ++base) {
            const auto next = (state * 4 + base) % states;
            const auto channel = 4 * next + state / (states / 4);
            visit(time + 1, next, sequence + "ACGT"[base],
                  log_probability +
                          static_cast<long double>(frame.scores[time * states * 4 + channel]));
        }
    };
    visit(0, frame.initial_state, "", 0.0L);
    return sums;
}
Frame simple(std::span<const std::array<double, 4>> rows, double blank = -8.0) {
    Frame frame{rows.size(), 1, 0, blank, {}};
    for (const auto& row : rows) {
        for (std::size_t channel = 0; channel < 16; ++channel) {
            const auto destination = channel / 4;
            frame.scores.push_back(row[destination]);
        }
    }
    return frame;
}
Policy tiny_policy() {
    Policy policy;
    policy.beam_width = 512;
    policy.max_symbols = 4;
    policy.min_symbols = 0;
    return policy;
}
}

std::string run_controls() {
    std::size_t comparisons = 0;
    std::size_t distance_comparisons = 0;
    std::size_t search_mass_comparisons = 0;
    for (const std::size_t k : {std::size_t{1}, std::size_t{2}, std::size_t{3}, std::size_t{4}}) {
        for (const std::size_t initial_selector : {std::size_t{0}, std::size_t{1}}) {
            for (std::size_t length = 0; length <= 4; ++length) {
                const auto channels = std::size_t{1} << (2 * (k + 1));
                Frame frame{length, k, 0, -0.7, {}};
                frame.initial_state = initial_selector == 0 ? 0 : (channels / 4) - 1;
                for (std::size_t i = 0; i < length * channels; ++i) {
                    frame.scores.push_back(-static_cast<double>((i * 17 + 3) % 31) / 10.0);
                }
                const auto independent = enumerate(frame);
                const RetrievedContext context{Availability::usable, {"AC", "AG"}};
                const auto paths = canonical_context(context);
                const auto all = search(frame, paths, tiny_policy(), true);
                expect(!all.pruned, "tiny oracle unexpectedly pruned");
                std::set<std::string> search_sequences;
                for (const auto& finalist : all.finalists) {
                    expect(search_sequences.insert(finalist.sequence).second,
                           "search emitted a duplicate sequence finalist");
                    const auto found = independent.find(finalist.sequence);
                    expect(found != independent.end(), "search emitted an impossible finalist");
                    const auto expected_mass = static_cast<double>(std::log(found->second));
                    std::size_t expected_distance = std::numeric_limits<std::size_t>::max();
                    for (const auto& path : paths) {
                        expected_distance = std::min(expected_distance,
                                                     oracle_distance(finalist.sequence, path));
                    }
                    const auto expected_rank =
                            expected_mass - 0.5 * static_cast<double>(expected_distance);
                    const auto tolerance = 1e-11 * (1.0 + std::abs(expected_rank));
                    expect(std::abs(finalist.signal_mass - expected_mass) <= tolerance,
                           "search omitted or double-counted marginalized signal paths");
                    expect(finalist.context_potential == -static_cast<double>(expected_distance) &&
                                   std::abs(finalist.rank - expected_rank) <= tolerance,
                           "search final context rank differs from independent oracle");
                    ++search_mass_comparisons;
                }
                expect(search_sequences.size() == independent.size(),
                       "complete unpruned search sequence census differs");
                for (const auto& [sequence, mass] : independent) {
                    const auto actual = sequence_likelihood(frame, sequence);
                    const auto expected = static_cast<double>(std::log(mass));
                    expect(std::abs(actual - expected) <= 1e-11 * (1.0 + std::abs(expected)),
                           "independent stay/step path probability mismatch");
                    ++comparisons;
                    std::size_t full = std::numeric_limits<std::size_t>::max();
                    std::size_t prefix = full;
                    for (const auto& path : paths) {
                        full = std::min(full, oracle_distance(sequence, path));
                        for (std::size_t j = 0; j <= path.size(); ++j) {
                            prefix = std::min(prefix, oracle_distance(sequence, path.substr(0, j)));
                        }
                    }
                    expect(context_potential(sequence, paths, true) == -static_cast<double>(full) &&
                                   context_potential(sequence, paths, false) ==
                                           -static_cast<double>(prefix),
                           "independent context-state oracle mismatch");
                    const auto expected_objective = expected - 0.5 * static_cast<double>(full);
                    const auto actual_objective =
                            actual + 0.5 * context_potential(sequence, paths, true);
                    expect(std::abs(expected_objective - actual_objective) <=
                                   1e-11 * (1.0 + std::abs(expected_objective)),
                           "independent nonzero context objective mismatch");
                    ++distance_comparisons;
                }
            }
        }
    }
    const std::array<std::array<double, 4>, 3> ambiguous{
            {{0.0, -0.1, -4.0, -4.0}, {0.0, -0.1, -4.0, -4.0}, {0.0, -0.1, -4.0, -4.0}}};
    const auto frame = simple(ambiguous);
    auto policy = tiny_policy();
    policy.beam_width = 1;
    policy.max_symbols = 3;
    policy.min_symbols = 3;
    const RetrievedContext ccc{Availability::usable, {"CCC"}};
    const RetrievedContext aaa{Availability::usable, {"AAA"}};
    const auto feedback = decode(frame, ccc, policy, "AAA");
    const auto different_context = decode(frame, aaa, policy, "AAA");
    expect(feedback.reference_free.sequence == "AAA" && feedback.selected.sequence == "CCC" &&
                   feedback.partial_search_differences > 0 &&
                   different_context.selected.sequence == "AAA",
           "valid sequence context did not alter partial search");
    const std::vector<std::string> old_h{"AAA", "AAC"};
    expect(std::find(old_h.begin(), old_h.end(), feedback.selected.sequence) == old_h.end(),
           "feedback alternative was confined to old H");
    const auto aliases = decode(frame, {Availability::usable, {"CCC", "CCC"}}, policy, "AAA");
    expect(aliases.selected.sequence == feedback.selected.sequence &&
                   aliases.selected.objective == feedback.selected.objective &&
                   aliases.conditioned.trace.front().retained_prefixes ==
                           feedback.conditioned.trace.front().retained_prefixes,
           "duplicate aliases manufactured context support");
    const auto ordered = decode(frame, {Availability::usable, {"CCC", "AAC"}}, policy, "AAA");
    const auto permuted =
            decode(frame, {Availability::usable, {"AAC", "CCC", "AAC"}}, policy, "AAA");
    expect(outcome_json(ordered) == outcome_json(permuted),
           "input path permutation or aliases changed output/search evidence");
    policy.context_weight = 0.0;
    const auto disabled = decode(frame, ccc, policy, "AAA");
    const auto missing = decode(frame, {Availability::missing, {}}, policy, "AAA");
    expect(outcome_json(disabled) == outcome_json(missing),
           "context-disabled fallback differs in bits/trace");
    expect(std::bit_cast<std::uint64_t>(disabled.selected.signal_likelihood) ==
                   std::bit_cast<std::uint64_t>(disabled.reference_free.signal_likelihood),
           "disabled scalar bits changed");
    policy.context_weight = 0.5;
    const auto missing_nonzero_weight = decode(frame, {Availability::missing, {}}, policy, "AAA");
    expect(outcome_json(disabled) == outcome_json(missing_nonzero_weight),
           "missing context at nonzero configured weight changed disabled parity");
    const auto ambiguous_location =
            decode(frame, {Availability::ambiguous, {"CCC"}}, policy, "AAA");
    expect(ambiguous_location.selected.sequence == "AAA" && !ambiguous_location.context_enabled,
           "ambiguous location did not fall back");
    const std::array<std::array<double, 4>, 3> strong{
            {{-9.0, -5.0, 0.0, -9.0}, {-9.0, -5.0, 0.0, -9.0}, {-9.0, -5.0, 0.0, -9.0}}};
    expect(decode(simple(strong), ccc, policy, "GGG").selected.sequence == "GGG",
           "strong private substitution was lost");
    policy.min_symbols = 0;
    const std::array<std::array<double, 4>, 2> insertion{
            {{0.0, -8.0, -8.0, -8.0}, {-8.0, -8.0, 0.0, -8.0}}};
    expect(decode(simple(insertion), {Availability::usable, {"A"}}, policy, "AG")
                           .selected.sequence == "AG",
           "strong private insertion was lost");
    const std::array<std::array<double, 4>, 1> deletion{{{0.0, -8.0, -8.0, -8.0}}};
    expect(decode(simple(deletion), {Availability::usable, {"AG"}}, policy, "A")
                           .selected.sequence == "A",
           "strong private deletion was lost");
    const auto empty = simple({});
    expect(sequence_likelihood(empty, "") == 0.0 &&
                   sequence_likelihood(empty, "A") == -std::numeric_limits<double>::infinity(),
           "empty interval/impossible sequence behavior differs");
    auto corrupt = frame;
    corrupt.scores[0] = std::numeric_limits<double>::infinity();
    bool rejected = false;
    try {
        validate(corrupt, policy);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    expect(rejected, "nonfinite score accepted");
    Frame guided{2, 1, 0, -20.0, std::vector<double>(32, -4.0)};
    for (std::size_t predecessor = 0; predecessor < 4; ++predecessor) {
        guided.scores[predecessor] = 0.0;
        guided.scores[4 + predecessor] = -0.1;
        guided.scores[8 + predecessor] = -10.0;
        guided.scores[12 + predecessor] = -10.0;
    }
    guided.scores[16 + 4 + 1] = 4.0;
    auto guided_policy = tiny_policy();
    guided_policy.beam_width = 1;
    guided_policy.min_symbols = 2;
    guided_policy.max_symbols = 2;
    guided_policy.context_weight = 0.0;
    const auto guide_control = decode(guided, {Availability::missing, {}}, guided_policy, "AA");
    const auto independently_enumerated_guided = enumerate(guided);
    const auto exact_cc = static_cast<double>(std::log(independently_enumerated_guided.at("CC")));
    expect(guide_control.escape.trace.front().retained_prefixes == std::vector<std::string>{"C"} &&
                   guide_control.reference_free.sequence == "CC" &&
                   std::abs(guide_control.reference_free.signal_likelihood - exact_cc) <= 1e-12 &&
                   std::abs(exact_cc - 3.9) <= 1e-12,
           "state-dependent backward guide was omitted or misindexed in pruned search");
    const auto zero_guide_first =
            guided.scores[0] >= guided.scores[4] ? std::size_t{0} : std::size_t{1};
    std::size_t zero_guide_next = 0;
    for (std::size_t base = 1; base < 4; ++base) {
        if (guided.scores[16 + 4 * base + zero_guide_first] >
            guided.scores[16 + 4 * zero_guide_next + zero_guide_first]) {
            zero_guide_next = base;
        }
    }
    const std::string zero_guide_sequence =
            std::string(1, "ACGT"[zero_guide_first]) + "ACGT"[zero_guide_next];
    expect(zero_guide_sequence == "AA" && guided.scores[0] + guided.scores[16] == -4.0,
           "independent zero-guide negative witness does not separate the guide");
    const std::array<std::array<double, 4>, 2> ties{
            {{0.0, 0.0, -10.0, -10.0}, {0.0, 0.0, -10.0, -10.0}}};
    auto tie_policy = guided_policy;
    tie_policy.beam_width = 16;
    expect(decode(simple(ties, -20.0), {Availability::missing, {}}, tie_policy, "CC")
                           .selected.sequence == "CC",
           "native-first final objective tie was not retained");
    expect(decode(simple(ties, -20.0), {Availability::missing, {}}, tie_policy, "GG")
                           .selected.sequence == "AA",
           "lexical final objective tie was not retained");
    const auto no_finalist = decode(simple(deletion), {Availability::missing, {}}, tie_policy, "A");
    expect(no_finalist.abstained && no_finalist.gate == "no_eligible_finalist_abstain" &&
                   no_finalist.selected.sequence == "A",
           "empty eligible finalist set did not abstain");
    auto bound_policy = tiny_policy();
    bound_policy.max_symbols = 1;
    const auto limited = decode(frame, aaa, bound_policy, "A");
    expect(limited.abstained && limited.gate == "symbol_bound_abstain" &&
                   limited.selected.sequence == "A",
           "symbol bound did not explicitly abstain");
    std::ostringstream summary;
    summary << "{\"schema\":\"context-decoder-controls/1\",\"independent_path_comparisons\":"
            << comparisons << ",\"independent_context_comparisons\":" << distance_comparisons
            << ",\"independent_search_finalist_mass_rank_comparisons\":" << search_mass_comparisons
            << ",\"context_tolerance\":\"1e-11*(1+abs(independent_long_double_logsum))\""
            << ",\"disabled_exact_bits_and_trace\":true,\"ambiguous_signal_feedback\":"
            << outcome_json(feedback)
            << ",\"strong_private_substitution_insertion_deletion_retained\":true"
            << ",\"state_dependent_backward_guide_control\":{\"actual_expected\":\"CC\",\"expected_"
               "signal\":3.9,\"independent_zero_guide\":\"AA\",\"zero_guide_signal\":-4}"
            << ",\"native_and_lexical_ties\":true,\"no_eligible_finalist_abstains\":true"
            << ",\"weak_private_caution\":\"The same ambiguous example would erase AAA if AAA were "
               "a genuine private allele. Escape alone is not protection.\""
            << ",\"genuine_fixture_checked\":false,\"complete\":true}";
    return summary.str();
}
}
