#include "context_policy/policy.h"

#include <algorithm>
#include <cmath>
#include <set>
#include <stdexcept>

namespace context_policy {
namespace {
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
bool preferred(const Candidate& a, double a_score, const Candidate& b, double b_score,
               const std::string& native) {
    if (a_score != b_score) {
        return a_score > b_score;
    }
    if ((a.sequence == native) != (b.sequence == native)) {
        return a.sequence == native;
    }
    return a.sequence != b.sequence ? a.sequence < b.sequence : a.id < b.id;
}
const Candidate& neural_winner(const Batch& batch) {
    const Candidate* best = &batch.candidates.front();
    for (const auto& candidate : batch.candidates) {
        if (preferred(candidate, candidate.neural_log_likelihood, *best,
                      best->neural_log_likelihood, batch.native_sequence)) {
            best = &candidate;
        }
    }
    return *best;
}
}
void validate(const Batch& batch, const Policy& policy) {
    require(!batch.candidates.empty(), "empty candidate union");
    require(batch.native_sequence.size() == batch.native_quality.size(), "native SEQ/Q mismatch");
    require(dna(batch.native_sequence), "non-DNA native sequence");
    require(std::all_of(batch.native_quality.begin(), batch.native_quality.end(), [](char q) {
                return q >= '!' && q <= '~';
            }), "invalid native quality");
    require(std::isfinite(policy.maximum_context_weight) && policy.maximum_context_weight >= 0.0 &&
                policy.maximum_context_weight <= 0.5, "invalid context weight bound");
    require(std::isfinite(policy.maximum_neural_deficit) && policy.maximum_neural_deficit >= 0.0 &&
                policy.maximum_neural_deficit <= 0.5, "invalid neural budget");
    require(std::isfinite(policy.minimum_objective_margin) && policy.minimum_objective_margin >= 0.0,
            "invalid objective margin");
    if (policy.mode == Mode::fixed) {
        require(policy.maximum_context_weight == 0.5 && policy.maximum_neural_deficit == 0.5 &&
                    policy.minimum_objective_margin == 0.5, "fixed gates must remain 0.5");
    }
    std::set<std::string> location_ids;
    for (const auto& location : batch.locations) {
        require(!location.id.empty() && location_ids.insert(location.id).second,
                "duplicate or empty location ID");
        require(std::isfinite(location.support) && location.support >= 0.0 && location.support <= 1.0,
                "invalid location support");
    }
    std::set<std::string> ids;
    std::set<std::string> sequences;
    bool native_present = false;
    for (const auto& candidate : batch.candidates) {
        require(!candidate.id.empty() && ids.insert(candidate.id).second, "duplicate candidate ID");
        require(dna(candidate.sequence) && sequences.insert(candidate.sequence).second,
                "duplicate or non-DNA candidate sequence");
        require(std::isfinite(candidate.neural_log_likelihood), "nonfinite neural likelihood");
        require(std::isfinite(candidate.context_cost) && candidate.context_cost >= 0.0,
                "invalid context cost");
        std::set<std::string> seen;
        for (const auto& id : candidate.location_ids) {
            require(location_ids.contains(id) && seen.insert(id).second,
                    "foreign or duplicate candidate location");
        }
        require(seen == location_ids, "candidate context scoring domain differs from batch locations");
        require(!batch.locations.empty() || candidate.context_cost == 0.0,
                "nonzero cost with empty context");
        require(std::all_of(candidate.eligibility_reasons.begin(), candidate.eligibility_reasons.end(),
                            [](const auto& value) { return !value.empty(); }),
                "empty eligibility reason");
        native_present = native_present || candidate.sequence == batch.native_sequence;
    }
    require(native_present, "native candidate absent from union");
    require(ids.contains(batch.reference_free_candidate_id), "genuine free candidate absent");
    require(neural_winner(batch).id == batch.union_nn_candidate_id,
            "named union NN candidate is not actual union neural winner");
}
Decision decide(const Batch& batch, const Policy& policy) {
    validate(batch, policy);
    Decision result;
    if (policy.mode == Mode::disabled) {
        const auto native = std::find_if(batch.candidates.begin(), batch.candidates.end(),
                                        [&](const auto& item) {
                                            return item.sequence == batch.native_sequence;
                                        });
        result.selected_candidate_id = native->id;
        result.sequence = batch.native_sequence;
        result.quality = batch.native_quality;
        result.reason = "disabled_identity";
        return result;
    }
    const auto& free = *std::find_if(batch.candidates.begin(), batch.candidates.end(),
        [&](const auto& item) { return item.id == batch.reference_free_candidate_id; });
    const Candidate* selected = &free;
    result.reason = "reference_free_escape";
    if (policy.mode == Mode::prior_none) {
        selected = &neural_winner(batch);
        result.reason = "prior_none_neural_winner";
    } else if (!batch.locations.empty()) {
        double support = 1.0;
        for (const auto& location : batch.locations) {
            support = std::min(support, location.support);
        }
        result.context_weight = policy.mode == Mode::fixed ? 0.5
                                                          : policy.maximum_context_weight * support;
        const double baseline = free.neural_log_likelihood - result.context_weight * free.context_cost;
        require(std::isfinite(baseline), "nonfinite baseline objective");
        const Candidate* top = &free;
        double top_score = baseline;
        for (const auto& candidate : batch.candidates) {
            const double objective = candidate.neural_log_likelihood -
                                     result.context_weight * candidate.context_cost;
            const double deficit = free.neural_log_likelihood - candidate.neural_log_likelihood;
            require(std::isfinite(objective) && std::isfinite(deficit), "nonfinite policy arithmetic");
            Assessment assessment{candidate.id, objective, deficit, candidate.eligibility_reasons};
            if (deficit > policy.maximum_neural_deficit) {
                assessment.reasons.push_back("neural_budget_exceeded");
            }
            const double improvement = objective - baseline;
            require(std::isfinite(improvement), "nonfinite objective improvement");
            if (improvement < policy.minimum_objective_margin ||
                (candidate.id != free.id && improvement <= 0.0)) {
                assessment.reasons.push_back("objective_margin_not_met");
            }
            std::sort(assessment.reasons.begin(), assessment.reasons.end());
            if (preferred(candidate, objective, *top, top_score, batch.native_sequence)) {
                top = &candidate;
                top_score = objective;
            }
            result.assessments.push_back(std::move(assessment));
        }
        if (result.context_weight > 0.0) {
            for (const auto& assessment : result.assessments) {
                const auto& candidate = *std::find_if(batch.candidates.begin(), batch.candidates.end(),
                    [&](const auto& item) { return item.id == assessment.candidate_id; });
                if (!assessment.reasons.empty() ||
                    (policy.mode == Mode::fixed && candidate.id != top->id)) {
                    continue;
                }
                const double selected_objective = selected->neural_log_likelihood -
                                                  result.context_weight * selected->context_cost;
                if (preferred(candidate, assessment.objective, *selected, selected_objective,
                              batch.native_sequence)) {
                    selected = &candidate;
                    result.reason = policy.mode == Mode::fixed ? "fixed_context_selected"
                                                              : "adaptive_eligible_selected";
                }
            }
        }
        std::sort(result.assessments.begin(), result.assessments.end(), [](const auto& a, const auto& b) {
            return a.candidate_id < b.candidate_id;
        });
    } else {
        result.reason = "empty_context_neural_winner";
    }
    result.selected_candidate_id = selected->id;
    result.sequence = selected->sequence;
    result.quality = selected->sequence == batch.native_sequence ? batch.native_quality
                                                               : std::string(selected->sequence.size(), '!');
    return result;
}
}
