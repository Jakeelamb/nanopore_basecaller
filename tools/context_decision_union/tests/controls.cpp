#include "context_decision_union/union.h"
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <tuple>
#include <unistd.h>

namespace context_decision_union {
namespace {
using namespace context_study;
CandidateCase sample() {
    CandidateCase value;
    value.id = "ordinary/0/ordinary";
    value.domain = "ordinary";
    value.native = "A";
    value.availability = "missing";
    value.candidates.emplace("A", Candidate{"A", native_origin, GuardedLogMass{0}});
    value.candidates.emplace("C", Candidate{"C", escape_origin, GuardedLogMass{1}});
    value.saved = replay(value);
    return value;
}
RawPacket duplicate_packet() {
    RawPacket raw{std::string(64, 'a'), {}};
    Record geometry{"CASE",     "ordinary/0/ordinary",
                    "ordinary", "parent",
                    "chr",      "+",
                    "0",        "1",
                    "0",        "1",
                    "0",        "1",
                    "0",        "1",
                    "0",        "",
                    "",         "A",
                    "missing",  "0",
                    "0",        "0",
                    "0",        std::string(64, 'b'),
                    ""};
    std::string identity = "context-geometry/1";
    for (std::size_t i = 3; i <= 17; ++i)
        identity += '\t' + geometry[i];
    identity += '\t' + geometry[23] + '\n';
    geometry[24] = sha256(identity);
    raw.records.push_back(geometry);
    raw.records.push_back({"CAND", geometry[1], "A", "1", "0"});
    raw.records.push_back({"CAND", geometry[1], "C", "2", "1"});
    raw.records.push_back({"CAND", geometry[1], "C", "4", "1"});
    for (const auto &[role, choice] : sample().saved)
        raw.records.push_back({"BASE", geometry[1], role, choice.sequence,
                               std::to_string(choice.log_mass), std::to_string(choice.potential),
                               std::to_string(choice.objective), choice.gate,
                               choice.abstained ? "1" : "0"});
    return raw;
}
}
std::size_t controls() {
    using namespace context_study;
    std::size_t assertions = 0;
    auto check = [&](bool condition, const std::string &message) {
        require(condition, message);
        ++assertions;
    };
    auto rejects = [&](auto action) {
        bool rejected = false;
        try {
            action();
        } catch (const std::invalid_argument &) {
            rejected = true;
        }
        check(rejected, "invalid union input accepted");
    };
    auto input = sample();
    input.candidates.emplace("CC", Candidate{"CC", conditioned_origin, GuardedLogMass{2}});
    check(choose(input).choice.sequence == "CC", "conditioned neural maximum omitted");
    check(replay(input).at("reference_free").sequence == "C", "historical free changed");
    input.candidates.emplace("CCC", Candidate{"CCC", graph_origin, std::nullopt});
    input.candidates.emplace("CCCC", Candidate{"CCCC", graph_origin, GuardedLogMass{100}});
    check(choose(input).choice.sequence == "CC" && choose(input).eligible == 3 &&
              choose(input).graph_only == 2,
          "graph-only candidate became union eligible");
    for (unsigned flags = 0; flags < 16; ++flags) {
        input.escape_capped = (flags & 1U) != 0;
        input.conditioned_capped = (flags & 2U) != 0;
        input.escape_empty = (flags & 4U) != 0;
        input.conditioned_empty = (flags & 8U) != 0;
        check(choose(input).choice.sequence == "CC", "flags changed retained-U argmax");
    }
    Packet flagged;
    for (unsigned flags = 0; flags < 16; ++flags) {
        auto value = sample();
        value.id = "ordinary/" + std::to_string(flags) + "/ordinary";
        value.escape_capped = (flags & 1U) != 0;
        value.conditioned_capped = (flags & 2U) != 0;
        value.escape_empty = (flags & 4U) != 0;
        value.conditioned_empty = (flags & 8U) != 0;
        value.saved = replay(value);
        flagged.cases.push_back(value);
    }
    const auto control_output =
        std::filesystem::current_path() / ("union-control-output-" + std::to_string(::getpid()));
    check(!std::filesystem::exists(control_output),
          "fresh union output control directory required");
    std::filesystem::create_directory(control_output);
    static_cast<void>(diagnose(flagged, control_output));
    std::ifstream census(control_output / "union-census.tsv");
    std::string line;
    check(static_cast<bool>(std::getline(census, line)) &&
              line.ends_with("\tcap_or_empty_flags\tretained_pool_only"),
          "union census limitation columns differ");
    for (unsigned flags = 0; flags < 16; ++flags)
        check(static_cast<bool>(std::getline(census, line)) &&
                  line.ends_with(flags == 0 ? "\t0\t1" : "\t1\t1"),
              "union census lost retained-pool limitation or cap flag OR");
    check(!std::getline(census, line), "union census has unexpected rows");
    for (const auto *availability : {"usable", "missing", "ambiguous", "inconsistent"}) {
        input.availability = availability;
        check(choose(input).choice.sequence == "CC", "context availability changed neural maximum");
    }
    input = sample();
    input.candidates.at("A").log_mass->value = 1;
    check(choose(input).choice.sequence == "A", "native neural tie preference differs");
    input.candidates.emplace("CC", Candidate{"CC", conditioned_origin, GuardedLogMass{2}});
    input.candidates.at("C").log_mass->value = 2;
    check(choose(input).choice.sequence == "C", "lexical neural tie preference differs");
    input.candidates.emplace("", Candidate{"", conditioned_origin, GuardedLogMass{3}});
    check(choose(input).choice.sequence.empty() && choose(input).eligible == 4,
          "empty DNA candidate confused with empty scored U");
    input = sample();
    input.candidates.at("C").origins = escape_origin | conditioned_origin | graph_origin;
    const auto merged = choose(input);
    check(merged.eligible == 2 && merged.native == 1 && merged.escape == 1 &&
              merged.conditioned == 1 && merged.graph_only == 0,
          "union origin counts double-count sequence or lose provenance");
    auto raw = duplicate_packet();
    const auto parsed = parse_candidates(raw);
    check(parsed.cases.size() == 1 && parsed.cases[0].candidates.size() == 2 &&
              parsed.cases[0].candidates.at("C").origins == (escape_origin | conditioned_origin),
          "duplicate sequence did not merge genuine origin bits");
    check(choose(parsed.cases[0]).choice.sequence == "C" && choose(parsed.cases[0]).eligible == 2,
          "merged duplicate changed neural maximum or unique count");
    std::swap(raw.records[2], raw.records[3]);
    check(choose(parse_candidates(raw).cases[0]).choice.sequence == "C",
          "duplicate record ordering changed neural maximum");
    raw.records[3][4] = "2";
    rejects([&] { static_cast<void>(parse_candidates(raw)); });
    input = sample();
    input.candidates.at("C").log_mass.reset();
    rejects([&] { static_cast<void>(choose(input)); });
    input = sample();
    input.candidates.at("C").log_mass->value = std::numeric_limits<double>::infinity();
    rejects([&] { static_cast<void>(choose(input)); });
    input = sample();
    input.candidates.at("A").log_mass->value = std::numeric_limits<double>::quiet_NaN();
    rejects([&] { static_cast<void>(choose(input)); });
    input = sample();
    input.candidates.at("C").origins = 16;
    rejects([&] { static_cast<void>(choose(input)); });
    input = sample();
    input.candidates.at("C").origins |= native_origin;
    rejects([&] { static_cast<void>(choose(input)); });
    input.candidates.clear();
    rejects([&] { static_cast<void>(choose(input)); });
    for (const auto *role : roles) {
        input = sample();
        input.saved.at(role).log_mass += 1;
        rejects([&] { verify_replay(input, replay(input)); });
    }
    for (int a = -2; a <= 2; ++a)
        for (int b = -2; b <= 2; ++b)
            for (int c = -2; c <= 2; ++c) {
                input = sample();
                input.candidates.at("A").log_mass->value = static_cast<double>(a) / 2;
                input.candidates.at("C").log_mass->value = static_cast<double>(b) / 2;
                input.candidates.emplace("CC",
                                         Candidate{"CC", conditioned_origin,
                                                   GuardedLogMass{static_cast<double>(c) / 2}});
                std::vector<std::tuple<double, bool, std::string>> ranked;
                for (const auto &[sequence, candidate] : input.candidates)
                    ranked.emplace_back(-candidate.log_mass->value, sequence != input.native,
                                        sequence);
                std::sort(ranked.begin(), ranked.end());
                check(choose(input).choice.sequence == std::get<2>(ranked.front()),
                      "union neural maximum differs from independent enumerator");
            }
    input = sample();
    input.paths = {"A", "CC"};
    check(replay_bound(Packet{"", {input}}) == 8 * (1 + 2 + 1 + 2),
          "conservative historical replay cell bound differs");
    input.native = std::string(4096, 'A');
    input.candidates.clear();
    input.candidates.emplace(input.native,
                             Candidate{input.native, native_origin, GuardedLogMass{0}});
    input.paths.assign(32, std::string(4096, 'C'));
    rejects([&] { static_cast<void>(replay_bound(Packet{"", {input}})); });
    return assertions;
}
}
