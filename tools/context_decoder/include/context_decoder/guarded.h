#pragma once

#include "context_decoder/decoder.h"

namespace context_decoder {

struct GuardedWindow {
    Frame scores;
    std::string left_guard;
    std::string right_guard;
    std::string native_center;
    RetrievedContext center_context;
};

struct GuardedPolicy {
    std::size_t beam_width{128};
    std::size_t min_center{0};
    std::size_t max_center{108};
    double context_weight{0.5};
    double maximum_signal_deficit{0.5};
    double minimum_objective_margin{0.5};
};

struct GuardedBundle {
    std::string center;
    double open_mass{};
    // Index j-1 means exactly j required right-guard bases have emitted.
    std::vector<double> suffix_mass;
    double partial_potential{};
    double terminal_potential{};
    double rank{};
};

struct GuardedExpansion {
    std::size_t timestep{};
    std::size_t generated{};
    std::size_t merged{};
    std::size_t pruned{};
    std::vector<double> left_mass;
    std::vector<GuardedBundle> retained;
};

struct GuardedSearch {
    std::vector<Prefix> finalists;
    std::vector<GuardedExpansion> trace;
    bool pruned{};
    bool center_bound_reached{};
};

struct GuardedCandidate {
    Choice choice;
    bool native{};
    bool free_finalist{};
    bool conditioned_finalist{};
};

struct GuardedOutcome {
    Choice native;
    Choice reference_free;
    Choice final_rerank_winner;
    Choice final_rerank;
    Choice context_winner;
    Choice selected;
    GuardedSearch escape;
    GuardedSearch conditioned;
    std::vector<GuardedCandidate> candidates;
    bool context_enabled{};
    bool abstained{};
    bool final_rerank_abstained{};
    bool reference_free_abstained{};
    std::size_t partial_search_differences{};
    std::string gate;
    std::string final_rerank_gate;
};

void validate_guarded(const GuardedWindow& window, const GuardedPolicy& policy);
std::vector<std::string> canonical_center_context(const RetrievedContext& context);
double guarded_likelihood(const GuardedWindow& window, const std::string& center);
GuardedSearch guarded_search(const GuardedWindow& window,
                             const GuardedPolicy& policy,
                             bool use_context);
GuardedOutcome decode_guarded(const GuardedWindow& window, const GuardedPolicy& policy);
std::string guarded_outcome_json(const GuardedOutcome& outcome);
std::string run_guarded_controls();

}
