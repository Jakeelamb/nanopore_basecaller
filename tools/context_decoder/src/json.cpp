#include "context_decoder/io.h"

#include <iomanip>
#include <sstream>

namespace context_decoder {
namespace {
void choice_json(std::ostream& out, const Choice& choice) {
    out << "{\"sequence\":" << quote(choice.sequence)
        << ",\"signal_likelihood\":" << choice.signal_likelihood
        << ",\"context_potential\":" << choice.context_potential
        << ",\"objective\":" << choice.objective << '}';
}
void search_json(std::ostream& out, const Search& search_result) {
    out << "{\"pruned\":" << (search_result.pruned ? "true" : "false")
        << ",\"symbol_bound_reached\":" << (search_result.symbol_bound_reached ? "true" : "false")
        << ",\"finalists\":" << search_result.finalists.size() << ",\"trace\":[";
    bool first = true;
    for (const auto& step : search_result.trace) {
        if (!first) {
            out << ',';
        }
        first = false;
        out << "{\"timestep\":" << step.timestep << ",\"generated\":" << step.generated
            << ",\"merged\":" << step.merged << ",\"pruned\":" << step.pruned
            << ",\"retained_prefixes\":[";
        bool first_prefix = true;
        for (const auto& prefix : step.retained_prefixes) {
            if (!first_prefix) {
                out << ',';
            }
            first_prefix = false;
            out << quote(prefix);
        }
        out << "]}";
    }
    out << "]}";
}
}
std::string outcome_json(const Outcome& outcome) {
    std::ostringstream out;
    out << std::setprecision(17) << "{\"native\":";
    choice_json(out, outcome.native);
    out << ",\"reference_free\":";
    choice_json(out, outcome.reference_free);
    out << ",\"context_winner\":";
    choice_json(out, outcome.context_winner);
    out << ",\"selected\":";
    choice_json(out, outcome.selected);
    out << ",\"gate\":" << quote(outcome.gate)
        << ",\"context_enabled\":" << (outcome.context_enabled ? "true" : "false")
        << ",\"different_from_native\":" << (outcome.different_from_native ? "true" : "false")
        << ",\"different_from_reference_free\":"
        << (outcome.different_from_reference_free ? "true" : "false")
        << ",\"abstained\":" << (outcome.abstained ? "true" : "false")
        << ",\"bounded_beam_is_approximate\":"
        << ((outcome.escape.pruned || outcome.conditioned.pruned) ? "true" : "false")
        << ",\"partial_search_differences\":" << outcome.partial_search_differences
        << ",\"reference_free_escape\":";
    search_json(out, outcome.escape);
    out << ",\"conditioned_search\":";
    search_json(out, outcome.conditioned);
    out << ",\"inference_scope\":\"offline retained-neural-score decoding; no encoder feedback or "
           "native integration\""
        << ",\"quality_policy\":\"changed bases uncalibrated; no new calibrated qualities emitted\""
        << ",\"admissible_candidate\":false}";
    return out.str();
}
}
