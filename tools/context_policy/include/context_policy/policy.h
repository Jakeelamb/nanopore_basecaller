#pragma once

#include <string>
#include <vector>

namespace context_policy {
enum class Mode { disabled, prior_none, fixed, adaptive };
struct Policy {
    Mode mode{Mode::adaptive};
    double maximum_context_weight{0.5};
    double maximum_neural_deficit{0.5};
    double minimum_objective_margin{0.0};
};
struct Location {
    std::string id;
    double support{};
};
struct Candidate {
    std::string id;
    std::string sequence;
    double neural_log_likelihood{};
    double context_cost{};
    std::vector<std::string> location_ids;
    std::vector<std::string> eligibility_reasons;
};
struct Batch {
    std::string native_sequence;
    std::string native_quality;
    std::string reference_free_candidate_id;
    std::string union_nn_candidate_id;
    std::vector<Location> locations;
    std::vector<Candidate> candidates;
};
struct Assessment {
    std::string candidate_id;
    double objective{};
    double neural_deficit{};
    std::vector<std::string> reasons;
};
struct Decision {
    std::string selected_candidate_id;
    std::string sequence;
    std::string quality;
    std::string reason;
    double context_weight{};
    std::vector<Assessment> assessments;
};
void validate(const Batch& batch, const Policy& policy);
Decision decide(const Batch& batch, const Policy& policy);
}
