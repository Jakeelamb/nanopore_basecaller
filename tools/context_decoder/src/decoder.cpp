#include "context_decoder/decoder.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <set>
#include <stdexcept>
#include <utility>

namespace context_decoder {
namespace {
constexpr double impossible = -std::numeric_limits<double>::infinity();
void require(bool ok, const char* message) {
    if (!ok) {
        throw std::invalid_argument(message);
    }
}
bool dna(const std::string& sequence) {
    return std::all_of(sequence.begin(), sequence.end(), [](char character) {
        const auto base = static_cast<unsigned char>(character);
        return base == 'A' || base == 'C' || base == 'G' || base == 'T';
    });
}
std::vector<std::size_t> distance_row(const std::string& a, const std::string& b) {
    std::vector<std::size_t> row(b.size() + 1);
    for (std::size_t j = 0; j < row.size(); ++j) {
        row[j] = j;
    }
    for (std::size_t i = 0; i < a.size(); ++i) {
        std::size_t diagonal = row[0];
        row[0] = i + 1;
        for (std::size_t j = 1; j < row.size(); ++j) {
            const auto previous = row[j];
            row[j] = std::min({row[j] + 1, row[j - 1] + 1,
                               diagonal + static_cast<std::size_t>(a[i] != b[j - 1])});
            diagonal = previous;
        }
    }
    return row;
}
std::vector<std::vector<double>> backward(const Frame& frame) {
    const auto states = std::size_t{1} << (2 * frame.state_length);
    const auto channels = states * 4;
    std::vector<std::vector<double>> guide(frame.timesteps + 1, std::vector<double>(states, 0.0));
    for (std::size_t t = frame.timesteps; t > 0; --t) {
        for (std::size_t state = 0; state < states; ++state) {
            double total = frame.stay_score + guide[t][state];
            for (const char character : std::string("ACGT")) {
                const auto base = static_cast<unsigned char>(character);
                std::size_t next = 0;
                const auto channel = transition(state, base, frame.state_length, next);
                total = log_add(total, frame.scores[(t - 1) * channels + channel] + guide[t][next]);
            }
            guide[t - 1][state] = total;
        }
    }
    return guide;
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
Choice rescore(const Frame& frame,
               const std::string& sequence,
               std::span<const std::string> paths,
               double weight) {
    const auto likelihood = sequence_likelihood(frame, sequence);
    const auto potential = weight == 0.0 ? 0.0 : context_potential(sequence, paths, true);
    return Choice{sequence, likelihood, potential, likelihood + weight * potential};
}
Choice best(const Frame& frame,
            const Search& primary,
            const Search* escape,
            std::span<const std::string> paths,
            double weight,
            const std::string& native) {
    auto winner = rescore(frame, native, paths, weight);
    std::set<std::string> candidates;
    for (const auto& prefix : primary.finalists) {
        candidates.insert(prefix.sequence);
    }
    if (escape != nullptr) {
        for (const auto& prefix : escape->finalists) {
            candidates.insert(prefix.sequence);
        }
    }
    for (const auto& sequence : candidates) {
        const auto candidate = rescore(frame, sequence, paths, weight);
        if (std::isfinite(candidate.signal_likelihood) && preferred(candidate, winner, native)) {
            winner = candidate;
        }
    }
    return winner;
}
}

void validate(const Frame& frame, const Policy& policy) {
    require(frame.state_length >= 1 && frame.state_length <= 4, "state length must be 1..4");
    require(frame.timesteps <= 256, "frame exceeds 256 timesteps");
    const auto states = std::size_t{1} << (2 * frame.state_length);
    require(frame.initial_state < states, "initial state out of bounds");
    require(frame.scores.size() == frame.timesteps * states * 4, "score shape mismatch");
    require(std::isfinite(frame.stay_score), "nonfinite stay score");
    require(std::all_of(frame.scores.begin(), frame.scores.end(),
                        [](double score) { return std::isfinite(score); }),
            "nonfinite score");
    require(policy.beam_width > 0 && policy.beam_width <= 512, "beam bound must be 1..512");
    require(policy.max_symbols <= 128 && policy.min_symbols <= policy.max_symbols,
            "invalid emitted length bounds");
    for (const double value :
         {policy.context_weight, policy.maximum_signal_deficit, policy.minimum_objective_margin}) {
        require(std::isfinite(value) && value >= 0.0, "invalid policy weight");
    }
}
std::vector<std::string> canonical_context(const RetrievedContext& context) {
    if (context.availability != Availability::usable) {
        return {};
    }
    std::set<std::string> unique;
    for (const auto& sequence : context.sequences) {
        require(!sequence.empty() && sequence.size() <= 128 && dna(sequence),
                "invalid context DNA");
        unique.insert(sequence);
    }
    require(!unique.empty() && unique.size() <= 32, "usable context must have 1..32 unique paths");
    return {unique.begin(), unique.end()};
}
double log_add(double a, double b) {
    if (a == impossible) {
        return b;
    }
    if (b == impossible) {
        return a;
    }
    const auto maximum = std::max(a, b);
    return maximum + std::log(std::exp(a - maximum) + std::exp(b - maximum));
}
std::size_t transition(std::size_t previous, unsigned char base, std::size_t k, std::size_t& next) {
    require(k >= 1 && k <= 4, "invalid transition state length");
    const auto states = std::size_t{1} << (2 * k);
    require(previous < states, "invalid predecessor state");
    const auto position = std::string("ACGT").find(static_cast<char>(base));
    require(position != std::string::npos, "noncanonical emitted base");
    next = ((previous << 2) & (states - 1)) | position;
    return 4 * next + (previous >> (2 * (k - 1)));
}
double sequence_likelihood(const Frame& frame, const std::string& sequence) {
    require(dna(sequence), "invalid sequence DNA");
    std::vector<std::size_t> channels;
    std::size_t state = frame.initial_state;
    for (const char character : sequence) {
        const auto base = static_cast<unsigned char>(character);
        std::size_t next = 0;
        channels.push_back(transition(state, base, frame.state_length, next));
        state = next;
    }
    std::vector<double> dp(sequence.size() + 1, impossible);
    dp[0] = 0.0;
    const auto width = std::size_t{1} << (2 * (frame.state_length + 1));
    for (std::size_t t = 0; t < frame.timesteps; ++t) {
        for (std::size_t j = sequence.size(); j > 0; --j) {
            dp[j] = log_add(dp[j] + frame.stay_score,
                            dp[j - 1] + frame.scores[t * width + channels[j - 1]]);
        }
        dp[0] += frame.stay_score;
    }
    return dp.back();
}
std::size_t edit_distance(const std::string& a, const std::string& b) {
    return distance_row(a, b).back();
}
double context_potential(const std::string& prefix,
                         std::span<const std::string> paths,
                         bool terminal) {
    require(!paths.empty(), "missing context paths");
    auto closest = std::numeric_limits<std::size_t>::max();
    for (const auto& sequence : paths) {
        const auto row = distance_row(prefix, sequence);
        const auto distance = terminal ? row.back() : *std::min_element(row.begin(), row.end());
        closest = std::min(closest, distance);
    }
    return -static_cast<double>(closest);
}
Search search(const Frame& frame,
              std::span<const std::string> paths,
              const Policy& policy,
              bool use_context) {
    validate(frame, policy);
    const bool enabled = use_context && policy.context_weight != 0.0 && !paths.empty();
    const auto guides = backward(frame);
    const auto channels = std::size_t{1} << (2 * (frame.state_length + 1));
    std::vector<Prefix> beam{{"", frame.initial_state, 0.0, 0.0, 0.0}};
    Search result;
    for (std::size_t t = 0; t < frame.timesteps; ++t) {
        std::map<std::string, Prefix> merged;
        std::size_t generated = 0;
        auto add = [&](std::string sequence, std::size_t state, double score) {
            ++generated;
            auto [iterator, inserted] =
                    merged.try_emplace(sequence, Prefix{sequence, state, score, 0.0, 0.0});
            if (!inserted) {
                iterator->second.signal_mass = log_add(iterator->second.signal_mass, score);
            }
        };
        for (const auto& prefix : beam) {
            add(prefix.sequence, prefix.state, prefix.signal_mass + frame.stay_score);
            if (prefix.sequence.size() == policy.max_symbols) {
                result.symbol_bound_reached = true;
                continue;
            }
            for (const char character : std::string("ACGT")) {
                const auto base = static_cast<unsigned char>(character);
                std::size_t next = 0;
                const auto channel = transition(prefix.state, base, frame.state_length, next);
                add(prefix.sequence + static_cast<char>(base), next,
                    prefix.signal_mass + frame.scores[t * channels + channel]);
            }
        }
        std::vector<Prefix> candidates;
        candidates.reserve(merged.size());
        for (auto& [sequence, prefix] : merged) {
            static_cast<void>(sequence);
            prefix.context_potential =
                    enabled ? context_potential(prefix.sequence, paths, t + 1 == frame.timesteps)
                            : 0.0;
            prefix.rank = prefix.signal_mass + guides[t + 1][prefix.state] +
                          policy.context_weight * prefix.context_potential;
            candidates.push_back(std::move(prefix));
        }
        std::sort(candidates.begin(), candidates.end(), [](const Prefix& a, const Prefix& b) {
            return a.rank == b.rank ? a.sequence < b.sequence : a.rank > b.rank;
        });
        const auto keep = std::min(policy.beam_width, candidates.size());
        Expansion expansion{t, generated, merged.size(), candidates.size() - keep, {}};
        expansion.retained_prefixes.reserve(keep);
        for (std::size_t i = 0; i < keep; ++i) {
            expansion.retained_prefixes.push_back(candidates[i].sequence);
        }
        std::sort(expansion.retained_prefixes.begin(), expansion.retained_prefixes.end());
        result.pruned = result.pruned || expansion.pruned != 0;
        result.trace.push_back(std::move(expansion));
        candidates.resize(keep);
        beam = std::move(candidates);
    }
    for (auto& prefix : beam) {
        if (prefix.sequence.size() >= policy.min_symbols) {
            prefix.context_potential =
                    enabled ? context_potential(prefix.sequence, paths, true) : 0.0;
            prefix.rank = prefix.signal_mass + policy.context_weight * prefix.context_potential;
            result.finalists.push_back(std::move(prefix));
        }
    }
    return result;
}
Outcome decode(const Frame& frame,
               const RetrievedContext& context,
               const Policy& policy,
               const std::string& native) {
    validate(frame, policy);
    require(native.size() <= policy.max_symbols && dna(native), "invalid native control");
    const auto paths = canonical_context(context);
    Outcome result;
    result.escape = search(frame, {}, policy, false);
    result.native = rescore(frame, native, {}, 0.0);
    require(std::isfinite(result.native.signal_likelihood), "native sequence impossible");
    result.reference_free = best(frame, result.escape, nullptr, {}, 0.0, native);
    result.context_enabled =
            policy.context_weight != 0.0 && context.availability == Availability::usable;
    if (!result.context_enabled) {
        result.conditioned = result.escape;
        result.context_winner = result.reference_free;
        result.selected = result.reference_free;
        result.gate = "reference_free_fallback";
    } else {
        result.conditioned = search(frame, paths, policy, true);
        result.context_winner = best(frame, result.conditioned, &result.escape, paths,
                                     policy.context_weight, native);
        const auto baseline =
                rescore(frame, result.reference_free.sequence, paths, policy.context_weight);
        const auto delta = result.context_winner.signal_likelihood - baseline.signal_likelihood;
        const auto margin = result.context_winner.objective - baseline.objective;
        if (delta < -policy.maximum_signal_deficit) {
            result.selected = result.reference_free;
            result.gate = "signal_deficit_fallback";
        } else if (margin < policy.minimum_objective_margin) {
            result.selected = result.reference_free;
            result.gate = "objective_margin_fallback";
        } else {
            result.selected = result.context_winner;
            result.gate = "context_selected";
        }
        for (std::size_t t = 0; t < result.escape.trace.size(); ++t) {
            if (result.escape.trace[t].retained_prefixes !=
                result.conditioned.trace[t].retained_prefixes) {
                ++result.partial_search_differences;
            }
        }
    }
    result.different_from_native = result.selected.sequence != native;
    result.different_from_reference_free =
            result.selected.sequence != result.reference_free.sequence;
    if (result.escape.symbol_bound_reached || result.conditioned.symbol_bound_reached) {
        result.abstained = true;
        result.gate = "symbol_bound_abstain";
        result.selected = result.native;
        result.different_from_native = false;
        result.different_from_reference_free =
                result.native.sequence != result.reference_free.sequence;
    } else if (result.escape.finalists.empty()) {
        result.abstained = true;
        result.gate = "no_eligible_finalist_abstain";
        result.selected = result.native;
        result.different_from_native = false;
        result.different_from_reference_free =
                result.native.sequence != result.reference_free.sequence;
    }
    return result;
}
}
