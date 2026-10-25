#include "context_decision/decision.h"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <limits>
#include <sstream>
#include <tuple>

namespace context_decision {
namespace {
using namespace context_study;
Choice score(const CandidateCase &input, const Candidate &candidate, double weight) {
    require(candidate.log_mass.has_value() && std::isfinite(candidate.log_mass->value),
            "decision candidate lacks finite retained neural score");
    double potential = 0;
    if (weight != 0) {
        require(!input.paths.empty(), "usable context has no paths");
        auto nearest = std::numeric_limits<std::size_t>::max();
        for (const auto &path : input.paths)
            nearest = std::min(nearest, distance(candidate.sequence, path));
        potential = -static_cast<double>(nearest);
    }
    const auto objective = candidate.log_mass->value + weight * potential;
    require(std::isfinite(objective), "nonfinite contextual objective");
    return {candidate.sequence, candidate.log_mass->value, potential, objective, ".", false};
}
bool preferred(const Choice &a, const Choice &b, const std::string &native) {
    if (a.objective != b.objective)
        return a.objective > b.objective;
    if ((a.sequence == native) != (b.sequence == native))
        return a.sequence == native;
    return a.sequence < b.sequence;
}
void row(std::ostringstream &out, const CandidateCase &input, const std::string &arm,
         const Decision &value) {
    const auto &raw = value.proposed;
    const auto &accepted = value.accepted;
    out << input.id << '\t' << input.domain << '\t' << arm << '\t' << sha256(raw.sequence) << '\t'
        << raw.sequence << '\t' << raw.log_mass << '\t' << raw.potential << '\t' << raw.objective
        << '\t' << sha256(accepted.sequence) << '\t' << accepted.sequence << '\t'
        << accepted.log_mass << '\t' << accepted.potential << '\t' << accepted.objective << '\t'
        << accepted.gate << '\t' << accepted.abstained << '\t' << value.eligible << '\t'
        << value.feasible << '\n';
}
}
Decision choose(const context_study::CandidateCase &input, bool partial, double weight) {
    using namespace context_study;
    require(std::isfinite(weight) && weight >= 0, "invalid context weight");
    const auto historical = replay(input);
    const auto free = historical.at("reference_free");
    Decision result{free, free, 0, 0};
    result.accepted.gate = "reference_free_fallback";
    if (weight == 0 || input.availability != "usable")
        return result;
    if (input.escape_capped || input.escape_empty ||
        (partial && (input.conditioned_capped || input.conditioned_empty))) {
        result.accepted = historical.at(partial ? "selected" : "final_rerank");
        return result;
    }
    const auto baseline = score(input, input.candidates.at(free.sequence), weight);
    result.proposed = baseline;
    const auto origins = native_origin | escape_origin | (partial ? conditioned_origin : 0U);
    for (const auto &[sequence, candidate] : input.candidates) {
        static_cast<void>(sequence);
        if ((candidate.origins & origins) == 0 || !candidate.log_mass.has_value())
            continue;
        const auto value = score(input, candidate, weight);
        ++result.eligible;
        if (value.log_mass - baseline.log_mass < -0.5)
            continue;
        ++result.feasible;
        if (preferred(value, result.proposed, input.native))
            result.proposed = value;
    }
    require(result.feasible > 0, "matched reference-free candidate absent from feasible pool");
    if (result.proposed.objective - baseline.objective < 0.5) {
        result.accepted.gate = "objective_margin_fallback";
    } else {
        result.accepted = result.proposed;
        result.accepted.gate = "context_selected";
    }
    return result;
}
std::uint64_t price(const context_study::CandidateCase &input) {
    std::uint64_t cells = 0;
    for (const auto &[sequence, candidate] : input.candidates) {
        if ((candidate.origins & (context_study::native_origin | context_study::escape_origin |
                                  context_study::conditioned_origin)) == 0 ||
            !candidate.log_mass)
            continue;
        for (const auto &path : input.paths) {
            const auto work = static_cast<std::uint64_t>(sequence.size()) * path.size();
            context_study::require(work <= maximum_work_cells - cells,
                                   "per-case decision work exceeds cap");
            cells += work;
        }
    }
    return cells;
}
std::vector<std::size_t> indices(const context_study::Packet &packet, const std::string &scope) {
    context_study::require(scope == "query0" || scope == "first32" || scope == "remaining" ||
                               scope == "all",
                           "unknown scope");
    std::vector<std::size_t> result;
    for (std::size_t i = 0; i < packet.cases.size(); ++i) {
        const auto &item = packet.cases[i];
        bool include = scope == "all";
        if (item.domain == "ordinary") {
            const auto end = item.id.find('/', 9);
            const auto query = context_study::natural(item.id.substr(9, end - 9));
            include = include || (scope == "query0" && query == 0) ||
                      (scope == "first32" && query > 0 && query < 32) ||
                      (scope == "remaining" && query >= 32);
        } else if (scope == "remaining")
            include = true;
        if (include)
            result.push_back(i);
    }
    return result;
}
std::string evaluate(const context_study::Packet &packet, const std::string &scope,
                     const std::filesystem::path &output) {
    using namespace context_study;
    const auto selected = indices(packet, scope);
    // Replay every retained historical choice before permitting any new policy output.
    for (const auto &input : packet.cases)
        verify_replay(input, replay(input));
    static_cast<void>(write_replays(packet, output));
    std::ostringstream table;
    table
        << std::setprecision(17)
        << "case_id\tdomain\tarm\tproposed_sha256\tproposed\tproposed_log_mass\tproposed_potential"
           "\tproposed_objective\taccepted_sha256\taccepted\taccepted_log_mass\taccepted_potential"
           "\taccepted_objective\tgate\tabstained\teligible\tfeasible\n";
    for (const auto index : selected) {
        const auto &input = packet.cases[index];
        const auto historical = replay(input);
        for (const auto &[name, raw, accepted_role] :
             {std::tuple{"raw_veto_escape", "final_rerank_winner", "final_rerank"},
              std::tuple{"raw_veto_partial", "context_winner", "selected"},
              std::tuple{"reference_free", "reference_free", "reference_free"},
              std::tuple{"disabled_edits", "native", "native"}})
            row(table, input, name, {historical.at(raw), historical.at(accepted_role), 0, 0});
        row(table, input, "feasible_escape", choose(input, false));
        row(table, input, "feasible_partial", choose(input, true));
        row(table, input, "zero_weight_escape", choose(input, false, 0));
        row(table, input, "zero_weight_partial", choose(input, true, 0));
    }
    synced_write(output / "decisions.tsv", table.str());
    return "{\"schema\":\"context-decision-inference/1\",\"historical_replay\":true,"
           "\"truth_available\":false,\"cases\":" +
           std::to_string(selected.size()) +
           ",\"packet_cases\":" + std::to_string(packet.cases.size()) + "}";
}
}
