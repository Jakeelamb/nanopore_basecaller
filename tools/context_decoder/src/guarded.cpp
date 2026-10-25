#include "context_decoder/guarded.h"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace context_decoder {
namespace {
constexpr double neg = -std::numeric_limits<double>::infinity();
constexpr char bases[] = "ACGT";
void require(bool condition, const char* message) {
    if (!condition) {
        throw std::invalid_argument(message);
    }
}
bool dna(const std::string& sequence) {
    return std::all_of(sequence.begin(), sequence.end(), [](char base) {
        return base == 'A' || base == 'C' || base == 'G' || base == 'T';
    });
}
std::size_t advance(std::size_t state, const std::string& sequence, std::size_t k) {
    for (const char base : sequence) {
        std::size_t next{};
        static_cast<void>(transition(state, static_cast<unsigned char>(base), k, next));
        state = next;
    }
    return state;
}
double emit(const Frame& frame, std::size_t time, std::size_t state, char base) {
    std::size_t next{};
    const auto channel =
            transition(state, static_cast<unsigned char>(base), frame.state_length, next);
    return frame.scores[time * (std::size_t{1} << (2 * (frame.state_length + 1))) + channel];
}
struct Guides {
    std::size_t states;
    std::size_t progress;
    std::vector<double> suffix;
    std::vector<double> open;
    double q(std::size_t time, std::size_t state, std::size_t j) const {
        return suffix[(time * states + state) * progress + j];
    }
    double b(std::size_t time, std::size_t state) const { return open[time * states + state]; }
};
Guides guides(const GuardedWindow& window) {
    const auto& frame = window.scores;
    const auto states = std::size_t{1} << (2 * frame.state_length);
    const auto progress = window.right_guard.size() + 1;
    Guides result{states, progress,
                  std::vector<double>((frame.timesteps + 1) * states * progress, neg),
                  std::vector<double>((frame.timesteps + 1) * states, neg)};
    for (std::size_t state = 0; state < states; ++state) {
        result.suffix[(frame.timesteps * states + state) * progress + progress - 1] = 0.0;
    }
    for (std::size_t time = frame.timesteps; time > 0; --time) {
        for (std::size_t state = 0; state < states; ++state) {
            for (std::size_t j = 0; j < progress; ++j) {
                double mass = frame.stay_score + result.q(time, state, j);
                if (j + 1 < progress) {
                    const auto base = window.right_guard[j];
                    const auto next = advance(state, std::string(1, base), frame.state_length);
                    mass = log_add(
                            mass, emit(frame, time - 1, state, base) + result.q(time, next, j + 1));
                }
                result.suffix[((time - 1) * states + state) * progress + j] = mass;
            }
            double mass = frame.stay_score + result.b(time, state);
            for (std::size_t base = 0; base < 4; ++base) {
                const auto next = advance(state, std::string(1, bases[base]), frame.state_length);
                mass = log_add(mass,
                               emit(frame, time - 1, state, bases[base]) + result.b(time, next));
            }
            const auto first = window.right_guard.front();
            const auto next = advance(state, std::string(1, first), frame.state_length);
            mass = log_add(mass, emit(frame, time - 1, state, first) + result.q(time, next, 1));
            result.open[(time - 1) * states + state] = mass;
        }
    }
    return result;
}
struct Item {
    GuardedBundle bundle;
    std::size_t state{};
    std::vector<std::vector<std::size_t>> distances;
};
Item empty_item(std::size_t state, std::size_t right_size, std::span<const std::string> paths) {
    Item result{{"", neg, std::vector<double>(right_size, neg), 0.0, 0.0, neg}, state, {}};
    for (const auto& path : paths) {
        std::vector<std::size_t> row(path.size() + 1);
        for (std::size_t j = 0; j < row.size(); ++j) {
            row[j] = j;
        }
        result.distances.push_back(std::move(row));
    }
    return result;
}
Item child_item(const Item& parent, char base, std::size_t next) {
    Item child = parent;
    child.state = next;
    child.bundle.center += base;
    child.bundle.open_mass = neg;
    std::fill(child.bundle.suffix_mass.begin(), child.bundle.suffix_mass.end(), neg);
    return child;
}
void update_distances(Item& child, char base, std::span<const std::string> paths) {
    auto partial = std::numeric_limits<std::size_t>::max();
    auto terminal = partial;
    for (std::size_t p = 0; p < paths.size(); ++p) {
        auto& row = child.distances[p];
        auto diagonal = row[0];
        row[0] = child.bundle.center.size();
        for (std::size_t j = 1; j < row.size(); ++j) {
            const auto previous = row[j];
            row[j] = std::min({row[j] + 1, row[j - 1] + 1,
                               diagonal + static_cast<std::size_t>(base != paths[p][j - 1])});
            diagonal = previous;
        }
        partial = std::min(partial, *std::min_element(row.begin(), row.end()));
        terminal = std::min(terminal, row.back());
    }
    if (!paths.empty()) {
        child.bundle.partial_potential = -static_cast<double>(partial);
        child.bundle.terminal_potential = -static_cast<double>(terminal);
    }
}
bool preferred(const Choice& a, const Choice& b, const std::string& native) {
    if (a.objective != b.objective) {
        return a.objective > b.objective;
    }
    if ((a.sequence == native) != (b.sequence == native)) {
        return a.sequence == native;
    }
    return a.sequence < b.sequence;
}
void number(std::ostream& out, double value) {
    if (std::isfinite(value)) {
        out << value;
    } else {
        out << "null";
    }
}
void choice_json(std::ostream& out, const Choice& choice) {
    out << "{\"sequence\":\"" << choice.sequence << "\",\"signal_likelihood\":";
    number(out, choice.signal_likelihood);
    out << ",\"context_potential\":";
    number(out, choice.context_potential);
    out << ",\"objective\":";
    number(out, choice.objective);
    out << '}';
}
void search_json(std::ostream& out, const GuardedSearch& search) {
    out << "{\"pruned\":" << search.pruned
        << ",\"center_bound_reached\":" << search.center_bound_reached << ",\"finalists\":[";
    for (std::size_t i = 0; i < search.finalists.size(); ++i) {
        if (i != 0) {
            out << ',';
        }
        const auto& finalist = search.finalists[i];
        out << "{\"center\":\"" << finalist.sequence << "\",\"signal_mass\":";
        number(out, finalist.signal_mass);
        out << ",\"context_potential\":";
        number(out, finalist.context_potential);
        out << ",\"rank\":";
        number(out, finalist.rank);
        out << '}';
    }
    out << "],\"trace\":[";
    for (std::size_t i = 0; i < search.trace.size(); ++i) {
        if (i != 0) {
            out << ',';
        }
        const auto& step = search.trace[i];
        out << "{\"timestep\":" << step.timestep << ",\"generated\":" << step.generated
            << ",\"merged\":" << step.merged << ",\"pruned\":" << step.pruned
            << ",\"retained_centers\":[";
        for (std::size_t j = 0; j < step.retained.size(); ++j) {
            if (j != 0) {
                out << ',';
            }
            const auto& bundle = step.retained[j];
            out << '"' << bundle.center << '"';
        }
        out << "]}";
    }
    out << "]}";
}
}

