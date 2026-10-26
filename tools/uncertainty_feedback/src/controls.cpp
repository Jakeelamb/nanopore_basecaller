#include "uncertainty_feedback/core.h"

#include <iostream>

namespace uncertainty_feedback {
int controls() {
    std::size_t assertions{};
    const auto expect = [&assertions](bool condition) {
        require(condition, "Synthetic targeting control failed");
        ++assertions;
    };
    const auto rejects = [&expect](const auto& action) {
        bool failed = false;
        try {
            action();
        } catch (const std::exception&) {
            failed = true;
        }
        expect(failed);
    };
    rejects([] { static_cast<void>(parse("{\"x\":1,\"x\":2}")); });
    rejects([] { static_cast<void>(parse(std::string(34, '[') + "0" + std::string(34, ']'))); });
    rejects([] { static_cast<void>(natural("-1")); });
    rejects([] { static_cast<void>(cigar("2M0I")); });
    expect(reverse_complement("ACGTT") == "AACGT");
    const std::string reference = "AAAAAAAAAACGTTAAAAAAAAAA";
    Json window = {{"query_index", 0},
                   {"contig", "chr1"},
                   {"ref_start", 0},
                   {"ref_end", reference.size()},
                   {"reverse", false}};
    Json graph = {
            {"schema", "hprc-local-paths/1"},
            {"query_index", 0},
            {"query",
             {{"sample", "GRCh38"}, {"contig", "chr1"}, {"start", 0}, {"end", reference.size()}}},
            {"reference", {{"start", 0}, {"end", reference.size()}, {"sequence", reference}}},
            {"boundary_nodes", Json::array({">1", ">2"})},
            {"walks", Json::array({Json{{"is_reference", true},
                                        {"both_anchors", true},
                                        {"sequence", reference},
                                        {"cigar", std::to_string(reference.size()) + 'M'},
                                        {"copy_count", nullptr}}})}};
    expect(project(window, graph).at("centers") == Json::array({"CGTT"}));
    window["reverse"] = true;
    expect(project(window, graph).at("centers") == Json::array({"AACG"}));
    window["reverse"] = false;
    graph["walks"].push_back({{"is_reference", false},
                              {"both_anchors", true},
                              {"sequence", std::string(20, 'A')},
                              {"cigar", "10M4D10M"},
                              {"copy_count", nullptr}});
    expect(project(window, graph).at("centers") == Json::array({"", "CGTT"}));
    graph["walks"].push_back({{"is_reference", false},
                              {"both_anchors", false},
                              {"sequence", "A"},
                              {"cigar", "*"},
                              {"copy_count", nullptr}});
    expect(project(window, graph).at("exclusions").size() == 1);
    auto wrong = graph;
    wrong["query_index"] = 1;
    rejects([&] { static_cast<void>(project(window, wrong)); });
    wrong = graph;
    wrong["walks"][1]["cigar"] = "10M5D10M";
    rejects([&] { static_cast<void>(project(window, wrong)); });
    const auto snapshot_pin = dependencies().at("observation_snapshot");
    check(snapshot_pin);
    const auto masks = read(snapshot_pin.at("path").get<std::string>()).at("eligible");
    expect(frozen_masks(masks) == masks);
    rejects([] { static_cast<void>(frozen_masks(Json::object())); });
    auto wrong_masks = masks;
    wrong_masks.erase("500");
    rejects([&] { static_cast<void>(frozen_masks(wrong_masks)); });
    wrong_masks = masks;
    wrong_masks["100"] = masks.at("500");
    rejects([&] { static_cast<void>(frozen_masks(wrong_masks)); });
    const auto fixtures = dependencies().at("nomination_worker_fixtures");
    check(fixtures.at("collect"));
    check(fixtures.at("merge"));
    const auto collect = read(fixtures.at("collect").at("path").get<std::string>());
    const auto merge = read(fixtures.at("merge").at("path").get<std::string>());
    const auto validate_worker = [&](const Json& value, const std::string& phase) {
        validate_nomination_worker(value, phase, collect.at("source_id"), collect.at("prepared"));
    };
    validate_worker(collect, "collect");
    expect(!collect.contains("binary"));
    validate_worker(merge, "merge");
    expect(merge.contains("binary") && merge.contains("engineering"));
    wrong = merge;
    wrong.erase("binary");
    rejects([&] { validate_worker(wrong, "merge"); });
    wrong = collect;
    wrong["phase"] = "merge";
    rejects([&] { validate_worker(wrong, "collect"); });
    wrong = collect;
    wrong["binary"] = merge.at("binary");
    rejects([&] { validate_worker(wrong, "collect"); });
    wrong = merge;
    wrong["engineering"] = fixtures.at("collect");
    rejects([&] { validate_worker(wrong, "merge"); });
    wrong = merge;
    wrong["binary"] = dependencies().at("unchanged_decoder");
    rejects([&] { validate_worker(wrong, "merge"); });
    const auto original_scalar = dependencies().at("original_scalar");
    Json scalar = {{"schema", "uncertainty-feedback-scalars/1"},
                   {"complete", true},
                   {"source_witness", source_witness()},
                   {"binary", original_scalar.at("binary")},
                   {"build_receipt", original_scalar.at("build_receipt")},
                   {"compiler_version", original_scalar.at("compiler_version")},
                   {"runtime", original_scalar.at("runtimes").at("scalar")},
                   {"sha256_runtime", original_scalar.at("runtimes").at("sha256")},
                   {"sources", scalar_build_inputs()}};
    validate_scalar_build(scalar);
    expect(true);
    wrong = scalar;
    wrong["binary"] = dependencies().at("unchanged_decoder");
    rejects([&] { validate_scalar_build(wrong); });
    wrong = scalar;
    wrong["source_witness"] =
            read(original_scalar.at("connector_witness").at("path").get<std::string>())
                    .at("source_witness");
    rejects([&] { validate_scalar_build(wrong); });
    wrong = scalar;
    wrong["build_receipt"] = original_scalar.at("compiler_version");
    rejects([&] { validate_scalar_build(wrong); });
    std::cout << Json{{"schema", "uncertainty-feedback-controls/1"},
                      {"synthetic_only", false},
                      {"metadata_only", true},
                      {"genuine_worker_metadata", fixtures},
                      {"original_scalar_dependency", original_scalar.at("build_receipt")},
                      {"assertions", assertions},
                      {"biological_qualification", false},
                      {"source_witness", source_witness()}}
                         .dump()
              << '\n';
    return 0;
}
}
