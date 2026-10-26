#include "uncertainty_feedback/core.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <sstream>

namespace uncertainty_feedback {
void apply(const Json& planned, const Json& decoded, const fs::path& output) {
    validate_plan(planned);
    validate_completion(decoded, "uncertainty-feedback-decoded/1");
    require(decoded.at("schema") == "uncertainty-feedback-decoded/1" &&
                    decoded.at("complete") == true &&
                    decoded.at("plan_sha256") == planned.at("plan_sha256"),
            "Decoded/new plan identity differs");
    check(planned.at("joins"));
    check(planned.at("parents"));
    const auto joins = read(planned.at("joins").at("path").get<std::string>()),
               parents = read(planned.at("parents").at("path").get<std::string>());
    std::map<std::size_t, Json> results;
    std::map<std::size_t, std::string> union_nn;
    Json union_diagnostics = Json::array();
    std::size_t conditioned_only{}, partial_differences{}, selected_vs_final{};
    for (const auto& row : decoded.at("rows")) {
        const auto id = integer(row.at("query_index"));
        require(id < joins.size() && !results.contains(id), "Foreign/duplicate decoded query");
        for (const auto& key : {"result", "frame", "base_frame", "completion", "producer"}) {
            check(row.at(key));
        }
        const auto result = read(row.at("result").at("path").get<std::string>()),
                   seal = read(row.at("completion").at("path").get<std::string>());
        const auto deps = dependencies();
        check(deps.at("unchanged_decoder_manifest_pin"));
        const auto original = read(deps.at("unchanged_decoder_manifest").get<std::string>());
        Json input_tuple = Json::array({row.at("frame")});
        for (const auto& item : original.at("compiled_sources")) {
            input_tuple.push_back(item);
        }
        const auto producer = read(row.at("producer").at("path").get<std::string>());
        const auto output_directory =
                fs::path(row.at("result").at("path").get<std::string>()).parent_path();
        const auto argv = Json::array({deps.at("unchanged_decoder").at("path"),
                                       "decode-guarded",
                                       "--frame",
                                       row.at("frame").at("path"),
                                       "--frame-sha256",
                                       row.at("frame").at("sha256"),
                                       "--output",
                                       output_directory.string(),
                                       "--beam",
                                       "128",
                                       "--min-center",
                                       "0",
                                       "--max-center",
                                       "108",
                                       "--weight",
                                       "0.5",
                                       "--deficit",
                                       "0.5",
                                       "--margin",
                                       "0.5"});
        validate_receipt(producer, deps.at("unchanged_decoder"), argv, input_tuple);
        require(producer.at("environment") == command_environment() &&
                        producer.at("extra_runtimes").empty(),
                "Decoder environment/runtime census differs");
        validate_runtime(producer.at("runtime"), deps.at("unchanged_decoder"));
        require(seal.at("schema") == "context-decoder-complete/1" && seal.at("complete") == true &&
                        std::find(seal.at("files").begin(), seal.at("files").end(),
                                  row.at("result")) != seal.at("files").end(),
                "Actual decoder result/completion join differs");
        for (const auto& item : seal.at("files")) {
            check(item);
            require(std::find(producer.at("produced_files").begin(),
                              producer.at("produced_files").end(),
                              item) != producer.at("produced_files").end(),
                    "Decoded byte output absent from actual producer closure");
        }
        const auto base =
                fields(row.at("base_frame").at("path").get<std::string>(), "context-frame/1");
        const auto frame = fields(row.at("frame").at("path").get<std::string>(), "guarded-frame/2");
        const auto& target = joins.at(id);
        require(result.at("schema") == "context-decoder-guarded-frame/2" &&
                        result.at("frame") == row.at("frame") &&
                        result.at("binding") == Json(frame) &&
                        base.at("query_index") == std::to_string(id) &&
                        base.at("parent") == target.at("window").at("read_id").get<std::string>() &&
                        base.at("plan_sha256") == planned.at("plan_sha256").get<std::string>() &&
                        natural(frame.at("owned_start")) == integer(target.at("owned_start")) &&
                        natural(frame.at("owned_end")) == integer(target.at("owned_end")) &&
                        integer(result.at("retained_rust_scalar_bit_comparisons")) > 0,
                "Decoder new geometry/scalar linkage differs");
        const auto& outcome = result.at("outcome");
        require(outcome.at("native").at("sequence") == target.at("nomination").at(15),
                "Decoder/native owned center differs");
        partial_differences += integer(outcome.at("partial_search_differences"));
        selected_vs_final += static_cast<std::size_t>(outcome.at("selected").at("sequence") !=
                                                      outcome.at("final_rerank").at("sequence"));
        for (const auto& candidate : outcome.at("candidates")) {
            conditioned_only += static_cast<std::size_t>(
                    candidate.at("conditioned_finalist") == true &&
                    candidate.at("free_finalist") == false && candidate.at("native") == false);
        }
        const auto native = outcome.at("native").at("sequence").get<std::string>();
        auto winner = native;
        double mass = -std::numeric_limits<double>::infinity();
        for (const auto& candidate : outcome.at("candidates")) {
            const auto& choice = candidate.at("choice");
            if (!choice.at("signal_likelihood").is_number()) {
                continue;
            }
            const auto value = choice.at("signal_likelihood").get<double>();
            const auto sequence = choice.at("sequence").get<std::string>();
            require(std::isfinite(value), "Nonfinite scored union mass");
            if (value > mass || (value == mass &&
                                 ((sequence == native && winner != native) ||
                                  (sequence != native && winner != native && sequence < winner)))) {
                mass = value;
                winner = sequence;
            }
        }
        union_nn[id] = winner;
        union_diagnostics.push_back(
                {{"query_index", id},
                 {"escape_H_reference_free", outcome.at("reference_free").at("sequence")},
                 {"scored_union_U_prior_none", winner},
                 {"selected", outcome.at("selected").at("sequence")},
                 {"diagnostic_only", true},
                 {"original_context_gate_baseline",
                  "escape-H actual reference_free; unchanged qualified0.5 gates"},
                 {"partial_search_abstained", outcome.at("abstained")}});
        results[id] = row;
    }
    Json arm_outputs = Json::array();
    for (const auto& arm :
         {"disabled", "reference_free", "diagnostic_union_nn", "final_rerank", "selected"}) {
        std::string sam = "@HD\tVN:1.6\tSO:unknown\n";
        Json arm_edits = Json::array();
        for (const auto& [parent, item] : parents.items()) {
            check(item.at("parent_pin"));
            check(item.at("native_location_sam"));
            const auto original = item.at("native_sequence").get<std::string>(),
                       quality = item.at("native_quality").get<std::string>();
            require(original.size() == quality.size() && !original.empty(),
                    "Actual native parent SEQ/Q absent");
            struct Edit {
                std::size_t a, b;
                std::string replacement;
                std::size_t query;
            };
            std::vector<Edit> changes;
            if (std::string(arm) != "disabled") {
                for (const auto& [id, row] : results) {
                    const auto& target = joins.at(id);
                    if (target.at("window").at("read_id") != parent) {
                        continue;
                    }
                    const auto result = read(row.at("result").at("path").get<std::string>());
                    const auto replacement = std::string(arm) == "diagnostic_union_nn"
                                                     ? union_nn.at(id)
                                                     : result.at("outcome")
                                                               .at(arm)
                                                               .at("sequence")
                                                               .get<std::string>();
                    dna(replacement);
                    const auto a = integer(target.at("owned_start")),
                               b = integer(target.at("owned_end"));
                    require(a <= b && b <= original.size() &&
                                    original.substr(a, b - a) ==
                                            target.at("nomination").at(15).get<std::string>(),
                            "Owned edit does not match actual native parent");
                    if (replacement != original.substr(a, b - a)) {
                        changes.push_back({a, b, replacement, id});
                    }
                }
            }
            std::sort(changes.begin(), changes.end(),
                      [](const auto& a, const auto& b) { return a.a < b.a; });
            std::string sequence, qualities;
            std::size_t cursor{};
            for (const auto& change : changes) {
                require(cursor <= change.a, "Owned edits overlap");
                sequence += original.substr(cursor, change.a - cursor) + change.replacement;
                qualities += quality.substr(cursor, change.a - cursor) +
                             std::string(change.replacement.size(), '!');
                cursor = change.b;
                arm_edits.push_back({{"query_index", change.query},
                                     {"parent", parent},
                                     {"start", change.a},
                                     {"end", change.b},
                                     {"stock", original.substr(change.a, change.b - change.a)},
                                     {"replacement", change.replacement}});
            }
            sequence += original.substr(cursor);
            qualities += quality.substr(cursor);
            auto reverse_sequence = original, reverse_quality = quality;
            for (auto it = changes.rbegin(); it != changes.rend(); ++it) {
                reverse_sequence.replace(it->a, it->b - it->a, it->replacement);
                reverse_quality.replace(it->a, it->b - it->a,
                                        std::string(it->replacement.size(), '!'));
            }
            require(sequence == reverse_sequence && qualities == reverse_quality,
                    "Independent complete SEQ/Q edit reconstruction differs");
            if (std::string(arm) == "disabled") {
                require(sequence == original && qualities == quality,
                        "Disabled edit identity failed");
            }
            sam += parent + "\t4\t*\t0\t0\t*\t*\t0\t0\t" + sequence + '\t' + qualities + '\n';
        }
        const auto path = output / (std::string(arm) + ".sam");
        fresh(path, sam);
        arm_outputs.push_back({{"arm", arm},
                               {"sam", pin(path)},
                               {"edits", arm_edits},
                               {"parents", parents.size()},
                               {"diagnostic_only", std::string(arm) == "diagnostic_union_nn"}});
    }
    write(output / "diagnostic-union.json", union_diagnostics);
    complete(output, "uncertainty-feedback-parent-emission/1",
             {{"plan", planned},
              {"plan_sha256", planned.at("plan_sha256")},
              {"decoded", decoded},
              {"arms", arm_outputs},
              {"union_nn_diagnostic", pin(output / "diagnostic-union.json")},
              {"union_comparison_scope",
               "Prior=none over actual same-invocation U is diagnostic; qualified context gates "
               "retain escape-H baseline, so this is not a fully matched policy comparison"},
              {"nomination_rows", joins.size()},
              {"decoded_rows", results.size()},
              {"population_complete", results.size() == joins.size()},
              {"conditioned_only_sequences", conditioned_only},
              {"partial_search_differences", partial_differences},
              {"selected_different_from_final_rerank", selected_vs_final},
              {"quality_policy",
               "Only changed owned centers receive uncalibrated !; all other actual native SEQ/Q "
               "preserved"},
              {"all_64_native_sam_parents_preserved", parents.size() == 64}});
}
}
