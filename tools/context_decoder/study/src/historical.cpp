#include "context_study/candidate.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace context_study {
void require(bool condition, const std::string &message) {
    if (!condition)
        throw std::invalid_argument(message);
}
bool dna(const std::string &sequence) {
    return sequence.size() <= 4096 && std::all_of(sequence.begin(), sequence.end(), [](char base) {
               return base == 'A' || base == 'C' || base == 'G' || base == 'T';
           });
}
std::string oriented(const std::string &sequence, bool reverse) {
    if (!reverse)
        return sequence;
    auto result = sequence;
    std::reverse(result.begin(), result.end());
    for (auto &base : result) {
        switch (base) {
        case 'A':
            base = 'T';
            break;
        case 'C':
            base = 'G';
            break;
        case 'G':
            base = 'C';
            break;
        case 'T':
            base = 'A';
            break;
        default:
            throw std::invalid_argument("noncanonical oriented DNA");
        }
    }
    return result;
}
std::size_t distance(const std::string &query, const std::string &reference) {
    std::vector<std::size_t> row(reference.size() + 1);
    for (std::size_t j = 0; j < row.size(); ++j)
        row[j] = j;
    for (std::size_t i = 0; i < query.size(); ++i) {
        auto diagonal = row[0];
        row[0] = i + 1;
        for (std::size_t j = 1; j < row.size(); ++j) {
            const auto old = row[j];
            row[j] = std::min({row[j] + 1, row[j - 1] + 1,
                               diagonal + static_cast<std::size_t>(query[i] != reference[j - 1])});
            diagonal = old;
        }
    }
    return row.back();
}
Replay replay(const CandidateCase &input) {
    auto score = [&](const Candidate &candidate, bool contextual) {
        require(candidate.log_mass.has_value(), "historical candidate is unscored");
        double potential = 0;
        if (contextual) {
            auto minimum = std::numeric_limits<std::size_t>::max();
            for (const auto &path : input.paths)
                minimum = std::min(minimum, distance(candidate.sequence, path));
            potential = -static_cast<double>(minimum);
        }
        return Choice{candidate.sequence,
                      candidate.log_mass->value,
                      potential,
                      candidate.log_mass->value + 0.5 * potential,
                      ".",
                      false};
    };
    auto preferred = [&](const Choice &a, const Choice &b) {
        if (a.objective != b.objective)
            return a.objective > b.objective;
        if ((a.sequence == input.native) != (b.sequence == input.native))
            return a.sequence == input.native;
        return a.sequence < b.sequence;
    };
    const bool enabled = input.availability == "usable";
    Replay result;
    result["native"] = score(input.candidates.at(input.native), false);
    auto free = result.at("native");
    for (const auto &[sequence, candidate] : input.candidates) {
        static_cast<void>(sequence);
        if ((candidate.origins & (native_origin | escape_origin)) != 0) {
            const auto value = score(candidate, false);
            if (preferred(value, free))
                free = value;
        }
    }
    result["reference_free"] = free;
    result["final_rerank_winner"] = free;
    result["context_winner"] = free;
    result["final_rerank"] = free;
    result["selected"] = free;
    result["final_rerank"].gate = "reference_free_fallback";
    result["selected"].gate = "reference_free_fallback";
    if (enabled) {
        auto final = score(input.candidates.at(input.native), true);
        for (const auto &[sequence, candidate] : input.candidates) {
            static_cast<void>(sequence);
            if ((candidate.origins & (native_origin | escape_origin)) != 0) {
                auto value = score(candidate, true);
                if (preferred(value, final))
                    final = value;
            }
        }
        auto context = final;
        for (const auto &[sequence, candidate] : input.candidates) {
            static_cast<void>(sequence);
            if ((candidate.origins & conditioned_origin) != 0) {
                auto value = score(candidate, true);
                if (preferred(value, context))
                    context = value;
            }
        }
        result["final_rerank_winner"] = final;
        result["context_winner"] = context;
        const auto baseline = score(input.candidates.at(free.sequence), true);
        auto gate = [&](const Choice &winner) {
            auto selected = free;
            if (winner.log_mass - baseline.log_mass < -0.5)
                selected.gate = "signal_deficit_fallback";
            else if (winner.objective - baseline.objective < 0.5)
                selected.gate = "objective_margin_fallback";
            else {
                selected = winner;
                selected.gate = "context_selected";
            }
            return selected;
        };
        result["final_rerank"] = gate(final);
        result["selected"] = gate(context);
    }
    if (input.escape_capped || input.escape_empty) {
        for (const auto *role : {"reference_free", "final_rerank", "selected"}) {
            result[role] = result.at("native");
            result[role].abstained = true;
        }
        const auto reason =
            input.escape_capped ? "center_bound_abstain" : "no_eligible_finalist_abstain";
        result["final_rerank"].gate = reason;
        result["selected"].gate = reason;
    } else if (input.conditioned_capped || input.conditioned_empty) {
        result["selected"] = result.at("native");
        result["selected"].abstained = true;
        result["selected"].gate = input.conditioned_capped ? "conditioned_center_bound_abstain"
                                                           : "conditioned_no_finalist_abstain";
    }
    return result;
}
void verify_replay(const CandidateCase &input, const Replay &result) {
    require(input.saved.size() == roles.size(), "six saved historical choices required");
    for (const auto *role : roles) {
        const auto &expected = input.saved.at(role);
        const auto &actual = result.at(role);
        require(expected.sequence == actual.sequence && expected.gate == actual.gate &&
                    expected.abstained == actual.abstained,
                input.id + ": historical choice/gate mismatch " + role);
        require(std::abs(expected.log_mass - actual.log_mass) <= 1e-11 &&
                    std::abs(expected.potential - actual.potential) <= 1e-11 &&
                    std::abs(expected.objective - actual.objective) <= 1e-11,
                input.id + ": historical numeric mismatch " + role);
    }
}
}
