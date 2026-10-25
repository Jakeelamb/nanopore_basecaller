#pragma once

#include <cstddef>
#include <map>
#include <span>
#include <string>
#include <vector>

namespace context_decoder {

struct Frame {
    std::size_t timesteps{};
    std::size_t state_length{};
    std::size_t initial_state{};
    double stay_score{};
    std::vector<double> scores;
};

enum class Availability { usable, missing, ambiguous };

struct RetrievedContext {
    Availability availability{Availability::missing};
    std::vector<std::string> sequences;
};

struct Policy {
    std::size_t beam_width{128};
    std::size_t max_symbols{128};
    std::size_t min_symbols{20};
    double context_weight{0.5};
    double maximum_signal_deficit{0.5};
    double minimum_objective_margin{0.5};
};

struct Prefix {
    std::string sequence;
    std::size_t state{};
    double signal_mass{};
    double context_potential{};
    double rank{};
};

struct Expansion {
    std::size_t timestep{};
    std::size_t generated{};
    std::size_t merged{};
    std::size_t pruned{};
    std::vector<std::string> retained_prefixes;
};

struct Search {
    std::vector<Prefix> finalists;
    std::vector<Expansion> trace;
    bool pruned{};
    bool symbol_bound_reached{};
};

struct Choice {
    std::string sequence;
    double signal_likelihood{};
    double context_potential{};
    double objective{};
};

struct Outcome {
    Choice native;
    Choice reference_free;
    Choice context_winner;
    Choice selected;
    Search escape;
    Search conditioned;
    bool context_enabled{};
    bool different_from_native{};
    bool different_from_reference_free{};
    bool abstained{};
    std::size_t partial_search_differences{};
    std::string gate;
};

void validate(const Frame& frame, const Policy& policy);
std::vector<std::string> canonical_context(const RetrievedContext& context);
double log_add(double a, double b);
std::size_t transition(std::size_t previous, unsigned char base, std::size_t k, std::size_t& next);
double sequence_likelihood(const Frame& frame, const std::string& sequence);
std::size_t edit_distance(const std::string& a, const std::string& b);
double context_potential(const std::string& prefix,
                         std::span<const std::string> paths,
                         bool terminal);
Search search(const Frame& frame,
              std::span<const std::string> paths,
              const Policy& policy,
              bool use_context);
Outcome decode(const Frame& frame,
               const RetrievedContext& context,
               const Policy& policy,
               const std::string& native);
std::string outcome_json(const Outcome& outcome);

}
