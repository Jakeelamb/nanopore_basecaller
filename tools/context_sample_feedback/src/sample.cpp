#include "context_sample_feedback/sample.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace context_sample_feedback {
namespace {
using context_study::require;
bool preferred(const Candidate &a, const Candidate &b, const std::string &native_center) {
    if (a.sequence == native_center || b.sequence == native_center)
        return a.sequence == native_center && b.sequence != native_center;
    return a.sequence < b.sequence;
}
Candidate neural(const std::vector<Candidate> &candidates, const std::string &native_center) {
    const Candidate *best = nullptr;
    for (const auto &candidate : candidates)
        if (std::isfinite(candidate.likelihood) &&
            (best == nullptr || candidate.likelihood > best->likelihood ||
             (candidate.likelihood == best->likelihood &&
              preferred(candidate, *best, native_center))))
            best = &candidate;
    require(best != nullptr, "common U has no finite neural candidate");
    return *best;
}
double potential(const Candidate &candidate, const Source &source) {
    return source.state == SourceState::available
               ? context_decoder::context_potential(candidate.sequence, source.paths, true)
               : 0.0;
}
}
Source canonical_source(Source source) {
    for (const auto &path : source.paths)
        require(context_study::dna(path), "source DNA is noncanonical");
    std::sort(source.paths.begin(), source.paths.end());
    source.paths.erase(std::unique(source.paths.begin(), source.paths.end()), source.paths.end());
    if (source.state != SourceState::available) {
        require(source.paths.empty(), "unavailable source contains paths");
        return source;
    }
    source.unique_paths = source.paths.size();
    source.maximum_length = 0;
    for (const auto &path : source.paths)
        source.maximum_length = std::max(source.maximum_length, path.size());
    if (source.paths.empty())
        source.state = SourceState::missing;
    else if (source.paths.size() > 32)
        source.state = SourceState::path_cap;
    else if (std::any_of(source.paths.begin(), source.paths.end(),
                         [](const auto &path) { return path.size() > 108; }))
        source.state = SourceState::length_cap;
    if (source.state != SourceState::available)
        source.paths.clear();
    return source;
}
Source union_source(const Source &left, const Source &right) {
    Source result = right;
    for (const auto state : {left.state, right.state})
        if (state == SourceState::path_cap || state == SourceState::length_cap) {
            result.state = state;
            result.paths.clear();
            return result;
        }
    result.state = SourceState::available;
    result.paths.insert(result.paths.end(), left.paths.begin(), left.paths.end());
    return canonical_source(std::move(result));
}
context_decoder::GuardedWindow overlay(const context_decoder::GuardedWindow &original,
                                       const Source &source) {
    auto copy = original;
    copy.center_context = {source.state == SourceState::available
                               ? context_decoder::Availability::usable
                               : context_decoder::Availability::missing,
                           source.paths};
    return copy;
}
BeamState beam_state(const context_decoder::GuardedSearch &search) {
    if (search.center_bound_reached)
        return BeamState::center_bound;
    return search.finalists.empty() ? BeamState::no_finalist : BeamState::complete;
}
std::string state_name(BeamState state) {
    switch (state) {
    case BeamState::complete:
        return "complete";
    case BeamState::center_bound:
        return "center_bound";
    case BeamState::no_finalist:
        return "no_finalist";
    case BeamState::unavailable:
        return "unavailable";
    }
    throw std::invalid_argument("unknown beam state");
}
std::string state_name(SourceState state) {
    switch (state) {
    case SourceState::available:
        return "available";
    case SourceState::missing:
        return "missing";
    case SourceState::path_cap:
        return "path_cap";
    case SourceState::length_cap:
        return "length_cap";
    }
    throw std::invalid_argument("unknown source state");
}
Decision select(const std::vector<Candidate> &candidates, const std::string &native_center,
                const Source &source, BeamState status, bool free_ok) {
    Decision result;
    const auto found =
        std::find_if(candidates.begin(), candidates.end(),
                     [&](const auto &candidate) { return candidate.sequence == native_center; });
    require(found != candidates.end() && std::isfinite(found->likelihood), "finite native absent");
    result.baseline = free_ok ? neural(candidates, native_center) : *found;
    result.proposed = result.accepted = result.baseline;
    result.baseline_potential = potential(result.baseline, source);
    result.baseline_objective = result.baseline.likelihood + 0.5 * result.baseline_potential;
    result.proposed_potential = result.baseline_potential;
    result.proposed_objective = result.baseline_objective;
    if (!free_ok || status == BeamState::center_bound || status == BeamState::no_finalist) {
        result.proposed = result.accepted = *found;
        result.proposed_potential = potential(*found, source);
        result.proposed_objective = found->likelihood + 0.5 * result.proposed_potential;
        result.gate =
            !free_ok ? "free_search_native_abstention" : state_name(status) + "_native_abstention";
        result.abstained = true;
        return result;
    }
    if (source.state != SourceState::available || status == BeamState::unavailable) {
        result.gate = "source_" + state_name(source.state) + "_nn_fallback";
        return result;
    }
    for (const auto &candidate : candidates) {
        if (!std::isfinite(candidate.likelihood) ||
            candidate.likelihood < result.baseline.likelihood - 0.5)
            continue;
        const auto phi = potential(candidate, source);
        const auto objective = candidate.likelihood + 0.5 * phi;
        if (objective > result.proposed_objective ||
            (objective == result.proposed_objective &&
             preferred(candidate, result.proposed, native_center))) {
            result.proposed = candidate;
            result.proposed_potential = phi;
            result.proposed_objective = objective;
        }
    }
    if (result.proposed_objective - result.baseline_objective >= 0.5) {
        result.accepted = result.proposed;
        result.gate = "common_u_context_selected";
    } else {
        result.gate = "common_u_objective_margin_nn_fallback";
    }
    return result;
}
Run infer(const context_decoder::GuardedWindow &window, const Source &source, const Source &wrong,
          const context_decoder::GuardedPolicy &policy) {
    using namespace context_decoder;
    require(policy.context_weight == 0.5 && policy.maximum_signal_deficit == 0.5 &&
                policy.minimum_objective_margin == 0.5,
            "frozen inference policy differs");
    Run result;
    result.historical = decode_guarded(window, policy);
    result.searches.emplace("free", result.historical.escape);
    result.searches.emplace("population", result.historical.conditioned);
    Source pop;
    pop.case_id = source.case_id;
    pop.geometry = source.geometry;
    pop.physical_window = source.physical_window;
    pop.role = SourceRole::population;
    pop.state = window.center_context.availability == Availability::usable ? SourceState::available
                                                                           : SourceState::missing;
    pop.paths = window.center_context.sequences;
    pop = canonical_source(std::move(pop));
    auto both = union_source(pop, source);
    both.role = SourceRole::combined;
    const std::map<std::string, Source> sources{
        {"population", pop}, {"sample", source}, {"combined", both}};
    result.sources = sources;
    result.sources.emplace("wrong_source_control", wrong);
    for (const auto &[name, context] : sources) {
        if (name != "population" && context.state == SourceState::available)
            result.searches.emplace(name, guarded_search(overlay(window, context), policy, true));
        result.states[name] = context.state == SourceState::available
                                  ? beam_state(result.searches.at(name))
                                  : BeamState::unavailable;
    }
    result.states["free"] = beam_state(result.searches.at("free"));
    const bool free_ok = result.states.at("free") == BeamState::complete;
    std::map<std::string, unsigned> origins{{window.native_center, Origin::native}};
    const std::map<std::string, unsigned> bits{{"free", Origin::free},
                                               {"population", Origin::population},
                                               {"sample", Origin::sample},
                                               {"combined", Origin::combined}};
    if (free_ok)
        for (const auto &[name, search] : result.searches)
            if (result.states.at(name) == BeamState::complete)
                for (const auto &candidate : search.finalists)
                    origins[candidate.sequence] |= bits.at(name);
    for (const auto &[sequence, bits_value] : origins)
        result.candidates.push_back({sequence, bits_value, guarded_likelihood(window, sequence)});
    Source missing;
    const auto nn =
        select(result.candidates, window.native_center, missing, BeamState::unavailable, free_ok);
    result.decisions["nn_u"] = nn;
    result.decisions["missing_source"] = nn;
    result.decisions["wrong_source_control"] =
        select(result.candidates, window.native_center, wrong,
               wrong.state == SourceState::available ? BeamState::complete : BeamState::unavailable,
               free_ok);
    for (const auto &[name, context] : sources)
        result.decisions[name] = select(result.candidates, window.native_center, context,
                                        result.states.at(name), free_ok);
    return result;
}
void verify_historical(const context_study::CandidateCase &input,
                       const context_decoder::GuardedOutcome &old) {
    using context_decoder::Choice;
    const std::map<std::string, Choice> actual{{"native", old.native},
                                               {"reference_free", old.reference_free},
                                               {"final_rerank_winner", old.final_rerank_winner},
                                               {"final_rerank", old.final_rerank},
                                               {"context_winner", old.context_winner},
                                               {"selected", old.selected}};
    for (const auto &[role, value] : actual) {
        const auto &saved = input.saved.at(role);
        require(saved.sequence == value.sequence &&
                    std::abs(saved.log_mass - value.signal_likelihood) <= 1e-11 &&
                    std::abs(saved.potential - value.context_potential) <= 1e-11 &&
                    std::abs(saved.objective - value.objective) <= 1e-11,
                "historical six-role replay differs " + role);
        const auto gate = role == "selected"       ? old.gate
                          : role == "final_rerank" ? old.final_rerank_gate
                                                   : ".";
        const auto abstained = role == "selected"         ? old.abstained
                               : role == "final_rerank"   ? old.final_rerank_abstained
                               : role == "reference_free" ? old.reference_free_abstained
                                                          : false;
        require(saved.gate == gate && saved.abstained == abstained,
                "historical gate/abstention differs " + role);
    }
    require(input.escape_capped == old.escape.center_bound_reached &&
                input.conditioned_capped == old.conditioned.center_bound_reached &&
                input.escape_empty == old.escape.finalists.empty() &&
                input.conditioned_empty == old.conditioned.finalists.empty(),
            "historical search status differs");
}
}
