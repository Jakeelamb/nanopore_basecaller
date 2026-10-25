#include "context_sample_feedback/runtime.h"
#include "context_study/oracle.h"
#include <array>
#include <iomanip>
#include <iostream>
#include <sstream>

int main(int argc, char **argv) {
    namespace sample = context_sample_feedback;
    namespace study = context_study;
    try {
        const auto invocation = sample::begin(argc, argv);
        study::require(invocation.command == "evaluate", "observer requires evaluate");
        const auto &options = invocation.options;
        const auto packet =
            study::read_candidates(options.at("--cases"), options.at("--cases-sha256"));
        const std::set<std::string> columns{"case_id",
                                            "domain",
                                            "arm",
                                            "baseline",
                                            "baseline_sha256",
                                            "baseline_likelihood",
                                            "baseline_origins",
                                            "proposed",
                                            "proposed_sha256",
                                            "proposed_likelihood",
                                            "proposed_origins",
                                            "accepted",
                                            "accepted_sha256",
                                            "accepted_likelihood",
                                            "accepted_origins",
                                            "baseline_potential",
                                            "baseline_objective",
                                            "proposed_potential",
                                            "proposed_objective",
                                            "gate",
                                            "abstained"};
        const auto rows =
            sample::read_table(options.at("--choices"), options.at("--choices-sha256"), columns);
        const std::set<std::string> arms{
            "disabled_edits", "historical_free", "nn_u",           "population",
            "sample",         "combined",        "missing_source", "wrong_source_control"};
        std::map<std::pair<std::string, std::string>, std::map<std::string, std::string>> choices;
        for (const auto &row : rows)
            study::require(
                arms.contains(row.at("arm")) &&
                    choices.emplace(std::make_pair(row.at("case_id"), row.at("arm")), row).second,
                "duplicate/foreign observer choice");
        study::require(choices.size() == packet.cases.size() * arms.size(),
                       "complete observer choice census differs");
        for (const auto &input : packet.cases) {
            const auto &nn = choices.at({input.id, "nn_u"});
            for (const auto &arm : arms) {
                const auto &row = choices.at({input.id, arm});
                study::require(row.at("domain") == input.domain,
                               "observer choice case/domain differs");
                for (const auto *role : {"baseline", "proposed", "accepted"})
                    study::require(study::dna(row.at(role)) &&
                                       study::sha256(row.at(role)) ==
                                           row.at(std::string(role) + "_sha256"),
                                   "observer choice digest differs");
                if (arm != "disabled_edits" && arm != "historical_free")
                    study::require(row.at("baseline") == nn.at("accepted") &&
                                       row.at("baseline_sha256") == nn.at("accepted_sha256") &&
                                       row.at("baseline_likelihood") ==
                                           nn.at("accepted_likelihood") &&
                                       row.at("baseline_origins") == nn.at("accepted_origins"),
                                   "observer frozen NN common-U baseline differs");
            }
        }
        const auto truth =
            study::read_truth(options.at("--truth"), options.at("--truth-sha256"), packet);
        std::ostringstream effects, events;
        effects << "case_id\tdomain\tparent\tarm\tchoice\tsequence_sha256\tmask\tboundary_"
                   "resolved\tM_min\tM_max\tX_min\tX_max\tI_min\tI_max\tD_min\tD_max\terror_"
                   "min\terror_max\tvs_native\tvs_nn_u\n";
        events << "case_id\tdomain\tparent\tarm\tchoice\tsequence_sha256\tevent_id\tcall\tnative_"
                  "call\tnn_u_call\talt_to_ref\texact_alt_support_loss\tunresolved\tadded_"
                  "information\n";
        std::size_t private_cases{}, resolved_native_alt{};
        for (const auto &input : packet.cases) {
            const auto &labels = truth.at(input.id);
            const auto observe = [&](const std::string &sequence) {
                return study::observe(input, {sequence, 0, std::nullopt}, labels);
            };
            const auto native = observe(input.native);
            const auto &nn_sequence = choices.at({input.id, "nn_u"}).at("accepted");
            const auto nn = observe(nn_sequence);
            if (input.domain != "ordinary") {
                ++private_cases;
                for (const auto call : native.events)
                    resolved_native_alt += static_cast<std::size_t>(call == study::AlleleCall::alt);
            }
            for (const auto &arm : arms) {
                const auto &row = choices.at({input.id, arm});
                study::require(row.at("domain") == input.domain, "observer choice/domain differs");
                for (const auto *role : {"proposed", "accepted"}) {
                    const auto &sequence = row.at(role);
                    study::require(study::dna(sequence) &&
                                       study::sha256(sequence) ==
                                           row.at(std::string(role) + "_sha256"),
                                   "observer choice DNA differs");
                    const auto observation = observe(sequence);
                    for (std::size_t mask = 0; mask < 2; ++mask) {
                        effects << input.id << '\t' << input.domain << '\t' << input.parent << '\t'
                                << arm << '\t' << role << '\t' << study::sha256(sequence) << '\t'
                                << (mask == 0 ? "100" : "500") << '\t' << observation.boundary;
                        for (const auto &range : observation.counts[mask])
                            effects << '\t' << range.minimum << '\t' << range.maximum;
                        effects << '\t'
                                << study::effect(
                                       observation.counts[mask][4], native.counts[mask][4],
                                       observation.boundary && native.boundary,
                                       !labels.masks[mask].empty(), sequence == input.native)
                                << '\t'
                                << study::effect(observation.counts[mask][4], nn.counts[mask][4],
                                                 observation.boundary && nn.boundary,
                                                 !labels.masks[mask].empty(),
                                                 sequence == nn_sequence)
                                << '\n';
                    }
                    if (input.domain == "ordinary")
                        continue;
                    for (std::size_t i = 0; i < observation.events.size(); ++i) {
                        const auto call = observation.events[i];
                        const bool native_alt = native.events[i] == study::AlleleCall::alt;
                        events << input.id << '\t' << input.domain << '\t' << input.parent << '\t'
                               << arm << '\t' << role << '\t' << study::sha256(sequence) << '\t'
                               << labels.events[i].id << '\t' << study::call_name(call) << '\t'
                               << study::call_name(native.events[i]) << '\t'
                               << study::call_name(nn.events[i]) << '\t'
                               << (native_alt && call == study::AlleleCall::ref) << '\t'
                               << (native_alt && call != study::AlleleCall::alt &&
                                   call != study::AlleleCall::unresolved)
                               << '\t' << (call == study::AlleleCall::unresolved)
                               << "\tother-read source can contain formerly panel-withheld ALT\n";
                    }
                }
            }
        }
        study::synced_write(invocation.output / "effects.tsv", effects.str());
        study::synced_write(invocation.output / "private.tsv", events.str());
        sample::finish(
            invocation,
            "{\"schema\":\"context-sample-feedback-observation/"
            "1\",\"truth_join_after_inference\":true,\"cases\":" +
                std::to_string(packet.cases.size()) +
                ",\"private_cases\":" + std::to_string(private_cases) +
                ",\"resolved_native_alt_case_witnesses\":" + std::to_string(resolved_native_alt) +
                ",\"streaming_claim\":false,\"biological_qualification\":false,\"promotion_"
                "eligible\":false}",
            {"effects.tsv", "private.tsv"});
    } catch (const std::exception &error) {
        std::cerr << "sample observer: " << error.what() << '\n';
        return 2;
    }
}
