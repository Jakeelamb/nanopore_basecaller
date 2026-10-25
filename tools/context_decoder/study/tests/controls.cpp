#include "context_study/oracle.h"
#include "wire_fields.h"
#include <algorithm>
#include <functional>
#include <limits>
#include <sstream>

namespace context_study {
namespace {
struct Brute {
    std::size_t cost{std::numeric_limits<std::size_t>::max()};
    Counts counts{};
    std::vector<std::set<std::size_t>> cuts;
    std::uint32_t any_mask_min{std::numeric_limits<std::uint32_t>::max()};
};
Brute enumerate(const std::string &reference, const std::string &query,
                const std::vector<GenomicSpan> &masks) {
    Brute result;
    result.cuts.resize(reference.size() + 1);
    std::vector<std::pair<std::size_t, std::size_t>> vertices{{0, 0}};
    auto inside = [&](std::size_t r) {
        for (const auto &span : masks)
            if (span.begin <= r && r < span.end)
                return true;
        return false;
    };
    auto flank = [&](std::size_t r) {
        if (r == 0)
            return false;
        for (const auto &span : masks)
            if (span.begin <= r - 1 && r < span.end)
                return true;
        return false;
    };
    std::function<void(std::size_t, std::size_t, std::size_t, std::array<std::uint32_t, 5>)> visit;
    visit = [&](std::size_t r, std::size_t q, std::size_t cost,
                std::array<std::uint32_t, 5> counts) {
        if (r == reference.size() && q == query.size()) {
            result.any_mask_min = std::min(result.any_mask_min, counts[4]);
            if (cost < result.cost) {
                result.cost = cost;
                for (std::size_t k = 0; k < counts.size(); ++k)
                    result.counts[k] = {counts[k], counts[k]};
                for (auto &cuts : result.cuts)
                    cuts.clear();
            }
            if (cost == result.cost) {
                for (std::size_t k = 0; k < counts.size(); ++k) {
                    result.counts[k].minimum = std::min(result.counts[k].minimum, counts[k]);
                    result.counts[k].maximum = std::max(result.counts[k].maximum, counts[k]);
                }
                for (const auto &[cut_r, cut_q] : vertices)
                    result.cuts[cut_r].insert(cut_q);
            }
            return;
        }
        auto step = [&](std::size_t nr, std::size_t nq, std::size_t extra, std::size_t category,
                        bool counted) {
            auto updated = counts;
            if (counted) {
                ++updated[category];
                if (category != 0)
                    ++updated[4];
            }
            vertices.emplace_back(nr, nq);
            visit(nr, nq, cost + extra, updated);
            vertices.pop_back();
        };
        if (r < reference.size() && q < query.size()) {
            const bool different = reference[r] != query[q];
            step(r + 1, q + 1, static_cast<std::size_t>(different), different ? 1 : 0, inside(r));
        }
        if (r < reference.size())
            step(r + 1, q, 1, 3, inside(r));
        if (q < query.size())
            step(r, q + 1, 1, 2, flank(r));
    };
    visit(0, 0, 0, {});
    return result;
}
CandidateCase fixture() {
    CandidateCase input;
    input.id = "synthetic";
    input.domain = "ordinary";
    input.native = "AC";
    input.availability = "usable";
    input.paths = {"A"};
    input.candidates.emplace("AC", Candidate{"AC", native_origin, GuardedLogMass{-1}});
    input.candidates.emplace("A",
                             Candidate{"A", escape_origin, GuardedLogMass{-1.43538991034512264}});
    return input;
}
RawPacket wire_fixture() {
    auto input = fixture();
    RawPacket result{sha256("synthetic manifest"), {}};
    Record record(wire::candidate_widths.at("CASE"));
    record[0] = "CASE";
    {
        using namespace wire::CASE;
        record[case_id] = input.id;
        record[domain] = input.domain;
        record[parent] = "parent";
        record[contig] = "chr1";
        record[strand] = "+";
        record[read_start] = "0";
        record[read_end] = "2";
        record[owned_start] = "0";
        record[owned_end] = "2";
        record[ref_start] = "0";
        record[ref_end] = "2";
        record[core_start] = "0";
        record[core_end] = "2";
        record[future_bases] = "0";
        record[left_guard] = "";
        record[right_guard] = "";
        record[native] = input.native;
        record[availability] = input.availability;
        record[escape_capped] = "0";
        record[conditioned_capped] = "0";
        record[escape_empty] = "0";
        record[conditioned_empty] = "0";
        record[geometry_ancestry_sha256] = sha256("synthetic native ancestry");
        std::string geometry = "context-geometry/1";
        for (const auto position : wire::geometry_indices)
            geometry += '\t' + record[position];
        record[geometry_sha256] = sha256(geometry + '\n');
    }
    result.records.push_back(record);
    result.records.push_back({"PATH", input.id, "A"});
    for (const auto &[sequence, candidate] : input.candidates) {
        std::ostringstream number;
        number.precision(17);
        number << candidate.log_mass->value;
        result.records.push_back(
            {"CAND", input.id, sequence, std::to_string(candidate.origins), number.str()});
    }
    const auto historical = replay(input);
    for (const auto *role : roles) {
        const auto &choice = historical.at(role);
        std::ostringstream mass, potential, objective;
        mass.precision(17);
        potential.precision(17);
        objective.precision(17);
        mass << choice.log_mass;
        potential << choice.potential;
        objective << choice.objective;
        result.records.push_back({"BASE", input.id, role, choice.sequence, mass.str(),
                                  potential.str(), objective.str(), choice.gate,
                                  choice.abstained ? "1" : "0"});
    }
    return result;
}
}
std::string run_controls() {
    std::size_t assertions{};
    auto check = [&](bool condition, const std::string &message) {
        ++assertions;
        require(condition, "control failed: " + message);
    };
    std::vector<std::string> strings{""};
    for (std::size_t length = 1; length <= 3; ++length) {
        const auto before = strings.size();
        for (std::size_t i = 0; i < before; ++i)
            if (strings[i].size() == length - 1) {
                const auto parent = strings[i];
                strings.push_back(parent + 'A');
                strings.push_back(parent + 'C');
            }
    }
    bool defeated_class_minimum = false, defeated_mask_only = false, defeated_traceback = false;
    std::size_t alignments{};
    for (const auto &reference : strings)
        for (const auto &query : strings) {
            std::vector<std::vector<GenomicSpan>> masks{{}};
            for (std::size_t begin = 0; begin < reference.size(); ++begin)
                for (std::size_t end = begin + 1; end <= reference.size(); ++end)
                    masks.push_back({{begin, end}});
            if (reference.size() >= 3)
                masks.push_back({{0, 1}, {2, 3}});
            for (const auto &mask : masks) {
                const auto expected = enumerate(reference, query, mask);
                const EditDag actual(reference, query);
                ++alignments;
                check(actual.optimum() == expected.cost, "all-path global edit cost");
                check(actual.counts(mask) == expected.counts,
                      "all-path masked class and direct error extrema");
                for (std::size_t cut = 0; cut <= reference.size(); ++cut) {
                    check(actual.cuts(cut) == expected.cuts[cut], "all-path cut union");
                    defeated_traceback = defeated_traceback || expected.cuts[cut].size() > 1;
                }
                const auto sum_min = expected.counts[1].minimum + expected.counts[2].minimum +
                                     expected.counts[3].minimum;
                defeated_class_minimum =
                    defeated_class_minimum || sum_min < expected.counts[4].minimum;
                defeated_mask_only =
                    defeated_mask_only || expected.any_mask_min < expected.counts[4].minimum;
            }
        }
    check(defeated_class_minimum, "negative control rejects summed per-class minima");
    check(defeated_mask_only,
          "negative control rejects minimizing masked errors instead of global edit cost");
    check(defeated_traceback, "negative control rejects one traceback for event cuts");
    check(EditDag("AAA", "AAAA").counts({{1, 2}})[2] == Range{0, 0},
          "one-base mask has no two-flank insertion exposure");
    check(EditDag("AAA", "AAAA").counts({{0, 1}, {2, 3}})[2] == Range{0, 0},
          "insertion cannot bridge mask gap");
    check(std::string(effect({0, 1}, {1, 2}, true, true, false)) == "unresolved",
          "overlapping count intervals unresolved");
    check(std::string(effect({0, 0}, {1, 1}, true, false, false)) == "no_exposure",
          "empty exposure never correction");
    check(std::string(effect({0, 0}, {1, 1}, false, true, false)) == "unresolved",
          "boundary uncertainty blocks positive label");
    check(std::string(effect({0, 0}, {1, 1}, true, true, false)) == "helpful",
          "strict separated improvement");
    check(std::string(effect({2, 2}, {1, 1}, true, true, false)) == "harmful",
          "strict separated harm");
    ExactEvent event{"event", "ACGTA", "T", "ACTTA", ".", 2, 3, true};
    check(event_call("ACTTA", event) == AlleleCall::alt, "exact ALT");
    check(event_call("ACGTA", event) == AlleleCall::ref, "exact REF");
    check(event_call("ACCTA", event) == AlleleCall::other, "exact other");
    event.resolved = false;
    event.reason = "archive ambiguity";
    check(event_call("ACTTA", event) == AlleleCall::unresolved, "archive ambiguity retained");
    ExactEvent repeat{"repeat", "AAAA", "AA", "AAAAA", ".", 1, 3, true};
    check(event_call("AAAAA", repeat) == AlleleCall::unresolved,
          "homopolymer event cuts unresolved");
    auto input = fixture();
    const auto historical = replay(input);
    check(historical.at("context_winner").sequence == "A", "query21-shaped raw winner");
    check(historical.at("selected").sequence == "AC" &&
              historical.at("selected").gate == "objective_margin_fallback",
          "query21-shaped margin gate refuses raw winner");
    input.candidates.emplace("", Candidate{"", conditioned_origin, GuardedLogMass{5}});
    const auto conditioned = replay(input);
    check(conditioned.at("reference_free").sequence == "AC" &&
              conditioned.at("final_rerank_winner").sequence == "A" &&
              conditioned.at("context_winner").sequence.empty(),
          "conditioned-only absent from historical free and final pools");
    input.candidates.emplace("AAA", Candidate{"AAA", graph_origin, GuardedLogMass{100}});
    input.candidates.emplace("GG", Candidate{"GG", graph_origin, std::nullopt});
    check(replay(input).at("context_winner").sequence.empty(),
          "scored graph-only excluded from inference");
    input.candidates.at("AC").origins |= graph_origin;
    check(replay(input).at("reference_free").sequence == "AC",
          "graph alias preserves native inference identity");
    input.availability = "missing";
    input.paths.clear();
    check(replay(input).at("selected").sequence == "AC",
          "missing context free fallback excludes conditioned-only");
    input.escape_capped = true;
    check(replay(input).at("selected").sequence == "AC" && replay(input).at("selected").abstained,
          "escape cap abstains to native");
    input = fixture();
    input.candidates.at("A").log_mass = GuardedLogMass{-1};
    input.paths = {"A", "AC"};
    check(replay(input).at("final_rerank_winner").sequence == "AC", "native-first objective ties");
    input.native = "T";
    input.candidates.erase("AC");
    input.candidates.emplace("T", Candidate{"T", native_origin, GuardedLogMass{-9}});
    input.candidates.emplace("C", Candidate{"C", escape_origin, GuardedLogMass{-1}});
    input.paths = {"A", "C"};
    check(replay(input).at("reference_free").sequence == "A", "lexical tie after native");
    input = fixture();
    input.native = "AAAA";
    input.paths = {"C"};
    input.candidates.clear();
    input.candidates.emplace("AAAA", Candidate{"AAAA", native_origin, GuardedLogMass{-1}});
    input.candidates.emplace("C", Candidate{"C", escape_origin, GuardedLogMass{-1.6}});
    check(replay(input).at("selected").gate == "signal_deficit_fallback",
          "signal deficit rejects favorable context winner");
    input.candidates.at("C").log_mass = GuardedLogMass{-1.5};
    check(replay(input).at("selected").sequence == "C", "exact signal deficit threshold admitted");
    CandidateCase boundary;
    boundary.left = "C";
    boundary.right = "G";
    boundary.native = "AA";
    boundary.reference = {0, 4};
    boundary.core = {1, 3};
    OracleTruth truth{"", "CAAG", {{{{1, 3}}, {{1, 3}}}}, {}};
    const auto forward =
        observe(boundary, Candidate{"AA", native_origin, GuardedLogMass{0}}, truth);
    check(forward.boundary, "unambiguous guarded center boundary");
    boundary.reverse = true;
    boundary.left = "C";
    boundary.right = "G";
    boundary.native = "TT";
    const auto reverse =
        observe(boundary, Candidate{"TT", native_origin, GuardedLogMass{0}}, truth);
    check(reverse.boundary && reverse.counts == forward.counts,
          "reverse orientation evaluated once");
    boundary.reverse = false;
    boundary.left = "A";
    boundary.right = "A";
    boundary.native = "AA";
    truth.reference = "AAAA";
    check(!observe(boundary, Candidate{"A", escape_origin, GuardedLogMass{0}}, truth).boundary,
          "repeat deletion crosses guard ownership");
    boundary.left = "A";
    boundary.right = "CG";
    boundary.future = 1;
    boundary.native = "T";
    truth.reference = "ATCG";
    boundary.reference = {0, 4};
    boundary.core = {1, 2};
    truth.events = {ExactEvent{"trim", "ATC", "T", "ATC", ".", 1, 2, true}};
    const auto trimmed = observe(boundary, Candidate{"T", native_origin, GuardedLogMass{0}}, truth);
    check(trimmed.events[0] == AlleleCall::alt, "future guard removed before private orientation");
    check(oriented("ATC", true) == "GAT", "reverse complement after trimming");
    bool rejected_nonfinite = false, rejected_integer = false;
    try {
        static_cast<void>(finite_number("nan"));
    } catch (const std::exception &) {
        rejected_nonfinite = true;
    }
    try {
        static_cast<void>(natural("01"));
    } catch (const std::exception &) {
        rejected_integer = true;
    }
    check(rejected_nonfinite && rejected_integer, "finite score and canonical coordinate parser");
    const auto raw = wire_fixture();
    const auto parsed = parse_candidates(raw);
    check(parsed.cases.size() == 1 && parsed.cases[0].candidates.size() == 2,
          "genuine synthetic wire handoff");
    verify_replay(parsed.cases[0], replay(parsed.cases[0]));
    auto rejects = [&](RawPacket malformed, const std::string &message) {
        bool rejected = false;
        try {
            static_cast<void>(parse_candidates(malformed));
        } catch (const std::exception &) {
            rejected = true;
        }
        check(rejected, message);
    };
    auto malformed = raw;
    malformed.records.push_back({"TRUTH", "synthetic", sha256(""), "AC"});
    rejects(malformed, "truth record rejected by inference parser");
    malformed = raw;
    malformed.records[0].push_back("truth_field");
    rejects(malformed, "extra inference field rejected");
    malformed = raw;
    malformed.records[0][wire::CASE::geometry_sha256] = sha256("wrong");
    rejects(malformed, "wrong geometry rejected");
    malformed = raw;
    malformed.records[0][wire::CASE::owned_end] = "3";
    rejects(malformed, "coordinate binding mutation rejected");
    malformed = raw;
    malformed.records.push_back({"CAND", "synthetic", "AC", "8", "99"});
    rejects(malformed, "duplicate candidate score conflict rejected");
    malformed = raw;
    malformed.records.push_back({"CAND", "synthetic", "A", "2", "nan"});
    rejects(malformed, "nonfinite retained log mass rejected");
    malformed = raw;
    malformed.records.push_back({"CAND", "synthetic", "A", "4294967297", "0"});
    rejects(malformed, "origin truncation rejected");
    malformed = raw;
    malformed.records.push_back(raw.records[0]);
    rejects(malformed, "duplicate case identity rejected");
    malformed = raw;
    malformed.records.push_back({"CAND", "synthetic", "AC", "8", "-1"});
    const auto aliased = parse_candidates(malformed);
    check(aliased.cases[0].candidates.at("AC").origins == (native_origin | graph_origin) &&
              replay(aliased.cases[0]).at("reference_free").sequence == "AC",
          "duplicate graph alias preserves real score and replay");
    std::ostringstream result;
    result << "{\"schema\":\"context-study-controls/"
              "1\",\"synthetic_only\":true,\"data_qualification\":false,\"assertions\":"
           << assertions << ",\"exhaustive_alignments\":" << alignments
           << ",\"independent_all_path_enumeration\":true,\"negative_controls\":{\"summed_class_"
              "extrema\":true,\"masked_objective\":true,\"single_traceback\":true},\"private_"
              "calls\":true,\"historical_pool_gate_ties\":true,\"graph_alias_and_unscored\":true,"
              "\"empty_and_reverse\":true,\"strict_inference_packet_rejections\":true}";
    return result.str();
}
}