std::vector<std::string> canonical_center_context(const RetrievedContext& context) {
    if (context.availability != Availability::usable) {
        return {};
    }
    std::set<std::string> paths;
    for (const auto& path : context.sequences) {
        require(path.size() <= 128 && dna(path), "invalid center context DNA");
        paths.insert(path);
    }
    require(!paths.empty() && paths.size() <= 32, "usable center context needs 1..32 paths");
    return {paths.begin(), paths.end()};
}
void validate_guarded(const GuardedWindow& window, const GuardedPolicy& policy) {
    Policy scalar;
    scalar.beam_width = policy.beam_width;
    scalar.min_symbols = policy.min_center;
    scalar.max_symbols = policy.max_center;
    scalar.context_weight = policy.context_weight;
    scalar.maximum_signal_deficit = policy.maximum_signal_deficit;
    scalar.minimum_objective_margin = policy.minimum_objective_margin;
    validate(window.scores, scalar);
    require(policy.min_center == 0, "guarded guide requires minimum center zero");
    require(window.left_guard.size() <= 128 && dna(window.left_guard), "invalid left guard");
    require(window.right_guard.size() >= window.scores.state_length &&
                    window.right_guard.size() <= 128 && dna(window.right_guard),
            "right guard must contain at least k canonical bases");
    require(window.native_center.size() <= policy.max_center && dna(window.native_center),
            "invalid native center");
    static_cast<void>(canonical_center_context(window.center_context));
}
double guarded_likelihood(const GuardedWindow& window, const std::string& center) {
    require(dna(center), "invalid candidate center DNA");
    return sequence_likelihood(window.scores, window.left_guard + center + window.right_guard);
}
GuardedSearch guarded_search(const GuardedWindow& window,
                             const GuardedPolicy& policy,
                             bool use_context) {
    validate_guarded(window, policy);
    const auto canonical = canonical_center_context(window.center_context);
    const bool enabled = use_context && policy.context_weight != 0.0 && !canonical.empty();
    const std::span<const std::string> paths =
            enabled ? std::span<const std::string>(canonical) : std::span<const std::string>{};
    const auto guide = guides(window);
    const auto& frame = window.scores;
    std::vector<double> left(window.left_guard.size(), neg);
    std::vector<std::size_t> left_states{frame.initial_state};
    for (const char base : window.left_guard) {
        left_states.push_back(
                advance(left_states.back(), std::string(1, base), frame.state_length));
    }
    std::vector<Item> beam;
    auto initial = empty_item(left_states.back(), window.right_guard.size(), paths);
    if (enabled) {
        initial.bundle.terminal_potential = context_potential("", paths, true);
    }
    if (left.empty()) {
        initial.bundle.open_mass = 0.0;
        beam.push_back(initial);
    } else {
        left[0] = 0.0;
    }
    GuardedSearch result;
    for (std::size_t time = 0; time < frame.timesteps; ++time) {
        std::map<std::string, Item> merged;
        std::size_t generated = 0;
        auto add = [&](const Item& item, std::size_t phase, double mass) {
            if (!std::isfinite(mass)) {
                return;
            }
            ++generated;
            auto [position, inserted] = merged.try_emplace(item.bundle.center, item);
            if (inserted) {
                position->second.bundle.open_mass = neg;
                std::fill(position->second.bundle.suffix_mass.begin(),
                          position->second.bundle.suffix_mass.end(), neg);
            }
            auto& destination = phase == 0 ? position->second.bundle.open_mass
                                           : position->second.bundle.suffix_mass[phase - 1];
            destination = log_add(destination, mass);
        };
        auto next_left = std::vector<double>(left.size(), neg);
        for (std::size_t j = 0; j < left.size(); ++j) {
            next_left[j] = log_add(next_left[j], left[j] + frame.stay_score);
            const auto mass = left[j] + emit(frame, time, left_states[j], window.left_guard[j]);
            if (j + 1 == left.size()) {
                add(initial, 0, mass);
            } else {
                next_left[j + 1] = log_add(next_left[j + 1], mass);
            }
        }
        for (const auto& item : beam) {
            const auto& bundle = item.bundle;
            add(item, 0, bundle.open_mass + frame.stay_score);
            if (bundle.center.size() < policy.max_center) {
                for (std::size_t base = 0; base < 4; ++base) {
                    const auto next =
                            advance(item.state, std::string(1, bases[base]), frame.state_length);
                    auto child = child_item(item, bases[base], next);
                    update_distances(child, bases[base], paths);
                    add(child, 0, bundle.open_mass + emit(frame, time, item.state, bases[base]));
                }
            } else if (std::isfinite(bundle.open_mass) &&
                       frame.timesteps - time > window.right_guard.size()) {
                result.center_bound_reached = true;
            }
            if (bundle.center.size() >= policy.min_center) {
                add(item, 1,
                    bundle.open_mass + emit(frame, time, item.state, window.right_guard.front()));
            }
            auto state = item.state;
            for (std::size_t j = 0; j < window.right_guard.size(); ++j) {
                state = advance(state, std::string(1, window.right_guard[j]), frame.state_length);
                add(item, j + 1, bundle.suffix_mass[j] + frame.stay_score);
                if (j + 1 < window.right_guard.size()) {
                    add(item, j + 2,
                        bundle.suffix_mass[j] +
                                emit(frame, time, state, window.right_guard[j + 1]));
                }
            }
        }
        std::vector<Item> candidates;
        for (auto& [key, item] : merged) {
            static_cast<void>(key);
            auto& bundle = item.bundle;
            const auto open_guide = bundle.center.size() == policy.max_center
                                            ? guide.q(time + 1, item.state, 0)
                                            : guide.b(time + 1, item.state);
            bundle.rank = bundle.open_mass + open_guide +
                          policy.context_weight * bundle.partial_potential;
            auto state = item.state;
            for (std::size_t j = 0; j < bundle.suffix_mass.size(); ++j) {
                state = advance(state, std::string(1, window.right_guard[j]), frame.state_length);
                bundle.rank = log_add(bundle.rank,
                                      bundle.suffix_mass[j] + guide.q(time + 1, state, j + 1) +
                                              policy.context_weight * bundle.terminal_potential);
            }
            // Impossible completion mass cannot consume a live beam slot.
            if (std::isfinite(bundle.rank)) {
                candidates.push_back(std::move(item));
            }
        }
        std::sort(candidates.begin(), candidates.end(), [](const Item& a, const Item& b) {
            return a.bundle.rank == b.bundle.rank ? a.bundle.center < b.bundle.center
                                                  : a.bundle.rank > b.bundle.rank;
        });
        const auto keep = std::min(policy.beam_width, candidates.size());
        GuardedExpansion step{time + 1,  generated, merged.size(), candidates.size() - keep,
                              next_left, {}};
        candidates.resize(keep);
        for (const auto& item : candidates) {
            step.retained.push_back(item.bundle);
        }
        result.pruned = result.pruned || step.pruned != 0;
        result.trace.push_back(std::move(step));
        beam = std::move(candidates);
        left = std::move(next_left);
    }
    for (const auto& item : beam) {
        const auto& bundle = item.bundle;
        if (std::isfinite(bundle.suffix_mass.back())) {
            auto state = advance(item.state, window.right_guard, frame.state_length);
            result.finalists.push_back({bundle.center, state, bundle.suffix_mass.back(),
                                        bundle.terminal_potential, bundle.rank});
        }
    }
    return result;
}
GuardedOutcome decode_guarded(const GuardedWindow& window, const GuardedPolicy& policy) {
    validate_guarded(window, policy);
    const auto paths = canonical_center_context(window.center_context);
    GuardedOutcome result;
    result.context_enabled = policy.context_weight != 0.0 && !paths.empty();
    result.escape = guarded_search(window, policy, false);
    auto score = [&](const std::string& center, bool contextual) {
        const auto signal = guarded_likelihood(window, center);
        const auto potential = contextual ? context_potential(center, paths, true) : 0.0;
        return Choice{center, signal, potential,
                      signal + (contextual ? policy.context_weight * potential : 0.0)};
    };
    result.native = score(window.native_center, false);
    require(std::isfinite(result.native.signal_likelihood), "native guarded sequence impossible");
    std::map<std::string, GuardedCandidate> candidates;
    candidates.emplace(window.native_center, GuardedCandidate{result.native, true, false, false});
    for (const auto& prefix : result.escape.finalists) {
        auto& candidate = candidates[prefix.sequence];
        candidate.choice = score(prefix.sequence, false);
        candidate.free_finalist = true;
    }
    result.reference_free = result.native;
    for (const auto& [center, candidate] : candidates) {
        static_cast<void>(center);
        if (preferred(candidate.choice, result.reference_free, window.native_center)) {
            result.reference_free = candidate.choice;
        }
    }
    result.final_rerank = result.reference_free;
    result.selected = result.reference_free;
    result.final_rerank_winner = result.reference_free;
    result.context_winner = result.reference_free;
    result.gate = "reference_free_fallback";
    result.final_rerank_gate = result.gate;
    if (result.context_enabled) {
        result.conditioned = guarded_search(window, policy, true);
        result.final_rerank_winner = score(window.native_center, true);
        for (auto& [center, candidate] : candidates) {
            candidate.choice = score(center, true);
            if (preferred(candidate.choice, result.final_rerank_winner, window.native_center)) {
                result.final_rerank_winner = candidate.choice;
            }
        }
        result.context_winner = result.final_rerank_winner;
        for (const auto& prefix : result.conditioned.finalists) {
            auto& candidate = candidates[prefix.sequence];
            candidate.choice = score(prefix.sequence, true);
            candidate.conditioned_finalist = true;
            if (preferred(candidate.choice, result.context_winner, window.native_center)) {
                result.context_winner = candidate.choice;
            }
        }
        const auto baseline = score(result.reference_free.sequence, true);
        auto gate = [&](const Choice& winner, Choice& selected, std::string& reason) {
            selected = result.reference_free;
            if (winner.signal_likelihood - baseline.signal_likelihood <
                -policy.maximum_signal_deficit) {
                reason = "signal_deficit_fallback";
            } else if (winner.objective - baseline.objective < policy.minimum_objective_margin) {
                reason = "objective_margin_fallback";
            } else {
                selected = winner;
                reason = "context_selected";
            }
        };
        gate(result.final_rerank_winner, result.final_rerank, result.final_rerank_gate);
        gate(result.context_winner, result.selected, result.gate);
        for (std::size_t i = 0; i < result.escape.trace.size(); ++i) {
            std::set<std::string> free_centers;
            std::set<std::string> contextual_centers;
            for (const auto& bundle : result.escape.trace[i].retained) {
                free_centers.insert(bundle.center);
            }
            for (const auto& bundle : result.conditioned.trace[i].retained) {
                contextual_centers.insert(bundle.center);
            }
            result.partial_search_differences +=
                    static_cast<std::size_t>(free_centers != contextual_centers);
        }
    } else {
        result.conditioned = result.escape;
        for (auto& [center, candidate] : candidates) {
            static_cast<void>(center);
            candidate.conditioned_finalist = candidate.free_finalist;
        }
    }
    if (result.escape.center_bound_reached || result.escape.finalists.empty()) {
        result.reference_free_abstained = true;
        result.final_rerank_abstained = true;
        result.abstained = true;
        result.gate = result.escape.center_bound_reached ? "center_bound_abstain"
                                                         : "no_eligible_finalist_abstain";
        result.final_rerank_gate = result.gate;
        result.reference_free = result.native;
        result.final_rerank = result.native;
        result.selected = result.native;
    } else if (result.conditioned.center_bound_reached || result.conditioned.finalists.empty()) {
        result.abstained = true;
        result.gate = result.conditioned.center_bound_reached ? "conditioned_center_bound_abstain"
                                                              : "conditioned_no_finalist_abstain";
        result.selected = result.native;
    }
    for (auto& [center, candidate] : candidates) {
        static_cast<void>(center);
        result.candidates.push_back(std::move(candidate));
    }
    return result;
}
std::string guarded_outcome_json(const GuardedOutcome& outcome) {
    std::ostringstream out;
    out << std::setprecision(17) << std::boolalpha
        << "{\"schema\":\"guarded-outcome/2\",\"native\":";
    choice_json(out, outcome.native);
    out << ",\"reference_free\":";
    choice_json(out, outcome.reference_free);
    out << ",\"final_rerank_winner\":";
    choice_json(out, outcome.final_rerank_winner);
    out << ",\"final_rerank\":";
    choice_json(out, outcome.final_rerank);
    out << ",\"context_winner\":";
    choice_json(out, outcome.context_winner);
    out << ",\"selected\":";
    choice_json(out, outcome.selected);
    out << ",\"context_enabled\":" << outcome.context_enabled
        << ",\"reference_free_abstained\":" << outcome.reference_free_abstained
        << ",\"final_rerank_abstained\":" << outcome.final_rerank_abstained
        << ",\"abstained\":" << outcome.abstained << ",\"gate\":\"" << outcome.gate
        << "\",\"final_rerank_gate\":\"" << outcome.final_rerank_gate
        << "\",\"partial_search_differences\":" << outcome.partial_search_differences
        << ",\"candidates\":[";
    for (std::size_t i = 0; i < outcome.candidates.size(); ++i) {
        if (i != 0) {
            out << ',';
        }
        const auto& candidate = outcome.candidates[i];
        out << "{\"choice\":";
        choice_json(out, candidate.choice);
        out << ",\"native\":" << candidate.native
            << ",\"free_finalist\":" << candidate.free_finalist
            << ",\"conditioned_finalist\":" << candidate.conditioned_finalist << '}';
    }
    out << "],\"reference_free_escape\":";
    search_json(out, outcome.escape);
    out << ",\"conditioned_search\":";
    search_json(out, outcome.conditioned);
    out << '}';
    return out.str();
}
}
