#include "context_decision_union/union.h"
#include "union_sources.h"
#include <cmath>
#include <iomanip>
#include <sstream>

namespace context_decision_union {
namespace {
using namespace context_study;
bool preferred(const Candidate &candidate, const Choice &best, const std::string &native) {
    if (candidate.log_mass->value != best.log_mass)
        return candidate.log_mass->value > best.log_mass;
    if ((candidate.sequence == native) != (best.sequence == native))
        return candidate.sequence == native;
    return candidate.sequence < best.sequence;
}
void row(std::ostringstream &out, const CandidateCase &input, const std::string &arm,
         const Choice &choice, std::size_t eligible) {
    out << input.id << '\t' << input.domain << '\t' << arm << '\t' << sha256(choice.sequence)
        << '\t' << choice.sequence << '\t' << choice.log_mass << '\t' << choice.potential << '\t'
        << choice.objective << '\t' << sha256(choice.sequence) << '\t' << choice.sequence << '\t'
        << choice.log_mass << '\t' << choice.potential << '\t' << choice.objective << '\t'
        << choice.gate << '\t' << choice.abstained << '\t' << eligible << '\t' << eligible << '\n';
}
}
Selection choose(const context_study::CandidateCase &input) {
    using namespace context_study;
    require(input.candidates.contains(input.native), "union native candidate absent");
    const auto &native = input.candidates.at(input.native);
    require((native.origins & native_origin) != 0 && native.log_mass.has_value() &&
                std::isfinite(native.log_mass->value),
            "union native candidate lacks finite score or native provenance");
    Selection result{{input.native, native.log_mass->value, 0, native.log_mass->value,
                      "retained_union_neural_maximum", false},
                     0,
                     0,
                     0,
                     0,
                     0};
    for (const auto &[sequence, candidate] : input.candidates) {
        require(sequence == candidate.sequence && candidate.origins > 0 && candidate.origins <= 15,
                "union candidate key or origin differs");
        require((candidate.origins & native_origin) == 0 || sequence == input.native,
                "union candidate has foreign native provenance");
        const bool eligible =
            (candidate.origins & (native_origin | escape_origin | conditioned_origin)) != 0;
        if (!eligible) {
            ++result.graph_only;
            continue;
        }
        require(candidate.log_mass.has_value() && std::isfinite(candidate.log_mass->value),
                "union eligible candidate lacks finite retained neural score");
        ++result.eligible;
        result.native += static_cast<std::size_t>((candidate.origins & native_origin) != 0);
        result.escape += static_cast<std::size_t>((candidate.origins & escape_origin) != 0);
        result.conditioned +=
            static_cast<std::size_t>((candidate.origins & conditioned_origin) != 0);
        if (preferred(candidate, result.choice, input.native))
            result.choice = {candidate.sequence,        candidate.log_mass->value,       0,
                             candidate.log_mass->value, "retained_union_neural_maximum", false};
    }
    require(result.eligible > 0, "empty scored retained union");
    return result;
}
std::uint64_t replay_bound(const context_study::Packet &packet) {
    std::uint64_t cells = 0;
    for (const auto &input : packet.cases)
        for (const auto &[sequence, candidate] : input.candidates) {
            if ((candidate.origins & (context_study::native_origin | context_study::escape_origin |
                                      context_study::conditioned_origin)) == 0 ||
                !candidate.log_mass)
                continue;
            for (const auto &path : input.paths) {
                const auto work = static_cast<std::uint64_t>(sequence.size()) * path.size();
                context_study::require(work <= maximum_work_cells / 8 - cells,
                                       "union historical replay work exceeds frozen cap");
                cells += work;
            }
        }
    return 8 * cells;
}
std::string diagnose(const context_study::Packet &packet, const std::filesystem::path &output) {
    using namespace context_study;
    const auto bound = replay_bound(packet);
    static_cast<void>(write_replays(packet, output));
    std::ostringstream decisions, census;
    decisions
        << std::setprecision(17)
        << "case_id\tdomain\tarm\tproposed_sha256\tproposed\tproposed_log_mass\tproposed_potential"
           "\tproposed_objective\taccepted_sha256\taccepted\taccepted_log_mass\taccepted_potential"
           "\taccepted_objective\tgate\tabstained\teligible\tfeasible\n";
    census
        << std::setprecision(17)
        << "case_id\tdomain\tunion_sha256\thistorical_free_sha256\tdifferent_from_historical_free"
           "\tunion_log_mass\thistorical_free_log_mass\teligible_unique\tnative_origin"
           "\tescape_origin\tconditioned_origin\tgraph_only_excluded\tescape_capped"
           "\tconditioned_capped\tescape_empty\tconditioned_empty\tcap_or_empty_flags"
           "\tretained_pool_only\n";
    std::size_t different = 0, ordinary_different = 0, flagged = 0;
    for (const auto &input : packet.cases) {
        const auto selected = choose(input);
        const auto &free = input.saved.at("reference_free");
        const bool changed = selected.choice.sequence != free.sequence;
        const bool limited = input.escape_capped || input.conditioned_capped ||
                             input.escape_empty || input.conditioned_empty;
        different += static_cast<std::size_t>(changed);
        ordinary_different += static_cast<std::size_t>(changed && input.domain == "ordinary");
        flagged += static_cast<std::size_t>(limited);
        row(decisions, input, "union_nn", selected.choice, selected.eligible);
        row(decisions, input, "reference_free", free, 0);
        row(decisions, input, "disabled_edits", input.saved.at("native"), 0);
        census << input.id << '\t' << input.domain << '\t' << sha256(selected.choice.sequence)
               << '\t' << sha256(free.sequence) << '\t' << changed << '\t'
               << selected.choice.log_mass << '\t' << free.log_mass << '\t' << selected.eligible
               << '\t' << selected.native << '\t' << selected.escape << '\t' << selected.conditioned
               << '\t' << selected.graph_only << '\t' << input.escape_capped << '\t'
               << input.conditioned_capped << '\t' << input.escape_empty << '\t'
               << input.conditioned_empty << '\t' << limited << "\t1\n";
    }
    synced_write(output / "decisions.tsv", decisions.str());
    synced_write(output / "union-census.tsv", census.str());
    return "{\"schema\":\"context-decision-union-diagnostic/1\",\"historical_replay\":true,"
           "\"truth_available\":false,\"new_neural_calls\":0,\"cases\":" +
           std::to_string(packet.cases.size()) +
           ",\"distance_cells_upper_bound\":" + std::to_string(bound) +
           ",\"different_from_historical_free\":" + std::to_string(different) +
           ",\"ordinary_different_from_historical_free\":" + std::to_string(ordinary_different) +
           ",\"cases_with_cap_or_empty_flags\":" + std::to_string(flagged) +
           ",\"cap_handling\":\"conditional_argmax_over_retained_scored_union\"}";
}
std::string source_json() {
    std::string result = "{\"compiled_sources\":[";
    bool first = true;
    for (const auto &source : union_compiled_sources) {
        if (!first)
            result += ',';
        first = false;
        result += "{\"path\":" + context_study::json_string(source.path) +
                  ",\"size\":" + std::to_string(source.size) +
                  ",\"sha256\":" + context_study::json_string(source.sha256) + "}";
    }
    return result + "],\"compiler_path\":" + context_study::json_string(union_compiler_path) +
           ",\"compiler_sha256\":" + context_study::json_string(union_compiler_sha256) +
           ",\"compile_flags\":" + context_study::json_string(union_compile_flags) +
           ",\"formatter_path\":" + context_study::json_string(union_formatter_path) +
           ",\"formatter_sha256\":" + context_study::json_string(union_formatter_sha256) + "}";
}
void verify_sources() {
    for (const auto &source : union_compiled_sources)
        context_study::require(std::filesystem::is_regular_file(source.path) &&
                                   std::filesystem::file_size(source.path) == source.size &&
                                   context_study::file_sha256(source.path) == source.sha256,
                               "compiled union source changed " + std::string(source.path));
    context_study::require(
        context_study::file_sha256(union_compiler_path) == union_compiler_sha256 &&
            context_study::file_sha256(union_formatter_path) == union_formatter_sha256,
        "union compiler or formatter changed");
    context_study::verify_compiled_sources();
}
}
