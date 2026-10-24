#include "context_decoder/guarded.h"

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
constexpr char alphabet[] = "ACGT";
void expect(bool condition, const char* message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}
void close(double actual, long double expected, const char* message) {
    if (expected == -std::numeric_limits<long double>::infinity()) {
        expect(actual == -std::numeric_limits<double>::infinity(), message);
        return;
    }
    expect(std::isfinite(actual) && std::abs(static_cast<long double>(actual) - expected) <=
                                            1e-11L * (1.0L + std::abs(expected)),
           message);
}
using Census = std::map<std::string, long double>;
// Raw paths only: no production transition, guide, phase or scalar routine is used.
Census raw_paths(const Frame& frame, std::size_t begin, std::size_t end, std::size_t initial) {
    Census result;
    const auto states = std::size_t{1} << (2 * frame.state_length);
    std::function<void(std::size_t, std::size_t, std::string, long double)> visit;
    visit = [&](std::size_t time, std::size_t state, std::string emitted, long double mass) {
        if (time == end) {
            result[emitted] += mass;
            return;
        }
        visit(time + 1, state, emitted,
              mass * std::exp(static_cast<long double>(frame.stay_score)));
        for (std::size_t base = 0; base < 4; ++base) {
            const auto destination = (state * 4 + base) % states;
            const auto channel = destination * 4 + state / (states / 4);
            visit(time + 1, destination, emitted + alphabet[base],
                  mass * std::exp(static_cast<long double>(
                                 frame.scores[time * states * 4 + channel])));
        }
    };
    visit(begin, initial, "", 1.0L);
    return result;
}
std::size_t raw_state(const Frame& frame, const std::string& emitted) {
    auto state = frame.initial_state;
    const auto states = std::size_t{1} << (2 * frame.state_length);
    for (const char base : emitted) {
        const auto code = std::string(alphabet).find(base);
        state = (state * 4 + code) % states;
    }
    return state;
}
bool starts(const std::string& sequence, const std::string& prefix) {
    return sequence.size() >= prefix.size() && sequence.compare(0, prefix.size(), prefix) == 0;
}
bool ends(const std::string& sequence, const std::string& suffix) {
    return sequence.size() >= suffix.size() &&
           sequence.compare(sequence.size() - suffix.size(), suffix.size(), suffix) == 0;
}
long double lookup(const Census& census, const std::string& sequence) {
    const auto found = census.find(sequence);
    return found == census.end() ? 0.0L : found->second;
}
std::size_t distance(const std::string& a, const std::string& b) {
    std::vector<std::vector<std::size_t>> table(a.size() + 1,
                                                std::vector<std::size_t>(b.size() + 1));
    for (std::size_t i = 0; i <= a.size(); ++i) {
        table[i][0] = i;
    }
    for (std::size_t j = 0; j <= b.size(); ++j) {
        table[0][j] = j;
    }
    for (std::size_t i = 1; i <= a.size(); ++i) {
        for (std::size_t j = 1; j <= b.size(); ++j) {
            table[i][j] = std::min(
                    {table[i - 1][j] + 1, table[i][j - 1] + 1,
                     table[i - 1][j - 1] + static_cast<std::size_t>(a[i - 1] != b[j - 1])});
        }
    }
    return table.back().back();
}
long double potential(const std::string& center,
                      const std::vector<std::string>& paths,
                      bool terminal) {
    auto nearest = std::numeric_limits<std::size_t>::max();
    for (const auto& path : paths) {
        if (terminal) {
            nearest = std::min(nearest, distance(center, path));
        } else {
            for (std::size_t j = 0; j <= path.size(); ++j) {
                nearest = std::min(nearest, distance(center, path.substr(0, j)));
            }
        }
    }
    return -static_cast<long double>(nearest);
}
Frame rows(std::span<const std::array<double, 4>> values, double stay = -20.0) {
    Frame frame{values.size(), 1, 0, stay, {}};
    for (const auto& row : values) {
        for (std::size_t channel = 0; channel < 16; ++channel) {
            frame.scores.push_back(row[channel / 4]);
        }
    }
    return frame;
}
Frame peaked(const std::string& sequence) {
    std::vector<std::array<double, 4>> values;
    for (const char base : sequence) {
        std::array<double, 4> row{-12.0, -12.0, -12.0, -12.0};
        row[std::string(alphabet).find(base)] = 0.0;
        values.push_back(row);
    }
    return rows(values);
}
GuardedPolicy wide(std::size_t maximum) {
    GuardedPolicy policy;
    policy.beam_width = 512;
    policy.max_center = maximum;
    return policy;
}
std::set<std::string> centers(const GuardedExpansion& expansion) {
    std::set<std::string> result;
    for (const auto& bundle : expansion.retained) {
        result.insert(bundle.center);
    }
    return result;
}
struct Counts {
    std::size_t frames{};
    std::size_t phases{};
    std::size_t ranks{};
    std::size_t finalists{};
    std::size_t isolated_gate_cases{};
    std::size_t isolated_gate_raw_candidates{};
};
void qualify_gate(std::size_t center_size,
                  double alternate_score,
                  const char* expected_gate,
                  Counts& counts) {
    const std::string native(center_size, 'A');
    const std::string target(center_size, 'C');
    const std::array<double, 4> guard{0.0, -50.0, -50.0, -50.0};
    std::vector<std::array<double, 4>> values{guard};
    for (std::size_t j = 0; j < center_size; ++j) {
        values.push_back({0.0, alternate_score, -50.0, -50.0});
    }
    values.push_back(guard);
    GuardedWindow window{rows(values, -30.0), "A", "A", native, {Availability::usable, {target}}};
    const GuardedPolicy policy;
    const auto raw =
            raw_paths(window.scores, 0, window.scores.timesteps, window.scores.initial_state);
    std::string raw_free;
    std::string raw_context;
    long double free_score = -std::numeric_limits<long double>::infinity();
    long double context_score = free_score;
    long double context_signal = free_score;
    for (const auto& [emitted, mass] : raw) {
        if (emitted.size() < 2 || !starts(emitted, "A") || !ends(emitted, "A")) {
            continue;
        }
        const auto center = emitted.substr(1, emitted.size() - 2);
        if (center.size() > policy.max_center) {
            continue;
        }
        const auto signal = std::log(mass);
        const auto objective = signal - 0.5L * static_cast<long double>(distance(center, target));
        if (signal > free_score) {
            free_score = signal;
            raw_free = center;
        }
        if (objective > context_score) {
            context_score = objective;
            context_signal = signal;
            raw_context = center;
        }
        ++counts.isolated_gate_raw_candidates;
    }
    expect(raw_free == native && raw_context == target,
           "isolated gate fixture raw winners differ from declared native and target");
    const auto result = decode_guarded(window, policy);
    expect(!result.escape.pruned && !result.conditioned.pruned && !result.abstained &&
                   result.reference_free.sequence == raw_free &&
                   result.context_winner.sequence == raw_context &&
                   result.final_rerank_winner.sequence == raw_context,
           "isolated gate guarded winners differ from exhaustive raw winners");
    close(result.context_winner.signal_likelihood, context_signal,
          "isolated gate target signal differs from raw paths");
    close(result.context_winner.objective, context_score,
          "isolated gate target objective differs from raw paths");
    const auto delta = context_signal - free_score;
    const auto baseline = free_score - 0.5L * static_cast<long double>(distance(raw_free, target));
    const auto margin = context_score - baseline;
    if (std::string(expected_gate) == "objective_margin_fallback") {
        expect(delta >= -static_cast<long double>(policy.maximum_signal_deficit) &&
                       margin < static_cast<long double>(policy.minimum_objective_margin),
               "margin fixture does not isolate the objective-margin failure");
    } else {
        expect(delta < -static_cast<long double>(policy.maximum_signal_deficit) &&
                       margin >= static_cast<long double>(policy.minimum_objective_margin),
               "deficit fixture does not isolate the signal-deficit failure");
    }
    expect(result.gate == expected_gate && result.final_rerank_gate == expected_gate &&
                   result.selected.sequence == raw_free && result.final_rerank.sequence == raw_free,
           "isolated failed gate did not return the matched free choice in both contextual arms");
    ++counts.isolated_gate_cases;
}
void qualify(const GuardedWindow& window, const GuardedPolicy& policy, Counts& counts) {
    const auto search = guarded_search(window, policy, true);
    expect(!search.pruned, "exhaustive guarded oracle unexpectedly pruned");
    const auto paths = window.center_context.sequences;
    const auto full =
            raw_paths(window.scores, 0, window.scores.timesteps, window.scores.initial_state);
    Census accepted;
    for (const auto& [emitted, mass] : full) {
        if (emitted.size() >= window.left_guard.size() + window.right_guard.size() &&
            starts(emitted, window.left_guard) && ends(emitted, window.right_guard)) {
            const auto size = emitted.size() - window.left_guard.size() - window.right_guard.size();
            if (size >= policy.min_center && size <= policy.max_center) {
                accepted[emitted.substr(window.left_guard.size(), size)] += mass;
            }
        }
    }
    std::set<std::string> actual_finalists;
    // Check the forward search first, before any production scalar rescoring.
    for (const auto& finalist : search.finalists) {
        expect(actual_finalists.insert(finalist.sequence).second, "duplicate guarded finalist");
        expect(accepted.contains(finalist.sequence), "guarded finalist absent raw path census");
        const auto signal = std::log(accepted.at(finalist.sequence));
        const auto context = potential(finalist.sequence, paths, true);
        close(finalist.signal_mass, signal, "guarded terminal mass differs from raw paths");
        close(finalist.context_potential, context, "guarded terminal potential differs");
        close(finalist.rank, signal + static_cast<long double>(policy.context_weight) * context,
              "guarded terminal rank differs before exact rescore");
        ++counts.finalists;
    }
    expect(actual_finalists.size() == accepted.size(), "full guarded center census differs");
    for (const auto& step : search.trace) {
        const auto prefix_paths =
                raw_paths(window.scores, 0, step.timestep, window.scores.initial_state);
        for (std::size_t j = 0; j < step.left_mass.size(); ++j) {
            close(step.left_mass[j], std::log(lookup(prefix_paths, window.left_guard.substr(0, j))),
                  "outside-beam left mass differs from raw prefixes");
            ++counts.phases;
        }
        std::set<std::string> expected_centers;
        for (const auto& [emitted, mass] : prefix_paths) {
            static_cast<void>(mass);
            if (!starts(emitted, window.left_guard)) {
                continue;
            }
            const auto tail = emitted.substr(window.left_guard.size());
            for (std::size_t j = 0; j <= window.right_guard.size(); ++j) {
                if (tail.size() < j || !ends(tail, window.right_guard.substr(0, j))) {
                    continue;
                }
                const auto center = tail.substr(0, tail.size() - j);
                if (center.size() <= policy.max_center &&
                    window.scores.timesteps - step.timestep >= window.right_guard.size() - j) {
                    expected_centers.insert(center);
                }
            }
        }
        expect(centers(step) == expected_centers, "intermediate viable bundle census differs");
        for (const auto& bundle : step.retained) {
            const auto core_prefix = window.left_guard + bundle.center;
            const auto open_mass = lookup(prefix_paths, core_prefix);
            close(bundle.open_mass, std::log(open_mass), "open mass differs from raw prefixes");
            ++counts.phases;
            const auto state = raw_state(window.scores, core_prefix);
            const auto future =
                    raw_paths(window.scores, step.timestep, window.scores.timesteps, state);
            long double open_completion = 0.0L;
            for (const auto& [emitted, mass] : future) {
                if (ends(emitted, window.right_guard) &&
                    (bundle.center.size() < policy.max_center || emitted == window.right_guard)) {
                    open_completion += mass;
                }
            }
            long double ranked_mass = open_mass * open_completion *
                                      std::exp(static_cast<long double>(policy.context_weight) *
                                               potential(bundle.center, paths, false));
            close(bundle.partial_potential, potential(bundle.center, paths, false),
                  "partial context edit row differs from independent table");
            close(bundle.terminal_potential, potential(bundle.center, paths, true),
                  "terminal context edit row differs from independent table");
            for (std::size_t j = 1; j <= window.right_guard.size(); ++j) {
                const auto emitted = core_prefix + window.right_guard.substr(0, j);
                const auto mass = lookup(prefix_paths, emitted);
                close(bundle.suffix_mass[j - 1], std::log(mass),
                      "suffix-progress mass differs from raw prefixes");
                ++counts.phases;
                const auto suffix_future =
                        raw_paths(window.scores, step.timestep, window.scores.timesteps,
                                  raw_state(window.scores, emitted));
                const auto completion = lookup(suffix_future, window.right_guard.substr(j));
                ranked_mass += mass * completion *
                               std::exp(static_cast<long double>(policy.context_weight) *
                                        potential(bundle.center, paths, true));
            }
            close(bundle.rank, std::log(ranked_mass),
                  "state-dependent phase completion rank differs from raw future paths");
            ++counts.ranks;
        }
    }
    for (const auto& [center, mass] : accepted) {
        close(guarded_likelihood(window, center), std::log(mass),
              "exact guarded scalar differs from independent raw paths");
    }
    ++counts.frames;
}
}

