#include "context_decision/decision.h"
#include "context_decision/runtime.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <tuple>

namespace context_decision {
namespace {
using namespace context_study;
CandidateCase sample() {
    CandidateCase value;
    value.native = "A";
    value.availability = "usable";
    value.paths = {"CCC"};
    value.candidates.emplace("A", Candidate{"A", native_origin, GuardedLogMass{0}});
    value.candidates.emplace("C", Candidate{"C", escape_origin, GuardedLogMass{0.25}});
    return value;
}
std::string enumerate(const CandidateCase &input, bool partial) {
    const auto free = replay(input).at("reference_free");
    std::vector<std::tuple<double, bool, std::string>> ranked;
    const auto origins = native_origin | escape_origin | (partial ? conditioned_origin : 0U);
    for (const auto &[sequence, candidate] : input.candidates) {
        if ((candidate.origins & origins) == 0 || !candidate.log_mass ||
            candidate.log_mass->value < free.log_mass - 0.5)
            continue;
        std::vector<std::size_t> distances;
        for (const auto &path : input.paths)
            distances.push_back(distance(sequence, path));
        const double objective =
            candidate.log_mass->value -
            0.5 * static_cast<double>(*std::min_element(distances.begin(), distances.end()));
        ranked.emplace_back(-objective, sequence != input.native, sequence);
    }
    std::sort(ranked.begin(), ranked.end());
    return std::get<2>(ranked.front());
}
}
std::size_t controls() {
    std::size_t assertions = 0;
    auto check = [&](bool condition, const std::string &message) {
        require(condition, message);
        ++assertions;
    };
    auto throws = [&](auto action) {
        bool rejected = false;
        try {
            action();
        } catch (const std::invalid_argument &) {
            rejected = true;
        }
        check(rejected, "invalid input accepted");
    };
    auto input = sample();
    input.paths = {"CCCC"};
    input.candidates.emplace("CCCC", Candidate{"CCCC", escape_origin, GuardedLogMass{-0.5}});
    input.candidates.emplace("CCC", Candidate{"CCC", escape_origin, GuardedLogMass{-0.25}});
    const auto old = replay(input);
    check(old.at("final_rerank").sequence == "C" &&
              old.at("final_rerank").gate == "signal_deficit_fallback",
          "witness must exercise historical winner veto");
    const auto rescued = choose(input, false);
    check(rescued.proposed.sequence == "CCC" && rescued.accepted.sequence == "CCC",
          "feasible candidate not rescued at inclusive deficit and margin boundaries");
    check(rescued.accepted.gate == "context_selected", "boundary equality rejected");
    input.candidates.at("CCC").log_mass->value = -0.25 - 1e-8;
    check(choose(input, false).accepted.sequence == "C", "deficit below boundary accepted");
    input = sample();
    input.candidates.emplace("CC", Candidate{"CC", escape_origin, GuardedLogMass{0.25}});
    check(choose(input, false).accepted.sequence == "CC", "margin equality rejected");
    input.candidates.at("CC").log_mass->value = 0.25 - 1e-8;
    check(choose(input, false).accepted.sequence == "C", "submargin candidate accepted");
    input = sample();
    input.candidates.emplace("CC", Candidate{"CC", conditioned_origin, GuardedLogMass{0.25}});
    check(choose(input, false).accepted.sequence == "C", "escape pool admitted conditioned-only");
    check(choose(input, true).accepted.sequence == "CC",
          "partial pool missed conditioned candidate");
    input.candidates.emplace("CCC", Candidate{"CCC", graph_origin, std::nullopt});
    check(choose(input, true).accepted.sequence == "CC",
          "unscored graph candidate became eligible");
    for (const auto *status : {"missing", "ambiguous"}) {
        input.availability = status;
        input.paths.clear();
        const auto value = choose(input, true);
        check(value.accepted.sequence == "C" && value.accepted.sequence != input.native,
              "unavailable context did not return actual matched reference-free arm");
    }
    input = sample();
    input.candidates.emplace("TT", Candidate{"TT", 16U, std::nullopt});
    check(choose(input, false).accepted.sequence == "C", "unknown unscored origin became eligible");
    check(choose(input, false, 0).accepted.sequence == "C" &&
              choose(input, true, 0).accepted.sequence == "C",
          "lambda zero identity failed");
    input.conditioned_capped = true;
    check(choose(input, true).accepted.sequence == input.native, "old partial cap policy changed");
    check(choose(input, true, 0).accepted.sequence == "C", "lambda zero cap identity failed");
    input = sample();
    input.candidates.at("A").log_mass->value = 0.25;
    input.paths = {"A", "C"};
    check(choose(input, false).proposed.sequence == "A", "native tie preference changed");
    input.native = "G";
    input.candidates.clear();
    for (const auto *sequence : {"G", "A", "C"})
        input.candidates.emplace(sequence, Candidate{sequence, escape_origin, GuardedLogMass{0}});
    input.candidates.at("G").origins |= native_origin;
    input.paths = {"A", "C"};
    check(choose(input, false).proposed.sequence == "A", "lexicographic tie changed");
    const auto ordered = choose(input, true);
    std::reverse(input.paths.begin(), input.paths.end());
    input.paths.push_back("A");
    check(choose(input, true).accepted.sequence == ordered.accepted.sequence,
          "path ordering/duplication changed decision");
    input.candidates.at("A").log_mass->value = std::numeric_limits<double>::infinity();
    throws([&] { static_cast<void>(choose(input, false)); });
    throws([&] {
        static_cast<void>(choose(sample(), false, std::numeric_limits<double>::quiet_NaN()));
    });
    throws(
        [&] { static_cast<void>(parse_options("replay", {"--output", "x", "--unknown", "y"})); });
    // Independent Cartesian census. No truth, masks, or private labels enter these cases.
    for (int a = -4; a <= 4; ++a)
        for (int b = -4; b <= 4; ++b)
            for (int c = -4; c <= 4; ++c)
                for (const auto &paths :
                     {std::vector<std::string>{"A"}, std::vector<std::string>{"CCC", "AA"}}) {
                    auto value = sample();
                    value.paths = paths;
                    value.candidates.at("A").log_mass->value = static_cast<double>(a) / 4;
                    value.candidates.at("C").log_mass->value = static_cast<double>(b) / 4;
                    value.candidates.emplace("CC",
                                             Candidate{"CC", conditioned_origin,
                                                       GuardedLogMass{static_cast<double>(c) / 4}});
                    for (const bool partial : {false, true})
                        check(choose(value, partial).proposed.sequence == enumerate(value, partial),
                              "constrained argmax differs from independent enumerator");
                }
    Packet packet;
    for (const auto &id : {"ordinary/0/ordinary", "ordinary/1/ordinary", "ordinary/10/ordinary",
                           "ordinary/31/ordinary", "ordinary/32/ordinary", "private/0/withheld"}) {
        auto value = sample();
        value.id = id;
        value.domain = value.id.starts_with("ordinary/") ? "ordinary" : "private-withheld";
        packet.cases.push_back(value);
    }
    check(indices(packet, "query0").size() == 1, "query0 scope differs");
    check(indices(packet, "first32").size() == 3, "numeric first32 scope differs");
    check(indices(packet, "remaining").size() == 2, "remaining scope differs");
    check(indices(packet, "all").size() == 6, "all scope differs");
    return assertions;
}
}
