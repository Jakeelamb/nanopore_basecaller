#include "context_study/oracle.h"
#include <algorithm>
#include <iomanip>
#include <limits>
#include <set>
#include <sstream>

namespace context_study {
namespace {
const char *private_effect(AlleleCall candidate, AlleleCall baseline) {
    if (candidate == AlleleCall::unresolved || baseline == AlleleCall::unresolved)
        return "unresolved";
    if (candidate == baseline)
        return "neutral";
    if (candidate == AlleleCall::alt)
        return "exact_alt_support_gained";
    if (baseline == AlleleCall::alt)
        return candidate == AlleleCall::ref ? "proven_alt_to_ref" : "exact_alt_support_lost_other";
    return "no_exact_alt_support";
}
}
std::string evaluate_packet(const Packet &packet, const TruthPacket &truths,
                            const std::filesystem::path &output) {
    std::ostringstream candidates, events, support, decisions;
    candidates << "case_id\tdomain\tparent\tcandidate_"
                  "sha256\tsequence\torigins\tscored\tmask\texposure\tboundary_resolved\tM_min\tM_"
                  "max\tX_min\tX_max\tI_min\tI_max\tD_min\tD_max\terror_min\terror_max\tvs_"
                  "native\tvs_reference_free\n";
    events << "case_id\tdomain\tparent\tcandidate_sha256\tevent_id\tcall\tnative_call\tfree_"
              "call\talt_to_ref\texact_alt_support_loss\talt_consequence_unresolved\tvs_native\tvs_"
              "reference_free\tunresolved_reason\n";
    support << "case_id\tdomain\tendpoint\tstage\tcandidates\tresolved_candidates\thelpful_vs_"
               "native\thelpful_vs_free\talt\tref\tother\tunresolved\n";
    decisions << "case_id\tdomain\tarm\tmask\tgate\tproposed_change\taccepted_change\traw_vs_"
                 "native\traw_vs_free\tselected_vs_native\tselected_vs_free\tprivate_raw_alt_to_"
                 "ref\tprivate_raw_support_loss\tprivate_raw_unresolved\n";
    std::size_t candidate_count{}, exposed_views{}, unresolved_boundaries{}, event_count{};
    std::set<std::string> parents, sites;
    std::map<std::string, std::size_t> census;
    std::map<std::string, std::set<std::string>> domain_parents;
    const std::array<unsigned, 4> stages{native_origin, native_origin | escape_origin,
                                         native_origin | escape_origin | conditioned_origin,
                                         native_origin | escape_origin | conditioned_origin |
                                             graph_origin};
    const std::array<const char *, 4> stage_names{"native", "escape", "conditioned", "graph"};
    for (const auto &input : packet.cases) {
        const auto &truth = truths.at(input.id);
        const auto historical = replay(input);
        verify_replay(input, historical);
        parents.insert(input.parent);
        domain_parents[input.domain].insert(input.parent);
        ++census[input.domain + "/cases"];
        std::map<std::string, Observation> observations;
        for (const auto &[sequence, candidate] : input.candidates)
            observations.emplace(sequence, observe(input, candidate, truth));
        const auto &native = observations.at(input.native);
        const auto &free = observations.at(historical.at("reference_free").sequence);
        std::array<std::size_t, 2> exposure{};
        for (std::size_t mask = 0; mask < 2; ++mask)
            for (const auto &span : truth.masks[mask]) {
                const auto begin = std::max(span.begin, input.core.begin),
                           end = std::min(span.end, input.core.end);
                if (begin < end)
                    exposure[mask] += end - begin;
            }
        for (std::size_t i = 0; i < truth.events.size(); ++i) {
            sites.insert(input.contig + "/" + truth.events[i].id);
            ++census[input.domain + (truth.events[i].resolved ? "/archive_resolved_events"
                                                              : "/archive_unresolved_events")];
        }
        for (const auto &[sequence, candidate] : input.candidates) {
            const auto &observation = observations.at(sequence);
            const auto id = sha256(sequence);
            ++candidate_count;
            if (!observation.boundary)
                ++unresolved_boundaries;
            for (std::size_t mask = 0; mask < 2; ++mask) {
                exposed_views += static_cast<std::size_t>(exposure[mask] > 0);
                candidates << input.id << '\t' << input.domain << '\t' << input.parent << '\t' << id
                           << '\t' << sequence << '\t' << candidate.origins << '\t'
                           << candidate.log_mass.has_value() << '\t' << (mask == 0 ? "100" : "500")
                           << '\t' << exposure[mask] << '\t' << observation.boundary;
                for (const auto &range : observation.counts[mask])
                    candidates << '\t' << range.minimum << '\t' << range.maximum;
                const auto *native_effect =
                    effect(observation.counts[mask][4], native.counts[mask][4],
                           observation.boundary && native.boundary, exposure[mask] > 0,
                           sequence == input.native);
                const auto *free_effect =
                    effect(observation.counts[mask][4], free.counts[mask][4],
                           observation.boundary && free.boundary, exposure[mask] > 0,
                           sequence == historical.at("reference_free").sequence);
                candidates << '\t' << native_effect << '\t' << free_effect << '\n';
                const auto prefix = input.domain + "/mask-" + (mask == 0 ? "100" : "500");
                ++census[prefix + "/candidate-vs-native/" + native_effect];
                ++census[prefix + "/candidate-vs-free/" + free_effect];
            }
            for (std::size_t i = 0; i < observation.events.size(); ++i) {
                const auto call = observation.events[i], baseline = native.events[i];
                ++event_count;
                events << input.id << '\t' << input.domain << '\t' << input.parent << '\t' << id
                       << '\t' << truth.events[i].id << '\t' << call_name(call) << '\t'
                       << call_name(baseline) << '\t' << call_name(free.events[i]) << '\t'
                       << (baseline == AlleleCall::alt && call == AlleleCall::ref) << '\t'
                       << (baseline == AlleleCall::alt &&
                           (call == AlleleCall::ref || call == AlleleCall::other))
                       << '\t' << (baseline == AlleleCall::alt && call == AlleleCall::unresolved)
                       << '\t' << private_effect(call, baseline) << '\t'
                       << private_effect(call, free.events[i]) << '\t'
                       << (call == AlleleCall::unresolved ? truth.events[i].resolved
                                                                ? "ambiguous_optimal_cuts"
                                                                : truth.events[i].reason
                                                          : ".")
                       << '\n';
                ++census[input.domain + "/candidate-private-vs-native/" +
                         private_effect(call, baseline)];
                ++census[input.domain + "/candidate-private-vs-free/" +
                         private_effect(call, free.events[i])];
            }
        }
        for (std::size_t stage = 0; stage < stages.size(); ++stage) {
            for (std::size_t mask = 0; mask < 2; ++mask) {
                std::size_t count{}, resolved{}, helpful_native{}, helpful_free{};
                for (const auto &[sequence, candidate] : input.candidates)
                    if ((candidate.origins & stages[stage]) != 0) {
                        ++count;
                        const auto &observation = observations.at(sequence);
                        resolved += static_cast<std::size_t>(observation.boundary);
                        helpful_native += static_cast<std::size_t>(
                            std::string(effect(observation.counts[mask][4], native.counts[mask][4],
                                               observation.boundary && native.boundary,
                                               exposure[mask] > 0, sequence == input.native)) ==
                            "helpful");
                        helpful_free += static_cast<std::size_t>(
                            std::string(
                                effect(observation.counts[mask][4], free.counts[mask][4],
                                       observation.boundary && free.boundary, exposure[mask] > 0,
                                       sequence == historical.at("reference_free").sequence)) ==
                            "helpful");
                    }
                support << input.id << '\t' << input.domain << '\t' << (mask == 0 ? "100" : "500")
                        << '\t' << stage_names[stage] << '\t' << count << '\t' << resolved << '\t'
                        << helpful_native << '\t' << helpful_free << "\t0\t0\t0\t0\n";
            }
            for (std::size_t i = 0; i < truth.events.size(); ++i) {
                std::array<std::size_t, 4> counts{};
                std::size_t count{};
                for (const auto &[sequence, candidate] : input.candidates)
                    if ((candidate.origins & stages[stage]) != 0) {
                        ++count;
                        ++counts[static_cast<std::size_t>(observations.at(sequence).events[i])];
                    }
                support << input.id << '\t' << input.domain << "\tevent/" << truth.events[i].id
                        << '\t' << stage_names[stage] << '\t' << count << '\t' << count - counts[3]
                        << "\t0\t0";
                for (const auto value : counts)
                    support << '\t' << value;
                support << '\n';
            }
        }
        for (const auto *arm : {"final_rerank", "selected"}) {
            const auto *winner_role =
                std::string(arm) == "final_rerank" ? "final_rerank_winner" : "context_winner";
            const auto &winner = historical.at(winner_role);
            const auto &selected = historical.at(arm);
            const auto &raw = observations.at(winner.sequence);
            const auto &actual = observations.at(selected.sequence);
            const bool proposed = winner.sequence != historical.at("reference_free").sequence;
            const bool accepted = selected.sequence != historical.at("reference_free").sequence;
            if (proposed)
                ++census[input.domain + "/" + arm + (accepted ? "/accepted" : "/blocked")];
            std::array<std::size_t, 3> consequences{};
            for (std::size_t i = 0; i < truth.events.size(); ++i)
                if (native.events[i] == AlleleCall::alt) {
                    consequences[0] += static_cast<std::size_t>(raw.events[i] == AlleleCall::ref);
                    consequences[1] += static_cast<std::size_t>(raw.events[i] == AlleleCall::ref ||
                                                                raw.events[i] == AlleleCall::other);
                    consequences[2] +=
                        static_cast<std::size_t>(raw.events[i] == AlleleCall::unresolved);
                }
            for (std::size_t mask = 0; mask < 2; ++mask) {
                decisions << input.id << '\t' << input.domain << '\t' << arm << '\t'
                          << (mask == 0 ? "100" : "500") << '\t' << selected.gate << '\t'
                          << proposed << '\t' << accepted;
                decisions << '\t'
                          << effect(raw.counts[mask][4], native.counts[mask][4],
                                    raw.boundary && native.boundary, exposure[mask] > 0,
                                    winner.sequence == input.native);
                decisions << '\t'
                          << effect(raw.counts[mask][4], free.counts[mask][4],
                                    raw.boundary && free.boundary, exposure[mask] > 0,
                                    winner.sequence == historical.at("reference_free").sequence);
                decisions << '\t'
                          << effect(actual.counts[mask][4], native.counts[mask][4],
                                    actual.boundary && native.boundary, exposure[mask] > 0,
                                    selected.sequence == input.native);
                decisions << '\t'
                          << effect(actual.counts[mask][4], free.counts[mask][4],
                                    actual.boundary && free.boundary, exposure[mask] > 0,
                                    selected.sequence == historical.at("reference_free").sequence);
                for (const auto value : consequences)
                    decisions << '\t' << value;
                decisions << '\n';
            }
        }
    }
    synced_write(output / "candidates.tsv", candidates.str());
    synced_write(output / "private.tsv", events.str());
    synced_write(output / "support.tsv", support.str());
    synced_write(output / "decisions.tsv", decisions.str());
    std::ostringstream result;
    result << "{\"schema\":\"context-study-evaluation/"
              "1\",\"synthetic_only\":false,\"biological_qualification\":false,\"historical_"
              "replay\":true,\"cases\":"
           << packet.cases.size() << ",\"unique_candidates\":" << candidate_count
           << ",\"parents\":" << parents.size() << ",\"event_sites\":" << sites.size()
           << ",\"candidate_event_observations\":" << event_count
           << ",\"exposed_candidate_mask_views\":" << exposed_views
           << ",\"unresolved_candidate_boundaries\":" << unresolved_boundaries << ",\"census\":{";
    for (const auto &[domain, values] : domain_parents)
        census[domain + "/parents"] = values.size();
    bool first = true;
    for (const auto &[key, value] : census) {
        if (!first)
            result << ',';
        first = false;
        result << json_string(key) << ':' << value;
    }
    result << "},\"score_comparison_absolute_tolerance\":1e-11,\"score_comparison_reason\":"
              "\"finite saved decimal double roundtrip; sequences, gates and abstentions require "
              "exact equality\"}";
    return result.str();
}
}
