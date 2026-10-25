#include "context_sample_feedback/runtime.h"
#include <algorithm>
#include <bit>
#include <iomanip>
#include <iostream>
#include <sstream>

namespace {
using namespace context_sample_feedback;
using context_study::require;
void handshake(const context_study::Invocation &invocation) {
    const auto &options = invocation.options;
    const auto &path = options.at("--handshake");
    require(context_study::file_sha256(path) == options.at("--handshake-sha256"),
            "source handshake pin differs");
    const auto fields = context_decoder::fields(path, "sample-feedback-source-handshake/1");
    require(fields.size() == 15 && fields.at("packet_sha256") == options.at("--cases-sha256") &&
                fields.at("source_cases_sha256") == options.at("--source-cases-sha256") &&
                fields.at("contexts_sha256") == options.at("--contexts-sha256") &&
                fields.at("table_completion_sha256") ==
                    "6df31f85382ce08068b98b2c7af5241ea162fefcdea0172b9ee44c950dac64cf" &&
                fields.at("role_completion_sha256") ==
                    "4c545ebd0b8fd183f9875efd1a1ef7d4dff47bd457dbf6cdbfd3ee81ff309486" &&
                fields.at("source_audit_sha256") ==
                    "c8916b0014e327b121e7068f47cce2abbbe85d7dcc64e8f6abb01bd8b34f14eb" &&
                fields.at("context_role") == "exploratory_published_protocol" &&
                fields.at("assumption_tag") == "published_protocol_pi_dx_preservation_v1" &&
                fields.at("strict_read_level_qualified") == "0" &&
                fields.at("consumer_ready") == "0" && fields.at("promotion_eligible") == "0" &&
                fields.at("biological_qualification") == "0" &&
                fields.at("independent_donor_confirmation") == "0" &&
                fields.at("source_qualification") == "0" &&
                fields.at("physical_read_independence_qualified") == "0",
            "source handshake ancestry/role/flags differ");
}
std::string number(double value) {
    std::ostringstream out;
    out << std::setprecision(17) << value;
    return out.str();
}
void choice(std::ostringstream &out, const Candidate &candidate) {
    out << candidate.sequence << '\t' << context_study::sha256(candidate.sequence) << '\t'
        << candidate.likelihood << '\t' << candidate.origins;
}
}
int main(int argc, char **argv) {
    try {
        const auto invocation = begin(argc, argv);
        const auto &options = invocation.options;
        if (invocation.command == "qualify") {
            finish(
                invocation,
                "{\"schema\":\"context-sample-feedback-controls/1\",\"passed\":true,\"executed\":" +
                    std::to_string(controls()) + ",\"skipped\":0}",
                {});
            return 0;
        }
        if (invocation.command == "consume-frame") {
            const auto bound = context_decoder::load_guarded_frame(options.at("--frame"),
                                                                   options.at("--frame-sha256"));
            require(bound.scalar_comparisons > 0, "genuine scalar comparisons did not execute");
            finish(
                invocation,
                "{\"schema\":\"context-sample-feedback-consumed-frame/1\",\"scalar_comparisons\":" +
                    std::to_string(bound.scalar_comparisons) + ",\"native_likelihood\":" +
                    number(context_decoder::guarded_likelihood(bound.window,
                                                               bound.window.native_center)) +
                    "}",
                {});
            return 0;
        }
        require(options.at("--allow-exploratory") == "1",
                "explicit exploratory consumption required");
        handshake(invocation);
        const auto packet =
            context_study::read_candidates(options.at("--cases"), options.at("--cases-sha256"));
        const auto sources =
            read_sources(options.at("--source-cases"), options.at("--source-cases-sha256"),
                         options.at("--contexts"), options.at("--contexts-sha256"), packet, true);
        const auto frames =
            read_table(options.at("--frames"), options.at("--frames-sha256"),
                       {"case_id", "geometry_sha256", "ancestry_sha256", "frame_path", "frame_size",
                        "frame_sha256", "base_frame_sha256", "plan_sha256", "query_index",
                        "location_receipt_sha256", "location_sam_sha256"});
        std::map<std::string, std::map<std::string, std::string>> index;
        for (const auto &row : frames)
            require(index.emplace(row.at("case_id"), row).second, "duplicate frame index");
        require(index.size() == packet.cases.size(), "frame-index case census differs");
        const auto found =
            std::find_if(packet.cases.begin(), packet.cases.end(),
                         [&](const auto &input) { return input.id == options.at("--case-id"); });
        require(found != packet.cases.end(), "case identity absent");
        const auto &input = *found;
        const auto &row = index.at(input.id);
        require(row.at("geometry_sha256") == input.geometry &&
                    row.at("ancestry_sha256") == input.ancestry &&
                    std::filesystem::file_size(row.at("frame_path")) ==
                        context_study::natural(row.at("frame_size")),
                "frame index binding differs");
        if (invocation.command == "price") {
            const auto frame = context_decoder::fields(row.at("frame_path"), "guarded-frame/2");
            const auto steps = context_study::natural(frame.at("expanded_t_end")) -
                               context_study::natural(frame.at("expanded_t_start"));
            const auto maximum_trace = 4 * (128 * steps * (8 * (4 + 20) + 108 + 8) + steps * 128);
            finish(invocation,
                   "{\"schema\":\"context-sample-feedback-price/1\",\"case_id\":" +
                       context_study::json_string(input.id) +
                       ",\"expanded_steps\":" + std::to_string(steps) +
                       ",\"maximum_raw_trace_bytes\":" + std::to_string(maximum_trace) +
                       ",\"searches\":4,\"tensor_loaded\":false,\"truth_available\":false}",
                   {});
            return 0;
        }
        const auto bound =
            context_decoder::load_guarded_frame(row.at("frame_path"), row.at("frame_sha256"));
        bind_frame(input, bound);
        require(row.at("base_frame_sha256") == bound.binding.at("base_frame_sha256"),
                "indexed base frame differs");
        for (const auto *field :
             {"plan_sha256", "query_index", "location_receipt_sha256", "location_sam_sha256"})
            require(row.at(field) == bound.base.binding.at(field),
                    "indexed native plan/query/location binding differs");
        const auto position = static_cast<std::size_t>(found - packet.cases.begin());
        auto wrong_position = (position + 1) % packet.cases.size();
        while (wrong_position != position &&
               physical_window(packet.cases.at(wrong_position)) == physical_window(input))
            wrong_position = (wrong_position + 1) % packet.cases.size();
        const auto &wrong_case = packet.cases.at(wrong_position);
        auto wrong = sources.at(wrong_case.id);
        wrong.role = SourceRole::wrong_source_control;
        require(wrong.case_id != input.id, "wrong-source mapping is not a derangement");
        const auto result = infer(bound.window, sources.at(input.id), wrong);
        verify_historical(input, result.historical);
        std::ostringstream candidates, decisions, beams, historical, source_table, proposals;
        candidates << std::setprecision(17)
                   << "case_id\tdomain\tsequence\tsequence_sha256\tfull_log_"
                      "likelihood\torigins\tlikelihood_bits\n";
        for (const auto &candidate : result.candidates)
            candidates << input.id << '\t' << input.domain << '\t' << candidate.sequence << '\t'
                       << context_study::sha256(candidate.sequence) << '\t' << candidate.likelihood
                       << '\t' << candidate.origins << '\t'
                       << std::bit_cast<std::uint64_t>(candidate.likelihood) << '\n';
        decisions << std::setprecision(17)
                  << "case_id\tdomain\tarm\tbaseline\tbaseline_sha256\tbaseline_"
                     "likelihood\tbaseline_origins\tproposed\tproposed_sha256\tproposed_"
                     "likelihood\tproposed_origins\taccepted\taccepted_sha256\taccepted_"
                     "likelihood\taccepted_origins\tbaseline_potential\tbaseline_"
                     "objective\tproposed_potential\tproposed_objective\tgate\tabstained\n";
        for (const auto &[arm, decision] : result.decisions) {
            decisions << input.id << '\t' << input.domain << '\t' << arm << '\t';
            choice(decisions, decision.baseline);
            decisions << '\t';
            choice(decisions, decision.proposed);
            decisions << '\t';
            choice(decisions, decision.accepted);
            decisions << '\t' << decision.baseline_potential << '\t' << decision.baseline_objective
                      << '\t' << decision.proposed_potential << '\t' << decision.proposed_objective
                      << '\t' << decision.gate << '\t' << decision.abstained << '\n';
        }
        for (const auto &[arm, value] : std::map<std::string, context_decoder::Choice>{
                 {"disabled_edits", result.historical.native},
                 {"historical_free", result.historical.reference_free}}) {
            const auto actual = std::find_if(
                result.candidates.begin(), result.candidates.end(),
                [&](const auto &candidate) { return candidate.sequence == value.sequence; });
            require(actual != result.candidates.end(), "historical control absent from common U");
            Candidate candidate{value.sequence, actual->origins, value.signal_likelihood};
            decisions << input.id << '\t' << input.domain << '\t' << arm << '\t';
            choice(decisions, candidate);
            decisions << '\t';
            choice(decisions, candidate);
            decisions << '\t';
            choice(decisions, candidate);
            decisions << "\t0\t" << value.signal_likelihood << "\t0\t" << value.signal_likelihood
                      << "\tidentity_control\t0\n";
        }
        beams << "beam\tstatus\tpruned\tsteps\tfinalists\n";
        std::vector<std::string> files{"candidates.tsv", "decisions.tsv",
                                       "beams.tsv",      "historical.tsv",
                                       "sources.tsv",    "proposal-diagnostics.tsv"};
        auto old_h_nn = result.historical.native;
        std::set<std::string> old_h;
        for (const auto &candidate : result.historical.candidates) {
            old_h.insert(candidate.choice.sequence);
            const auto &value = candidate.choice;
            const bool tie_preferred =
                value.sequence == input.native ||
                (old_h_nn.sequence != input.native && value.sequence < old_h_nn.sequence);
            if (value.signal_likelihood > old_h_nn.signal_likelihood ||
                (value.signal_likelihood == old_h_nn.signal_likelihood && tie_preferred))
                old_h_nn = value;
        }
        const auto &nn = result.decisions.at("nn_u").accepted;
        const auto newly_proposed = std::count_if(
            result.candidates.begin(), result.candidates.end(),
            [&](const auto &candidate) { return !old_h.contains(candidate.sequence); });
        proposals << std::setprecision(17)
                  << "case_id\told_h_nn\told_h_nn_likelihood\thistorical_free\thistorical_free_"
                     "likelihood\tnn_u\tnn_u_likelihood\tproposal_neural_gain\tnew_candidates_"
                     "absent_old_h\n"
                  << input.id << '\t' << old_h_nn.sequence << '\t' << old_h_nn.signal_likelihood
                  << '\t' << result.historical.reference_free.sequence << '\t'
                  << result.historical.reference_free.signal_likelihood << '\t' << nn.sequence
                  << '\t' << nn.likelihood << '\t' << nn.likelihood - old_h_nn.signal_likelihood
                  << '\t' << newly_proposed << '\n';
        source_table << "arm\tsource_case_id\tgeometry_sha256\tphysical_window_"
                        "sha256\tstatus\tunique_paths_before_cap\tmaximum_path_length\trole\n";
        for (const auto &[arm, source] : result.sources) {
            const auto role = source.role == SourceRole::population ? "original_population"
                              : source.role == SourceRole::combined ? "population_plus_sample"
                              : source.role == SourceRole::wrong_source_control
                                  ? "wrong_source_control"
                                  : "exploratory_published_protocol";
            source_table << arm << '\t' << source.case_id << '\t' << source.geometry << '\t'
                         << source.physical_window << '\t' << state_name(source.state) << '\t'
                         << source.unique_paths << '\t' << source.maximum_length << '\t' << role
                         << '\n';
        }
        for (const auto &[name, search] : result.searches) {
            beams << name << '\t' << state_name(result.states.at(name)) << '\t' << search.pruned
                  << '\t' << search.trace.size() << '\t' << search.finalists.size() << '\n';
            const auto name_file = name + "-trace.bin";
            write_trace(invocation.output / name_file, search);
            files.push_back(name_file);
        }
        historical << "role\tsequence\tlog_mass\tpotential\tobjective\tgate\tabstained\n"
                   << std::setprecision(17);
        for (const auto &[role, saved] : input.saved)
            historical << role << '\t' << saved.sequence << '\t' << saved.log_mass << '\t'
                       << saved.potential << '\t' << saved.objective << '\t' << saved.gate << '\t'
                       << saved.abstained << '\n';
        context_study::synced_write(invocation.output / "candidates.tsv", candidates.str());
        context_study::synced_write(invocation.output / "decisions.tsv", decisions.str());
        context_study::synced_write(invocation.output / "beams.tsv", beams.str());
        context_study::synced_write(invocation.output / "historical.tsv", historical.str());
        context_study::synced_write(invocation.output / "sources.tsv", source_table.str());
        context_study::synced_write(invocation.output / "proposal-diagnostics.tsv",
                                    proposals.str());
        require(context_study::file_sha256(row.at("frame_path")) == row.at("frame_sha256"),
                "frame changed after decode");
        finish(invocation,
               "{\"schema\":\"context-sample-feedback-result/1\",\"case_id\":" +
                   context_study::json_string(input.id) +
                   ",\"domain\":" + context_study::json_string(input.domain) +
                   ",\"wrong_source_case\":" + context_study::json_string(wrong.case_id) +
                   ",\"historical_six_roles_verified\":true,\"scalar_comparisons\":" +
                   std::to_string(bound.scalar_comparisons) + ",\"sample_source_status\":" +
                   context_study::json_string(state_name(sources.at(input.id).state)) +
                   ",\"truth_available\":false,\"context_role\":\"exploratory_published_protocol\","
                   "\"assumption_tag\":\"published_protocol_pi_dx_preservation_v1\",\"strict_read_"
                   "level_qualified\":false,\"consumer_ready\":false,\"promotion_eligible\":false,"
                   "\"biological_qualification\":false,\"independent_donor_confirmation\":false,"
                   "\"source_qualification\":false,\"physical_read_independence_qualified\":false}",
               files);
    } catch (const std::exception &error) {
        std::cerr << "context-sample-feedback: " << error.what() << '\n';
        return 2;
    }
}
