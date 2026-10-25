#include "context_uncertainty/uncertainty.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
#include <tuple>
#include <utility>

namespace context_uncertainty {
namespace {
constexpr double impossible = -std::numeric_limits<double>::infinity();
double entropy_term(double value) {
    return value > 0 ? -value * std::log(value) : 0;
}
std::vector<std::optional<std::size_t>> mapping(const Parent &parent, std::size_t length) {
    std::vector<std::optional<std::size_t>> result;
    std::size_t reference = parent.reference_start, count{};
    for (const char character : parent.cigar) {
        if (character >= '0' && character <= '9') {
            require(count <= (std::numeric_limits<std::size_t>::max() - 9) / 10,
                    "CIGAR integer overflow");
            count = count * 10 + static_cast<std::size_t>(character - '0');
            continue;
        }
        require(count > 0, "CIGAR operation lacks count");
        if (character == '=' || character == 'X' || character == 'M') {
            require(count <= length && result.size() <= length - count,
                    "CIGAR exceeds native parent");
            for (std::size_t i = 0; i < count; ++i)
                result.emplace_back(reference++);
        } else if (character == 'I' || character == 'S') {
            require(count <= length && result.size() <= length - count,
                    "CIGAR insertion exceeds native parent");
            result.insert(result.end(), count, std::nullopt);
        } else if (character == 'D' || character == 'N') {
            require(count <= std::numeric_limits<std::size_t>::max() - reference,
                    "CIGAR reference overflow");
            reference += count;
        } else {
            require(character == 'H' || character == 'P', "Unsupported CIGAR operation");
        }
        count = 0;
    }
    require(count == 0 && result.size() == length, "Native CIGAR/parent length differs");
    if (parent.reverse)
        std::reverse(result.begin(), result.end());
    return result;
}
bool contiguous(const std::vector<std::optional<std::size_t>> &values, std::size_t a, std::size_t b,
                bool reverse) {
    if (a >= b || b > values.size())
        return false;
    for (std::size_t i = a; i < b; ++i) {
        if (!values[i])
            return false;
        if (i > a) {
            const auto left = *values[i - 1], right = *values[i];
            if ((!reverse && (right <= left || right - left != 1)) ||
                (reverse && (left <= right || left - right != 1)))
                return false;
        }
    }
    return true;
}
}
double log_add(double a, double b) {
    if (a == impossible)
        return b;
    if (b == impossible)
        return a;
    const auto high = std::max(a, b);
    return high + std::log1p(std::exp(std::min(a, b) - high));
}
double half(std::uint16_t value) {
    const auto exponent = static_cast<int>((value >> 10U) & 31U);
    require(exponent != 31, "Nonfinite binary16 score");
    const auto fraction = static_cast<double>(value & 1023U);
    const auto magnitude =
        exponent == 0 ? std::ldexp(fraction, -24) : std::ldexp(1 + fraction / 1024, exponent - 15);
    return (value & 0x8000U) == 0 ? magnitude : -magnitude;
}
std::size_t transition(std::size_t previous, std::size_t base, std::size_t k, std::size_t &next) {
    require(k >= 1 && k <= 4 && base < 4, "Invalid CRF transition geometry");
    const auto states = std::size_t{1} << (2 * k);
    require(previous < states, "CRF predecessor outside state space");
    next = ((previous << 2U) & (states - 1)) | base;
    return 4 * next + (previous >> (2 * (k - 1)));
}
Posterior posterior(const Frame &frame, bool retain_edges) {
    require(frame.state_length >= 1 && frame.state_length <= 4 && frame.timesteps > 0 &&
                frame.timesteps <= 4096 && std::isfinite(frame.stay),
            "Posterior frame bounds differ");
    const auto states = std::size_t{1} << (2 * frame.state_length), channels = states * 4;
    require(frame.scores.size() == frame.timesteps * channels &&
                std::all_of(frame.scores.begin(), frame.scores.end(),
                            [](double x) { return std::isfinite(x); }),
            "Posterior score shape/nonfinite input");
    std::vector<std::array<std::pair<std::size_t, std::size_t>, 4>> edges(states);
    for (std::size_t state = 0; state < states; ++state)
        for (std::size_t base = 0; base < 4; ++base) {
            std::size_t next{};
            const auto channel = transition(state, base, frame.state_length, next);
            edges[state][base] = {next, channel};
        }
    std::vector<double> alpha((frame.timesteps + 1) * states, impossible), scales(frame.timesteps);
    std::fill_n(alpha.begin(), states, -std::log(static_cast<double>(states)));
    for (std::size_t t = 0; t < frame.timesteps; ++t) {
        auto *next_row = alpha.data() + (t + 1) * states;
        for (std::size_t state = 0; state < states; ++state) {
            const auto mass = alpha[t * states + state];
            next_row[state] = log_add(next_row[state], mass + frame.stay);
            for (std::size_t base = 0; base < 4; ++base) {
                const auto [next, channel] = edges[state][base];
                next_row[next] =
                    log_add(next_row[next], mass + frame.scores[t * channels + channel]);
            }
        }
        double scale = impossible;
        for (std::size_t state = 0; state < states; ++state)
            scale = log_add(scale, next_row[state]);
        require(std::isfinite(scale), "Posterior partition is not finite");
        scales[t] = scale;
        for (std::size_t state = 0; state < states; ++state)
            next_row[state] -= scale;
    }
    Posterior result;
    result.log_partition = std::accumulate(scales.begin(), scales.end(), 0.0);
    require(std::isfinite(result.log_partition), "Accumulated posterior partition overflow");
    result.timesteps.resize(frame.timesteps);
    if (retain_edges)
        result.edge_probabilities.resize(frame.timesteps * states * 5);
    std::vector<double> backward(states, 0), previous(states);
    const auto log_four = std::log(4.0), log_two = std::log(2.0);
    for (std::size_t cursor = frame.timesteps; cursor > 0; --cursor) {
        const auto t = cursor - 1;
        auto &observed = result.timesteps[t];
        std::array<double, 4> log_emitted{impossible, impossible, impossible, impossible};
        double log_stay = impossible;
        for (std::size_t state = 0; state < states; ++state) {
            const auto stay = frame.stay + backward[state];
            auto mass = stay;
            const auto stay_mass = alpha[t * states + state] + stay - scales[t];
            log_stay = log_add(log_stay, stay_mass);
            if (retain_edges)
                result.edge_probabilities[(t * states + state) * 5 + 4] = std::exp(stay_mass);
            for (std::size_t base = 0; base < 4; ++base) {
                const auto [next, channel] = edges[state][base];
                const auto value = frame.scores[t * channels + channel] + backward[next];
                mass = log_add(mass, value);
                const auto edge_mass = alpha[t * states + state] + value - scales[t];
                log_emitted[base] = log_add(log_emitted[base], edge_mass);
                if (retain_edges)
                    result.edge_probabilities[(t * states + state) * 5 + base] =
                        std::exp(edge_mass);
            }
            previous[state] = mass - scales[t];
        }
        observed.stay = std::exp(log_stay);
        double log_emission = impossible;
        for (std::size_t base = 0; base < 4; ++base) {
            observed.emitted[base] = std::exp(log_emitted[base]);
            log_emission = log_add(log_emission, log_emitted[base]);
        }
        const auto emission =
            std::accumulate(observed.emitted.begin(), observed.emitted.end(), 0.0);
        require(std::abs(emission + observed.stay - 1) <= 1e-8 && std::isfinite(log_emission) &&
                    observed.stay >= 0 && observed.stay <= 1 + 1e-8,
                "Posterior transition probability does not conserve mass");
        for (const auto probability : log_emitted)
            observed.conditional_entropy += entropy_term(std::exp(probability - log_emission));
        const auto stay_probability = std::clamp(observed.stay, 0.0, 1.0);
        observed.stay_entropy = entropy_term(stay_probability) + entropy_term(1 - stay_probability);
        observed.uncertainty =
            0.5 * (observed.conditional_entropy / log_four + observed.stay_entropy / log_two);
        require(observed.uncertainty >= -1e-12 && observed.uncertainty <= 1 + 1e-8,
                "Uncertainty outside declared range");
        backward.swap(previous);
    }
    return result;
}
std::vector<Proposal> select(std::vector<Proposal> proposals, std::size_t maximum) {
    require(maximum > 0 && maximum <= 512, "Nomination cap must be 1..512");
    require(std::all_of(proposals.begin(), proposals.end(),
                        [](const auto &candidate) {
                            return std::isfinite(candidate.uncertainty) &&
                                   candidate.read_end > candidate.read_begin;
                        }),
            "Invalid proposal score/interval");
    std::sort(proposals.begin(), proposals.end(), [](const auto &a, const auto &b) {
        if (a.uncertainty != b.uncertainty)
            return a.uncertainty > b.uncertainty;
        return std::tie(a.tie, a.parent, a.read_begin, a.chunk) <
               std::tie(b.tie, b.parent, b.read_begin, b.chunk);
    });
    std::vector<Proposal> selected;
    for (auto &candidate : proposals) {
        const auto overlap = std::any_of(selected.begin(), selected.end(), [&](const auto &old) {
            return old.parent == candidate.parent && candidate.read_begin < old.read_end &&
                   old.read_begin < candidate.read_end;
        });
        if (!overlap)
            selected.push_back(std::move(candidate));
        if (selected.size() == maximum)
            break;
    }
    return selected;
}
std::vector<Proposal> nominate(const Frame &frame, const Posterior &probabilities,
                               const Parent &parent, const Chunk &chunk, const Fields &meta,
                               const Fields &whole,
                               std::map<std::string, std::size_t> &exclusions) {
    require(parent.eligible && probabilities.timesteps.size() == frame.timesteps,
            "Unqualified parent/posterior nomination");
    const auto &sequence = meta.at("SEQ"), &quality = meta.at("Q"), &moves = meta.at("MOVES");
    require(
        moves.size() == frame.timesteps && sequence.size() == quality.size() &&
            std::all_of(moves.begin(), moves.end(), [](char x) { return x == '0' || x == '1'; }),
        "Native chunk sequence/moves invalid");
    std::vector<std::size_t> emissions;
    for (std::size_t t = 0; t < moves.size(); ++t)
        if (moves[t] == '1')
            emissions.push_back(t);
    require(
        emissions.size() == sequence.size() && chunk.chunk_end <= emissions.size() &&
            chunk.parent_end <= whole.at("SEQ").size() &&
            sequence.substr(chunk.chunk_start, chunk.chunk_end - chunk.chunk_start) ==
                whole.at("SEQ").substr(chunk.parent_start, chunk.parent_end - chunk.parent_start) &&
            quality.substr(chunk.chunk_start, chunk.chunk_end - chunk.chunk_start) ==
                whole.at("Q").substr(chunk.parent_start, chunk.parent_end - chunk.parent_start),
        "Retained chunk/parent SEQ/Q differs");
    const auto coordinates = mapping(parent, whole.at("SEQ").size());
    std::vector<double> uncertainty(frame.timesteps + 1), base_entropy(frame.timesteps + 1),
        stay_entropy(frame.timesteps + 1);
    for (std::size_t t = 0; t < frame.timesteps; ++t) {
        uncertainty[t + 1] = uncertainty[t] + probabilities.timesteps[t].uncertainty;
        base_entropy[t + 1] = base_entropy[t] + probabilities.timesteps[t].conditional_entropy;
        stay_entropy[t + 1] = stay_entropy[t] + probabilities.timesteps[t].stay_entropy;
    }
    std::vector<Proposal> proposals;
    for (std::size_t begin = chunk.chunk_start; begin < chunk.chunk_end; ++begin) {
        const auto end = begin + 21;
        if (begin < 14 || end > chunk.chunk_end || begin < chunk.chunk_start + 14 ||
            end + 20 >= chunk.chunk_end || end + 20 >= emissions.size()) {
            ++exclusions["initial_context_or_retained_expanded_guard"];
            continue;
        }
        const auto t_begin = emissions[begin - 10], t_end = emissions[end + 20];
        if (t_begin < chunk.retained_start || t_end > chunk.retained_end || t_end - t_begin > 256) {
            ++exclusions["expanded_timestep_bound"];
            continue;
        }
        const auto read_begin = chunk.parent_start + begin - chunk.chunk_start,
                   read_end = read_begin + 21;
        const auto a = read_begin - 10, b = read_end + 10;
        if (!contiguous(coordinates, a, a + 10, parent.reverse) ||
            !contiguous(coordinates, b - 10, b + 10, parent.reverse)) {
            ++exclusions["native_guard_gapped_or_clipped"];
            continue;
        }
        const auto first = *coordinates[a], last = *coordinates[b - 1];
        const auto ref_begin = std::min(first, last), ref_end = std::max(first, last) + 1;
        if (ref_end - ref_begin <= 20) {
            ++exclusions["empty_reference_core"];
            continue;
        }
        const auto expanded_first = *coordinates[a], expanded_last = *coordinates[b + 9];
        const auto core_t_begin = emissions[begin], core_t_end = emissions[end];
        const auto duration = static_cast<double>(core_t_end - core_t_begin);
        require(duration > 0, "Native center has empty timestep interval");
        const auto score = (uncertainty[core_t_end] - uncertainty[core_t_begin]) / duration;
        const auto identity =
            parent.id + '\n' + std::to_string(read_begin) + '\n' + chunk.id + '\n';
        proposals.push_back({chunk.id,
                             parent.id,
                             parent.contig,
                             sequence.substr(begin, 21),
                             sha256("uncertainty-v1\n" + identity),
                             chunk.index,
                             begin,
                             end,
                             read_begin,
                             read_end,
                             t_begin,
                             t_end,
                             std::min(expanded_first, expanded_last),
                             std::max(expanded_first, expanded_last) + 1,
                             ref_begin + 10,
                             ref_end - 10,
                             parent.reverse,
                             score,
                             (base_entropy[core_t_end] - base_entropy[core_t_begin]) / duration,
                             (stay_entropy[core_t_end] - stay_entropy[core_t_begin]) / duration});
    }
    return select(std::move(proposals), 512);
}
}