std::string run_guarded_controls() {
    Counts counts;
    for (const std::size_t k : {std::size_t{1}, std::size_t{2}}) {
        for (const std::size_t selector : {std::size_t{0}, std::size_t{1}}) {
            for (std::size_t time = k + 1; time <= 7; ++time) {
                const auto states = std::size_t{1} << (2 * k);
                Frame frame{time, k, selector == 0 ? 0 : states - 1, -0.7, {}};
                for (std::size_t i = 0; i < time * states * 4; ++i) {
                    frame.scores.push_back(-static_cast<double>((i * 17 + 3) % 31) / 10.0);
                }
                const std::string right(k, selector == 0 ? 'A' : 'C');
                GuardedWindow window{frame, "A", right, "", {Availability::usable, {"", "AC"}}};
                qualify(window, wide(2), counts);
            }
        }
    }
    // A raw all-A path has C(4,2)=6 timings for AA. An epsilon handoff can assign
    // each intervening stay to either phase, producing C(5,3)=10 interpretations.
    Frame repeated{4, 1, 0, 0.0, std::vector<double>(64, 0.0)};
    const auto repeated_raw = raw_paths(repeated, 0, 4, 0);
    expect(lookup(repeated_raw, "AA") == 6.0L, "independent AA timing census differs");
    // Deliberately wrong automaton: open and epsilon-closed phases both allow
    // stays, and a scoreless close may occur at every row boundary.
    std::array<long double, 4> epsilon_dp{1.0L, 0.0L, 0.0L, 0.0L};
    for (std::size_t time = 0; time < repeated.timesteps; ++time) {
        epsilon_dp[2] += epsilon_dp[1];
        epsilon_dp = {epsilon_dp[0], epsilon_dp[1] + epsilon_dp[0], epsilon_dp[2],
                      epsilon_dp[3] + epsilon_dp[2]};
    }
    const auto repeated_search = guarded_search(
            {repeated, "A", "A", "", {Availability::usable, {"", "AA"}}}, wide(2), false);
    const auto empty_center =
            std::find_if(repeated_search.finalists.begin(), repeated_search.finalists.end(),
                         [](const Prefix& finalist) { return finalist.sequence.empty(); });
    expect(empty_center != repeated_search.finalists.end(),
           "unit-weight guarded search omitted the empty center");
    close(empty_center->signal_mass, std::log(lookup(repeated_raw, "AA")),
          "actual guarded empty-center mass differs from six raw timing paths");
    expect(epsilon_dp.back() == 10.0L &&
                   std::abs(static_cast<long double>(empty_center->signal_mass) -
                            std::log(epsilon_dp.back())) > 0.1L,
           "executed epsilon-close recurrence failed to disagree with guarded search");
    qualify({repeated, "A", "A", "", {Availability::usable, {"", "AA"}}}, wide(2), counts);
    qualify_gate(1, -0.3, "objective_margin_fallback", counts);
    qualify_gate(3, -0.2, "signal_deficit_fallback", counts);

    Frame guided{2, 1, 0, -20.0, std::vector<double>(32, -10.0)};
    for (std::size_t predecessor = 0; predecessor < 4; ++predecessor) {
        guided.scores[predecessor] = 0.0;
        guided.scores[4 + predecessor] = -0.1;
        guided.scores[16 + 12 + predecessor] = -4.0;
    }
    guided.scores[16 + 12 + 1] = 4.0;
    auto narrow = wide(1);
    narrow.beam_width = 1;
    GuardedWindow guide_window{guided, "", "T", "A", {Availability::missing, {}}};
    const auto guide_result = decode_guarded(guide_window, narrow);
    const auto guide_raw = raw_paths(guided, 0, 2, 0);
    expect(guide_result.escape.trace.front().retained.front().center == "C" &&
                   guide_result.reference_free.sequence == "C",
           "required-suffix state-dependent guide was not used by beam1");
    close(guide_result.reference_free.signal_likelihood, std::log(guide_raw.at("CT")),
          "guide witness exact likelihood differs");
    // Independent zero-guide choice reads current raw prefix masses only.
    const auto guide_prefixes = raw_paths(guided, 0, 1, 0);
    expect(guide_prefixes.at("A") > guide_prefixes.at("C") &&
                   guide_raw.at("AT") < guide_raw.at("CT"),
           "independent zero-guide witness does not separate current mass and suffix support");

    const std::array<std::array<double, 4>, 4> ambiguity{{{0.0, -0.1, -9.0, -9.0},
                                                          {0.0, -0.1, -9.0, -9.0},
                                                          {0.0, -0.1, -9.0, -9.0},
                                                          {-9.0, -9.0, -9.0, 0.0}}};
    auto partial_policy = wide(3);
    partial_policy.beam_width = 1;
    GuardedWindow partial{rows(ambiguity), "", "T", "AAA", {Availability::usable, {"CCCC"}}};
    const auto feedback = decode_guarded(partial, partial_policy);
    expect(feedback.reference_free.sequence == "AAA" && feedback.final_rerank.sequence == "AAA" &&
                   feedback.selected.sequence == "CCC" && feedback.partial_search_differences > 0,
           "context search failed to discover a center absent free finalists");
    expect(std::none_of(feedback.escape.finalists.begin(), feedback.escape.finalists.end(),
                        [](const Prefix& prefix) { return prefix.sequence == "CCC"; }) &&
                   partial.center_context.sequences.front() != feedback.selected.sequence,
           "feedback witness was injected from context or already a free finalist");
    expect(feedback.selected.sequence != "AAA" && feedback.selected.sequence != "AAC",
           "feedback witness stayed confined to historical synthetic H");
    const auto rerank_only = decode_guarded(partial, wide(3));
    std::set<std::string> free_finalists;
    std::set<std::string> conditioned_finalists;
    for (const auto& finalist : rerank_only.escape.finalists) {
        free_finalists.insert(finalist.sequence);
    }
    for (const auto& finalist : rerank_only.conditioned.finalists) {
        conditioned_finalists.insert(finalist.sequence);
    }
    expect(free_finalists == conditioned_finalists &&
                   rerank_only.reference_free.sequence == "AAA" &&
                   rerank_only.final_rerank.sequence == "CCC" &&
                   rerank_only.selected.sequence == "CCC",
           "matched-finalist case failed to isolate final context weighting");
    auto changed = partial;
    changed.center_context.sequences = {"AAAA"};
    expect(decode_guarded(changed, partial_policy).selected.sequence == "AAA",
           "changing valid context did not change partial search");
    changed.center_context.sequences = {"CCCC", "AAC", "CCCC"};
    const auto aliased = decode_guarded(changed, partial_policy);
    changed.center_context.sequences = {"AAC", "CCCC"};
    expect(guarded_outcome_json(aliased) ==
                   guarded_outcome_json(decode_guarded(changed, partial_policy)),
           "context permutation or aliases changed exact output or trace");
    auto zero = partial_policy;
    zero.context_weight = 0.0;
    const auto disabled = decode_guarded(partial, zero);
    changed.center_context = {Availability::missing, {}};
    const auto missing = decode_guarded(changed, partial_policy);
    expect(guarded_outcome_json(disabled) == guarded_outcome_json(missing),
           "zero-weight and missing context differ in exact choices or full traces");
    changed.center_context = {Availability::ambiguous, {"CCCC"}};
    expect(guarded_outcome_json(disabled) ==
                   guarded_outcome_json(decode_guarded(changed, partial_policy)),
           "ambiguous context differs from exact disabled fallback");
    expect(std::bit_cast<std::uint64_t>(disabled.reference_free.signal_likelihood) ==
                   std::bit_cast<std::uint64_t>(disabled.selected.signal_likelihood),
           "disabled likelihood bits changed");
    const auto deletion_context = canonical_center_context({Availability::usable, {"", ""}});
    expect(deletion_context == std::vector<std::string>{""},
           "valid full-deletion center context was confused with missing context");

    const std::array<std::pair<std::string, std::string>, 3> private_cases{
            {{"GGG", "AAA"}, {"AG", "A"}, {"A", "AG"}}};
    for (const auto& [native, context] : private_cases) {
        GuardedWindow private_window{
                peaked(native + "T"), "", "T", native, {Availability::usable, {context}}};
        const auto result = decode_guarded(private_window, wide(native.size()));
        expect(result.selected.sequence == native && result.reference_free.sequence == native &&
                       native != context && !result.abstained,
               "strong private SNV/insertion/deletion absent context was lost");
    }
    GuardedWindow boundary_insertion{peaked("AAAA"), "A", "A", "A", {Availability::missing, {}}};
    const auto inserted = decode_guarded(boundary_insertion, wide(2));
    expect(inserted.selected.sequence == "AA" &&
                   std::isfinite(guarded_likelihood(boundary_insertion, "A")) &&
                   std::isfinite(guarded_likelihood(boundary_insertion, "AA")),
           "supported center/right homopolymer insertion was deduplicated or filtered");
    // The feedback witness also retains a measured weak-private erasure warning.
    expect(feedback.selected.sequence != partial.native_center,
           "weak private caution witness no longer demonstrates an actual loss");

    const std::array<std::array<double, 4>, 2> tie_rows{
            {{0.0, 0.0, -12.0, -12.0}, {-12.0, -12.0, -12.0, 0.0}}};
    GuardedWindow ties{rows(tie_rows), "", "T", "C", {Availability::missing, {}}};
    expect(decode_guarded(ties, wide(1)).selected.sequence == "C",
           "native-first exact objective tie differs");
    ties.native_center = "G";
    expect(decode_guarded(ties, wide(1)).selected.sequence == "A",
           "lexical exact objective tie differs");
    GuardedWindow impossible{peaked("A"), "A", "T", "", {Availability::missing, {}}};
    expect(guarded_search(impossible, wide(0), false).finalists.empty(),
           "unfinishable grammar manufactured an eligible finalist");
    GuardedWindow capped{peaked("AAAT"), "", "T", "A", {Availability::usable, {"AAA"}}};
    const auto cap = decode_guarded(capped, wide(1));
    expect(cap.escape.center_bound_reached && cap.reference_free_abstained && cap.abstained &&
                   cap.final_rerank_abstained && cap.selected.sequence == "A" &&
                   cap.final_rerank.sequence == "A" && cap.reference_free.sequence == "A",
           "feasible center-cap event did not abstain all affected candidate arms");
    const auto physical_end = decode_guarded(guide_window, narrow);
    expect(!physical_end.escape.center_bound_reached,
           "physical end-of-frame was mislabeled feasible center-cap truncation");
    const std::array<std::array<double, 4>, 3> conditioned_cap_rows{
            {{0.6, -20.0, -20.0, 0.0}, {-20.0, -20.0, -20.0, 0.0}, {-20.0, -20.0, -20.0, 0.0}}};
    GuardedWindow conditioned_cap{
            rows(conditioned_cap_rows, 0.0), "", "T", "", {Availability::usable, {"AAAA"}}};
    const auto conditioned_limit = decode_guarded(conditioned_cap, narrow);
    expect(!conditioned_limit.escape.center_bound_reached &&
                   conditioned_limit.conditioned.center_bound_reached &&
                   !conditioned_limit.reference_free_abstained &&
                   !conditioned_limit.final_rerank_abstained && conditioned_limit.abstained &&
                   conditioned_limit.gate == "conditioned_center_bound_abstain" &&
                   conditioned_limit.selected.sequence == conditioned_cap.native_center &&
                   conditioned_limit.reference_free.sequence == "" &&
                   conditioned_limit.final_rerank.sequence == "",
           "conditioned-only cap changed the independent free or final-rerank arms");

    std::ostringstream out;
    out << "{\"schema\":\"guarded-controls/2\",\"raw_path_frames\":" << counts.frames
        << ",\"independent_phase_mass_comparisons\":" << counts.phases
        << ",\"independent_state_dependent_rank_comparisons\":" << counts.ranks
        << ",\"independent_finalist_census_mass_rank_comparisons\":" << counts.finalists
        << ",\"isolated_gate_cases\":" << counts.isolated_gate_cases
        << ",\"isolated_gate_raw_candidates\":" << counts.isolated_gate_raw_candidates
        << ",\"tolerance\":\"1e-11*(1+abs(independent_long_double))\""
        << ",\"raw_paths_k1_k2_through_T7\":true,\"epsilon_close_raw_count\":6"
        << ",\"epsilon_close_duplicate_count\":10,\"epsilon_close_bad_recurrence_executed\":true"
        << ",\"isolated_margin_and_signal_deficit_fallbacks\":true"
        << ",\"state_dependent_guide_beam1\":true"
        << ",\"zero_guide_independent_witness\":\"A versus guarded C\""
        << ",\"disabled_exact_bits_and_trace\":true,\"strong_private_snv_ins_del\":true"
        << ",\"empty_context_path_is_valid\":true,\"weak_private_loss_retained\":true"
        << ",\"native_lexical_ties_and_caps\":true,\"conditioned_only_cap_isolated\":true"
        << ",\"partial_context_discovery\":" << guarded_outcome_json(feedback)
        << ",\"genuine_fixture_checked\":false,\"complete\":true}";
    return out.str();
}
}
