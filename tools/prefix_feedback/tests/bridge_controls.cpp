#include "prefix_feedback/bridge.h"

#include <algorithm>
#include <cmath>
#include <functional>
#include <iostream>

namespace prefix_feedback {
namespace {
void near(double a, double b) {
    require(std::abs(a - b) < 1e-10, "bridge numerical census differs");
}
void rejects(const std::function<void()>& action) {
    bool caught{};
    try {
        action();
    } catch (const std::exception&) {
        caught = true;
    }
    require(caught, "bridge rejection control accepted");
}
Session tiny(std::size_t rows = 4) {
    auto session = start({"bridge", std::string(64, 'a'), 1, 0, {1, 16, 1, 8, 0.5}});
    Block block{{{"block_index", 0},
                 {"read_id", "bridge"},
                 {"orientation", "signal-forward"},
                 {"available_signal_end", 100},
                 {"chunk_index", 0},
                 {"chunk_row_begin", 0},
                 {"chunk_row_end", rows}},
                0,
                rows,
                std::vector<double>(rows * 16, 0.125)};
    advance(session, block, std::nullopt);
    return session;
}
Json binding(const Session& session, const std::string& sequence) {
    const Json literal{
            {"path", "/pure-semantic-fixture"}, {"size", 0}, {"sha256", std::string(64, 'a')}};
    return {{"source_sha256", source_id()},
            {"plan_sha256", session.spec.plan_sha256},
            {"input_tensor", literal},
            {"read_id", session.spec.read_id},
            {"parent_index", 0},
            {"chunk_index", 0},
            {"block_index", 0},
            {"availability",
             {{"kind", "released-score-block"},
              {"row_begin", 0},
              {"row_end", session.consumed_rows},
              {"available_row_end", session.consumed_rows},
              {"chunk_lookahead", "whole_chunk"},
              {"signal_geometry", nullptr}}},
            {"previous_state_sha256", std::string(64, 'b')},
            {"prefix_sha256", digest(sequence)},
            {"prefix_length", sequence.size()},
            {"orientation", "forward"},
            {"location_producer", literal},
            {"reference_free_producer", literal},
            {"identity_input", literal}};
}
Json normalized(const Session& session, Json& coverage) {
    const auto raw = batch(session, std::string(64, 'b'));
    const auto sequence = raw.at("provisional_prefix").get<std::string>();
    return normalize_candidates(
            session, raw, {{"sequence", sequence}, {"quality", std::string(sequence.size(), '!')}},
            binding(session, sequence), coverage);
}
Json sidecar(const Session& session, const Json& base, const std::string& sequence) {
    const auto native = base.at("native").at("sequence").get<std::string>();
    Json proposals = Json::array();
    proposals.push_back({{"id", "prefix-indel-" + digest(sequence)},
                         {"sequence", sequence},
                         {"edit",
                          {{"query_begin", 0},
                           {"query_end", native.size()},
                           {"reference", native},
                           {"alternate", sequence}}},
                         {"mechanism", "run-length-plus-minus-two"}});
    return {{"schema", "indel-prefix-proposals/1"},
            {"mode", "consumed-prefix-unscored-v1"},
            {"scoring_status", "unscored"},
            {"status", "ready"},
            {"source_batch",
             {{"path", "/pure-batch"}, {"size", 0}, {"sha256", std::string(64, 'a')}}},
            {"binding", base.at("binding")},
            {"scoring_descriptor", scoring_descriptor(session, base.at("binding"))},
            {"reference_free_candidate",
             {{"id", base.at("reference_free_candidate_id")},
              {"sequence", native},
              {"source_batch_sha256", std::string(64, 'a')}}},
            {"tail",
             {{"query_begin", 0},
              {"query_end", native.size()},
              {"selection", "deterministic-last-32-available-bases"}}},
            {"limits",
             {{"maximum_full_prefix_bases", 512},
              {"maximum_consumed_rows", 2048},
              {"maximum_tail_bases", 32},
              {"maximum_new_unique_proposals", 512},
              {"minimum_result_bases", 1},
              {"maximum_result_bases", 514}}},
            {"counts",
             {{"visited", 1},
              {"eligible", 1},
              {"unique", 1},
              {"duplicate", 0},
              {"excluded", 0},
              {"original_duplicates", 0}}},
            {"arm_exclusions", Json::array()},
            {"exclusions", Json::array()},
            {"proposals", proposals},
            {"request_sha256", std::string(64, 'c')},
            {"source_files", Json::array()},
            {"complete", true}};
}
}
int bridge_controls() {
    std::size_t executed{}, failed{};
    auto run = [&](const char* name, const std::function<void()>& test) {
        ++executed;
        try {
            test();
            std::cout << "bridge PASS " << name << '\n';
        } catch (const std::exception& error) {
            ++failed;
            std::cerr << name << ": " << error.what() << '\n';
        }
    };
    run("strict-normalized-shape-and-genuine-free-identity", [] {
        const auto session = tiny();
        Json coverage = Json::array();
        const auto value = normalized(session, coverage);
        require(value.size() == 8 && value.at("kind") == "candidate-batch" &&
                        value.at("native").at("sequence") == "AAAA" &&
                        value.at("native").at("quality") == "!!!!" &&
                        value.at("reference_free_candidate_id") == digest("AAAA") &&
                        value.at("locations").empty(),
                "normalization shape/free differs");
        near(value.at("candidates").at(0).at("context_cost"), 0);
        near(value.at("candidates").at(0).at("neural_log_likelihood"), 0.5);
    });
    run("complete-panel-mixture-finite-cost-and-neutral-exhaustion", [] {
        auto session = tiny();
        Location a{"a", "chr1", "+", 0, 2, 2, 0, 2, 100, 0, "2M", "AA", {}};
        auto b = a;
        b.id = "b";
        b.strand = "-";
        b.continuation = "CC";
        session.locations = {a, b};
        const auto value = panel_cost(session, "AACC");
        near(value.value, -std::log((1.0 + std::exp(-2.0)) / 2.0));
        require(value.coverage.size() == 2 && value.coverage.at(0).at("covered_emissions") == 2,
                "panel census differs");
        std::reverse(session.locations.begin(), session.locations.end());
        const auto permuted = panel_cost(session, "AACC");
        require(permuted.value == value.value && permuted.coverage == value.coverage,
                "panel permutation changed cost/coverage");
        const auto exhausted = panel_cost(session, "AACCTT");
        near(exhausted.value, value.value);
        require(exhausted.coverage.at(0).at("neutral_emissions") == 2, "neutral exhaustion hidden");
    });
    run("new-indel-exact-uniform-mass-H-versus-U", [] {
        const auto session = tiny();
        Json coverage = Json::array(), report;
        const auto base = normalized(session, coverage);
        const auto proposal = sidecar(session, base, "AA");
        const auto value = merge_candidates(
                session, base, proposal, scoring_descriptor(session, base.at("binding")), report);
        require(value.at("reference_free_candidate_id") == digest("AAAA") &&
                        value.at("union_nn_candidate_id") == digest("AA"),
                "H was replaced or U not recomputed");
        near(likelihood(session, "AA"), std::log(6.0) + 0.25);
        require(report.at("scalar_calls") == 1 && value.at("candidates").size() == 2,
                "new scalar/candidate census differs");
    });
    run("native-relative-SNV-INS-DEL-edits-both-strands", [] {
        for (const bool reverse : {false, true}) {
            const auto source = reverse ? reverse_complement("AACG") : std::string("AACG");
            for (const auto& forward :
                 {std::string("ATCG"), std::string("AACGG"), std::string("ACG")}) {
                const auto target = reverse ? reverse_complement(forward) : forward;
                Json internal = Json::array();
                for (const auto& value : wire_edits(source, target)) {
                    internal.push_back({{"offset", value.at("query_position")},
                                        {"ref", value.at("reference")},
                                        {"alt", value.at("alternate")}});
                }
                require(apply_edits(source, internal) == target,
                        "wire edit reconstruction differs");
            }
        }
    });
    run("foreign-prior-binding-and-replacement-hard-rejections", [] {
        const auto session = tiny();
        Json coverage = Json::array(), report;
        const auto base = normalized(session, coverage);
        const auto good = sidecar(session, base, "AA");
        for (const auto* field : {"binding", "scoring_descriptor"}) {
            auto bad = good;
            bad[field]["source_sha256"] = std::string(64, 'f');
            rejects([&] {
                merge_candidates(session, base, bad,
                                 scoring_descriptor(session, base.at("binding")), report);
            });
        }
        auto bad = good;
        bad["proposals"][0]["edit"]["reference"] = "TTTT";
        rejects([&] {
            merge_candidates(session, base, bad, scoring_descriptor(session, base.at("binding")),
                             report);
        });
        bad = good;
        bad["scoring_descriptor"]["prior"] = "conditional-native-context";
        rejects([&] {
            merge_candidates(session, base, bad, scoring_descriptor(session, base.at("binding")),
                             report);
        });
    });
    run("permutation-no-context-and-source-rank-separation", [] {
        auto session = tiny();
        auto raw = batch(session, "prior");
        raw["candidates"][0]["context_cost"] = nullptr;
        raw["candidates"][0]["partial_rank"] = -9999;
        Json coverage = Json::array();
        const auto sequence = std::string("AAAA");
        const auto value =
                normalize_candidates(session, raw, {{"sequence", sequence}, {"quality", "!!!!"}},
                                     binding(session, sequence), coverage);
        require(value.at("candidates")[0].at("eligibility_reasons").empty(),
                "snapshot provenance labels became policy rejections");
        near(value.at("candidates")[0].at("context_cost"), 0);
        std::reverse(session.signal.begin(), session.signal.end());
        Json other = Json::array();
        require(normalized(session, other) == value, "path permutation changed normalized batch");
    });
    run("abstention-missing-identity-and-missing-H", [] {
        const auto session = tiny();
        auto raw = batch(session, "prior");
        Json coverage = Json::array();
        rejects([&] {
            normalize_candidates(session, raw, {{"sequence", ""}, {"quality", ""}},
                                 binding(session, ""), coverage);
        });
        raw["reference_free_candidate_id"] = nullptr;
        rejects([&] {
            normalize_candidates(session, raw, {{"sequence", "AAAA"}, {"quality", "!!!!"}},
                                 binding(session, "AAAA"), coverage);
        });
        raw["abstained"] = true;
        rejects([&] { normalize_candidates(session, raw, {}, {}, coverage); });
    });
    run("excluded-new-arm-and-impossible-proposals-preserve-original", [] {
        const auto session = tiny();
        Json coverage = Json::array(), report;
        const auto base = normalized(session, coverage);
        auto proposal = sidecar(session, base, "AAAAA");
        auto value = merge_candidates(session, base, proposal,
                                      scoring_descriptor(session, base.at("binding")), report);
        require(value == base && report.at("scoring_exclusions").size() == 1,
                "impossible proposal erased original or was hidden");
        proposal["status"] = "excluded";
        proposal["arm_exclusions"] = Json::array({"declared-bound"});
        proposal["proposals"] = Json::array();
        value = merge_candidates(session, base, proposal,
                                 scoring_descriptor(session, base.at("binding")), report);
        require(value == base && report.at("new_arm_status") == "excluded",
                "whole-arm exclusion dropped original candidates");
        const auto larger = tiny(8);
        coverage = Json::array();
        auto full = normalized(larger, coverage);
        full["candidates"] = Json::array();
        for (std::size_t code = 0; code < 4096; ++code) {
            auto remainder = code;
            std::string sequence(8, 'A');
            for (std::size_t position = sequence.size(); position > 0; --position) {
                sequence[position - 1] = std::string("ACGT")[remainder % 4];
                remainder /= 4;
            }
            full["candidates"].push_back({{"id", digest(sequence)},
                                          {"sequence", sequence},
                                          {"neural_log_likelihood", 1.0},
                                          {"context_cost", 0},
                                          {"location_ids", Json::array()},
                                          {"edits", wire_edits("AAAAAAAA", sequence)},
                                          {"eligibility_reasons", Json::array()}});
        }
        proposal = sidecar(larger, full, "AAAAAA");
        value = merge_candidates(larger, full, proposal,
                                 scoring_descriptor(larger, full.at("binding")), report);
        require(value == full &&
                        report.at("reason") == "full-union-exceeds-4096-preserve-original-arm" &&
                        report.at("scalar_calls") == 0,
                "union bound dropped original arm or performed new scoring");
    });
    std::cout << Json{{"bridge_executed", executed}, {"failed", failed}, {"skipped", 0}}.dump()
              << '\n';
    return failed == 0 ? 0 : 1;
}
}
