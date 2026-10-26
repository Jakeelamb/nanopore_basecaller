#include "prefix_feedback/bridge.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <set>
#include <sstream>

namespace prefix_feedback {
namespace {
void keys(const Json& value, std::initializer_list<const char*> fields) {
    require(value.is_object() && value.size() == fields.size(), "bridge field census differs");
    for (const auto* field : fields) {
        require(value.contains(field), std::string("missing bridge field ") + field);
    }
}
std::size_t index(const Json& value) {
    require(value.is_number_unsigned() ||
                    (value.is_number_integer() && value.get<std::int64_t>() >= 0),
            "bridge nonnegative integer required");
    return value.get<std::size_t>();
}
Json consumed(const Json& value) {
    check_pin(value);
    const auto result = read_json(value.at("path").get<std::string>());
    check_pin(value);
    return result;
}
const Json& candidate(const Json& value, const Json& id) {
    const Json* result = nullptr;
    for (const auto& item : value.at("candidates")) {
        if (item.at("id") == id) {
            require(result == nullptr, "duplicate candidate role");
            result = &item;
        }
    }
    require(result != nullptr, "genuine reference-free candidate absent");
    return *result;
}
Json location_ids(const Session& session) {
    std::set<std::string> ids;
    for (const auto& location : session.locations) {
        require(ids.insert(location.id).second, "duplicate frozen panel ID");
    }
    return ids;
}
Json winner_id(const Json& candidates, const std::string& identity) {
    require(!candidates.empty(), "empty normalized candidate union");
    const Json* best = &candidates.front();
    for (const auto& item : candidates) {
        const auto score = item.at("neural_log_likelihood").get<double>();
        const auto current = best->at("neural_log_likelihood").get<double>();
        const auto sequence = item.at("sequence").get<std::string>();
        const auto previous = best->at("sequence").get<std::string>();
        if (score > current || (score == current &&
                ((sequence == identity && previous != identity) ||
                 ((sequence == identity) == (previous == identity) && sequence < previous)))) {
            best = &item;
        }
    }
    return best->at("id");
}
Json scored(const Session& session, const std::string& native, const std::string& sequence,
            Json& coverage, std::optional<double> known = std::nullopt) {
    require(!sequence.empty() && sequence.size() <= 4096, "normalized sequence bound");
    const auto neural = known.has_value() ? *known : likelihood(session, sequence);
    require(std::isfinite(neural), "candidate impossible on complete consumed prefix");
    const auto cost = panel_cost(session, sequence);
    coverage.push_back({{"id", digest(sequence)}, {"panels", cost.coverage}});
    return {{"id", digest(sequence)}, {"sequence", sequence},
            {"neural_log_likelihood", neural}, {"context_cost", cost.value},
            {"location_ids", location_ids(session)}, {"edits", wire_edits(native, sequence)},
            {"eligibility_reasons", Json::array()}};
}
Json availability(const Session& session) {
    return {{"kind", "released-score-block"}, {"row_begin", 0},
            {"row_end", session.consumed_rows}, {"available_row_end", session.consumed_rows},
            {"chunk_lookahead", "whole_chunk"}, {"signal_geometry", nullptr}};
}
Json stage_evidence(const Json& receipt_pin, const Json& expected_pin,
                    const Json& binary, const std::string& command, const Json& outputs) {
    require(receipt_pin == expected_pin, "independently expected producer receipt differs");
    const auto receipt = consumed(receipt_pin);
    keys(receipt, {"schema", "complete", "binary", "command", "terminal", "outputs",
                   "stdout", "stderr", "time"});
    require(receipt.at("schema") == "prefix-stage-receipt/1" && receipt.at("complete") == true &&
                    receipt.at("binary") == binary && receipt.at("outputs") == outputs,
            "actual producer binary/output census differs");
    check_pin(binary);
    const auto invocation = consumed(receipt.at("command"));
    keys(invocation, {"argv", "cwd", "env", "input_pins", "source_pins"});
    for (const auto& value : invocation.at("input_pins")) {
        check_pin(value);
    }
    for (const auto& value : invocation.at("source_pins")) {
        check_pin(value);
    }
    const auto& argv = invocation.at("argv");
    require(argv.size() >= 2 && argv.at(0) == binary.at("path") && argv.at(1) == command,
            "actual producer command differs");
    for (const auto& value : outputs) {
        check_pin(value);
    }
    for (const auto* field : {"stdout", "stderr", "time"}) {
        check_pin(receipt.at(field));
    }
    const auto terminal = consumed(receipt.at("terminal"));
    require(terminal.at("command") == receipt.at("command") && terminal.at("exit") == 0 &&
                    terminal.at("exit_known") == true && terminal.at("failure").is_null() &&
                    terminal.at("cleanup").at("terminal") == true &&
                    !terminal.at("start").get<std::string>().empty() &&
                    terminal.at("start").get<std::string>() <= terminal.at("end").get<std::string>(),
            "producer did not retain a successful terminal stage");
    return invocation;
}
Json own_binary() { return pin(fs::canonical("/proc/self/exe")); }
void check_complete(const Json& value) {
    const auto complete = consumed(value);
    require(complete.at("schema") == "prefix-complete/1" && complete.at("complete") == true &&
                    complete.at("source_sha256") == source_id() &&
                    complete.at("source") == source_witness(), "compiled producer source differs");
    check_pin(complete.at("request"));
}
Session advance_origin(const Json& state, const Json& snapshot, const Json& complete,
                       const Json& producer) {
    check_complete(complete);
    const auto invocation = stage_evidence(producer, producer, own_binary(), "advance",
                                           Json::array({state, snapshot, complete}));
    const auto closure = consumed(complete);
    const auto request = closure.at("request");
    const auto& argv = invocation.at("argv");
    require(argv.size() == 8 && argv.at(2) == "--request" && argv.at(3) == request.at("path") &&
                    argv.at(4) == "--request-sha256" && argv.at(5) == request.at("sha256") &&
                    argv.at(6) == "--output" &&
                    fs::path(argv.at(7).get<std::string>()) ==
                            fs::path(state.at("path").get<std::string>()).parent_path() &&
                    invocation.at("cwd") == source_witness().at("root"),
            "advance request/cwd/output provenance differs");
    const auto result = restore(consumed(state));
    const auto raw = consumed(snapshot);
    require(raw == batch(result, raw.at("previous_state_sha256")),
            "snapshot does not describe actual retained session");
    return result;
}
std::string frame_bytes(const Session& session) {
    require(!session.consumed.empty() && session.consumed_rows <= 2048,
            "normalization deferred: consumed-prefix rows exceed 2048");
    std::vector<std::string> header;
    std::string payload;
    const auto chunk = session.consumed.front().binding.at("chunk_index");
    for (const auto& block : session.consumed) {
        require(block.binding.at("chunk_index") == chunk, "multi-chunk normalization unsupported");
        const auto bytes = read_text(block.binding.at("tensor").at("path").get<std::string>());
        const auto newline = bytes.find('\n');
        require(newline != std::string::npos, "released tensor header absent");
        std::istringstream input(bytes.substr(0, newline));
        std::vector<std::string> fields;
        std::string field;
        while (std::getline(input, field, '\t')) {
            fields.push_back(field);
        }
        require(fields.size() == 15, "released tensor header census differs");
        fields[1] = std::to_string(session.consumed_rows);
        if (header.empty()) {
            header = fields;
        }
        require(fields == header, "released tensor codec/options differ across blocks");
        payload += bytes.substr(newline + 1);
    }
    std::string result;
    for (const auto& field : header) {
        result += (result.empty() ? "" : "\t") + field;
    }
    return result + '\n' + payload;
}
Json panels(const Session& session, const std::string& identity) {
    Json query = nullptr;
    if (!session.updates.empty()) {
        const auto& update = session.updates.back();
        const auto old = update.at("query_sequence").get<std::string>();
        require(old.size() <= identity.size() && identity.starts_with(old) &&
                        update.at("query_sha256") == digest(old) &&
                        index(update.at("query_length")) == old.size() &&
                        index(update.at("available_score_end")) <= session.consumed_rows &&
                        update.at("locations") == state_json(session).at("locations"),
                "older mapper query cannot project onto current free identity");
        check_pin(update.at("query"));
        check_pin(update.at("producer_receipt"));
        query = update;
    } else {
        require(session.locations.empty(), "locations have no prefix producer");
    }
    for (const auto& location : session.locations) {
        require(location.query_end <= identity.size(), "panel query exceeds current identity");
    }
    return {{"schema", "prefix-frozen-panels/1"}, {"source_sha256", source_id()},
            {"state_sha256", state_id(session)}, {"mapper_query", query},
            {"locations", state_json(session).at("locations")},
            {"cost_recipe", "uniform-unit-emitted-position-mismatch-neutral-exhaustion/1"},
            {"support_recipe", "retained-valid-panel-support-one-not-probability"}};
}
Json identity_fields(const Session& session, const Json& snapshot, const Json& tensor,
                     std::size_t parent, const std::string& sequence) {
    return {{"schema", "feedback-prefix-identity/1"}, {"kind", "pipeline-free-input"},
            {"quality_status", "uncalibrated"}, {"source_sha256", source_id()},
            {"plan_sha256", session.spec.plan_sha256}, {"input_tensor", tensor},
            {"read_id", session.spec.read_id}, {"parent_index", parent},
            {"chunk_index", session.last_binding.at("chunk_index")},
            {"block_index", session.last_binding.at("block_index")},
            {"availability", availability(session)},
            {"previous_state_sha256", snapshot.at("previous_state_sha256")},
            {"prefix_sha256", digest(sequence)}, {"prefix_length", sequence.size()},
            {"orientation", "forward"}, {"sequence", sequence},
            {"quality", std::string(sequence.size(), '!')}};
}
Json binding_from(const Json& identity, const Json& location, const Json& free,
                  const Json& identity_pin) {
    Json result = identity;
    for (const auto* field : {"schema", "kind", "quality_status", "sequence", "quality"}) {
        result.erase(field);
    }
    result["location_producer"] = location;
    result["reference_free_producer"] = free;
    result["identity_input"] = identity_pin;
    return result;
}
struct Emission {
    Session session;
    Json value;
    Json identity;
    Json snapshot;
};
Emission load_emission(const Json& request) {
    const auto value = consumed(request.at("emission"));
    require(value.at("schema") == "prefix-free-emission/1", "free emission schema differs");
    const auto root = fs::path(request.at("emission").at("path").get<std::string>()).parent_path();
    const auto complete = pin(root / "complete.json");
    check_complete(complete);
    const auto invocation = stage_evidence(request.at("producer"), request.at("expected_producer"),
            own_binary(), "emit-free-input", Json::array({value.at("binding").at("input_tensor"),
                    value.at("binding").at("location_producer"), value.at("identity"),
                    request.at("emission"), complete}));
    require(invocation.at("cwd") == source_witness().at("root"), "free emission cwd differs");
    const auto producer_request = consumed(consumed(complete).at("request"));
    require(producer_request.at("state") == value.at("state") &&
                    producer_request.at("snapshot") == value.at("snapshot") &&
                    producer_request.at("producer") == value.at("producer") &&
                    producer_request.at("advance_complete") == value.at("advance_complete"),
            "free input was not produced from declared independent branch");
    auto session = advance_origin(value.at("state"), value.at("snapshot"),
                                  value.at("advance_complete"), value.at("producer"));
    const auto snapshot = consumed(value.at("snapshot"));
    const auto sequence = candidate(snapshot, snapshot.at("reference_free_candidate_id"))
                                  .at("sequence").get<std::string>();
    const auto identity = consumed(value.at("identity"));
    const auto tensor = value.at("binding").at("input_tensor");
    check_pin(tensor);
    require(read_text(tensor.at("path").get<std::string>()) == frame_bytes(session),
            "consumed prefix tensor differs from actual released rows");
    require(identity == identity_fields(session, snapshot, tensor,
                            index(producer_request.at("parent_index")), sequence) &&
                    consumed(value.at("binding").at("location_producer")) == panels(session, sequence) &&
                    value.at("binding") == binding_from(identity,
                            value.at("binding").at("location_producer"), value.at("producer"),
                            value.at("identity")) &&
                    value.at("descriptor") == scoring_descriptor(session, value.at("binding")),
            "free identity/panel/prior descriptor differs from actual producer");
    return {std::move(session), value, identity, snapshot};
}
void validate_sidecar(const Json& original, const Json& proposals, const Json& descriptor) {
    keys(proposals, {"schema", "mode", "scoring_status", "status", "source_batch", "binding",
                     "scoring_descriptor", "reference_free_candidate", "tail", "limits", "counts",
                     "arm_exclusions", "exclusions", "proposals", "request_sha256", "source_files", "complete"});
    require(proposals.at("schema") == "indel-prefix-proposals/1" &&
                    proposals.at("mode") == "consumed-prefix-unscored-v1" &&
                    proposals.at("scoring_status") == "unscored" && proposals.at("complete") == true &&
                    proposals.at("binding") == original.at("binding") &&
                    proposals.at("scoring_descriptor") == descriptor,
            "foreign sidecar mode/binding/prior descriptor");
    const auto& free = candidate(original, original.at("reference_free_candidate_id"));
    require(proposals.at("reference_free_candidate") == Json{{"id", free.at("id")},
                    {"sequence", free.at("sequence")},
                    {"source_batch_sha256", proposals.at("source_batch").at("sha256")}},
            "sidecar changed genuine reference-free role");
    const auto length = original.at("native").at("sequence").get<std::string>().size();
    require(proposals.at("tail") == Json{{"query_begin", length > 32 ? length - 32 : 0},
                    {"query_end", length}, {"selection", "deterministic-last-32-available-bases"}} &&
                    proposals.at("limits") == Json{{"maximum_full_prefix_bases", 512},
                    {"maximum_consumed_rows", 2048}, {"maximum_tail_bases", 32},
                    {"maximum_new_unique_proposals", 512}, {"minimum_result_bases", 1},
                    {"maximum_result_bases", 514}}, "sidecar tail/limits differ");
    const auto& counts = proposals.at("counts");
    keys(counts, {"visited", "eligible", "unique", "duplicate", "excluded", "original_duplicates"});
    require(index(counts.at("visited")) == index(counts.at("eligible")) + index(counts.at("excluded")) &&
                    index(counts.at("eligible")) == index(counts.at("unique")) + index(counts.at("duplicate")) &&
                    index(counts.at("original_duplicates")) <= index(counts.at("duplicate")),
            "sidecar count conservation differs");
    require((proposals.at("status") == "ready" && proposals.at("arm_exclusions").empty() &&
                    proposals.at("proposals").size() == index(counts.at("unique"))) ||
                    (proposals.at("status") == "excluded" && !proposals.at("arm_exclusions").empty() &&
                     proposals.at("proposals").empty()), "sidecar exclusion census differs");
}
}

PanelCost panel_cost(const Session& session, const std::string& sequence) {
    PanelCost result;
    if (session.locations.empty()) {
        return result;
    }
    double marginal = -std::numeric_limits<double>::infinity();
    std::vector<const Location*> ordered;
    for (const auto& panel : session.locations) {
        ordered.push_back(&panel);
    }
    std::sort(ordered.begin(), ordered.end(), [](const Location* a, const Location* b) { return a->id < b->id; });
    for (const auto* pointer : ordered) {
        const auto& panel = *pointer;
        std::size_t covered{}, mismatches{};
        const auto suffix = sequence.size() > panel.query_length ? sequence.size() - panel.query_length : 0;
        if (panel.query_end == panel.query_length) {
            covered = std::min(suffix, panel.continuation.size());
            for (std::size_t offset = 0; offset < covered; ++offset) {
                mismatches += static_cast<std::size_t>(sequence[panel.query_length + offset] != panel.continuation[offset]);
            }
        }
        marginal = log_add(marginal, -static_cast<double>(mismatches));
        result.coverage.push_back({{"location_id", panel.id}, {"covered_emissions", covered},
                {"neutral_emissions", suffix - covered}, {"unit_mismatches", mismatches},
                {"query_anchor", panel.query_length}, {"continuation_length", panel.continuation.size()}});
    }
    result.value = std::max(0.0, std::log(static_cast<double>(session.locations.size())) - marginal);
    require(std::isfinite(result.value), "nonfinite complete-panel cost");
    return result;
}
Json wire_edits(const std::string& identity, const std::string& sequence) {
    Json result = Json::array();
    const auto changes = edits(identity, sequence);
    for (const auto& change : changes) {
        const auto ref = change.at("ref").get<std::string>();
        const auto alt = change.at("alt").get<std::string>();
        result.push_back({{"operation", ref.empty() ? "INS" : alt.empty() ? "DEL" : "SNV"},
                {"query_position", change.at("offset")}, {"reference", ref}, {"alternate", alt}});
    }
    return result;
}
Json scoring_descriptor(const Session& session, const Json& binding) {
    return {{"schema", "consumed-prefix-descriptor/1"}, {"prior", "uniform-all-states"},
            {"state_length", session.spec.state_length}, {"row_begin", 0},
            {"row_end", session.consumed_rows}, {"available_row_end", session.consumed_rows},
            {"source_sha256", binding.at("source_sha256")}, {"plan_sha256", binding.at("plan_sha256")},
            {"input_tensor", binding.at("input_tensor")}, {"producers", {
                    {"location_producer", binding.at("location_producer")},
                    {"reference_free_producer", binding.at("reference_free_producer")},
                    {"identity_input", binding.at("identity_input")}}}};
}
Json normalize_candidates(const Session& session, const Json& snapshot,
                          const Json& identity, const Json& binding, Json& coverage) {
    require(snapshot.at("schema") == "prefix-snapshot/1" && !snapshot.at("abstained").get<bool>(),
            "empty/absent free prefix is explicit normalization abstention");
    const auto& free = candidate(snapshot, snapshot.at("reference_free_candidate_id"));
    const auto native = identity.at("sequence").get<std::string>();
    require(!native.empty() && native == free.at("sequence") &&
                    identity.at("quality") == std::string(native.size(), '!') &&
                    binding.at("prefix_sha256") == digest(native) && index(binding.at("prefix_length")) == native.size(),
            "available free input identity differs");
    std::set<std::string> sequences;
    for (const auto& item : snapshot.at("candidates")) {
        require(sequences.insert(item.at("sequence").get<std::string>()).second,
                "duplicate snapshot sequence");
    }
    sequences.insert(native);
    require(sequences.size() <= 4096, "original union exceeds strict F2 bound; no truncation");
    Json candidates = Json::array();
    for (const auto& sequence : sequences) {
        candidates.push_back(scored(session, native, sequence, coverage));
    }
    Json locations = Json::array();
    for (const auto& panel : session.locations) {
        require(panel.query_end <= native.size(), "older panel exceeds available identity");
        locations.push_back({{"id", panel.id}, {"contig", panel.contig}, {"strand", panel.strand},
                {"query_begin", panel.query_begin}, {"query_end", panel.query_end},
                {"reference_begin", panel.reference_begin}, {"reference_end", panel.reference_end},
                {"confidence", {{"feature", "declared-location-support"}, {"value", 1.0},
                                {"meaning", "bounded_support_not_probability"}}}});
    }
    std::sort(locations.begin(), locations.end(), [](const Json& a, const Json& b) { return a.at("id").get<std::string>() < b.at("id").get<std::string>(); });
    require(free.at("id") == digest(native), "genuine H ID differs from sequence identity");
    return {{"schema", "feedback-next/1"}, {"kind", "candidate-batch"}, {"binding", binding},
            {"native", {{"sequence", native}, {"quality", identity.at("quality")}, {"scope", "available_input_segment"}}},
            {"reference_free_candidate_id", free.at("id")},
            {"union_nn_candidate_id", winner_id(candidates, native)}, {"locations", locations},
            {"candidates", candidates}};
}
Json merge_candidates(const Session& session, const Json& original, const Json& proposals,
                      const Json& descriptor, Json& report) {
    validate_sidecar(original, proposals, descriptor);
    const auto native = original.at("native").at("sequence").get<std::string>();
    Json result = original;
    Json additions = Json::array();
    Json coverage = Json::array();
    std::set<std::string> sequences;
    for (const auto& item : original.at("candidates")) {
        require(sequences.insert(item.at("sequence").get<std::string>()).second, "duplicate base sequence");
    }
    std::string previous;
    std::string reason;
    if (native.size() > 512 || session.consumed_rows > 2048) {
        reason = "prefix-or-consumed-row-bound-excludes-new-arm";
    }
    for (const auto& proposal : proposals.at("proposals")) {
        keys(proposal, {"id", "sequence", "edit", "mechanism"});
        const auto sequence = proposal.at("sequence").get<std::string>();
        dna(sequence);
        const auto& edit = proposal.at("edit");
        keys(edit, {"query_begin", "query_end", "reference", "alternate"});
        const auto begin = index(edit.at("query_begin")), end = index(edit.at("query_end"));
        const auto alternate = edit.at("alternate").get<std::string>();
        dna(alternate);
        require(begin <= end && end <= native.size() && begin >= (native.size() > 32 ? native.size() - 32 : 0) &&
                        edit.at("reference") == native.substr(begin, end - begin) &&
                        native.substr(0, begin) + alternate + native.substr(end) == sequence &&
                        proposal.at("id") == "prefix-indel-" + digest(sequence) &&
                        (previous.empty() || previous < sequence) && sequences.insert(sequence).second,
                "sidecar replacement/order/dedup/tail differs");
        const auto mechanism = proposal.at("mechanism").get<std::string>();
        const auto reference = edit.at("reference").get<std::string>();
        if (mechanism == "single-deletion") {
            require(end == begin + 1 && alternate.empty(), "single-deletion shape differs");
        } else if (mechanism == "single-insertion") {
            require(begin == end && alternate.size() == 1, "single-insertion shape differs");
        } else {
            const auto difference = reference.size() > alternate.size() ? reference.size() - alternate.size() : alternate.size() - reference.size();
            require(mechanism == "run-length-plus-minus-two" && reference.size() >= 2 &&
                    !alternate.empty() && alternate.size() <= 6 && difference >= 1 && difference <= 2 &&
                    reference.find_first_not_of(reference.front()) == std::string::npos &&
                    alternate.find_first_not_of(reference.front()) == std::string::npos &&
                    (begin == 0 || native[begin - 1] != reference.front()) &&
                    (end == native.size() || native[end] != reference.front()), "visible maximal run proposal shape differs");
        }
        if (sequence.empty() || sequence.size() > 514) {
            reason = "empty-or-overlong-result-excludes-new-arm";
        }
        previous = sequence;
        additions.push_back(sequence);
    }
    if (proposals.at("status") == "excluded") {
        reason = "F3-whole-new-arm-excluded";
    } else if (additions.size() > 512) {
        reason = "new-unique-proposals-exceed-512";
    } else if (original.at("candidates").size() + additions.size() > 4096) {
        reason = "full-union-exceeds-4096-preserve-original-arm";
    }
    std::size_t calls{};
    Json scoring_exclusions = Json::array();
    if (reason.empty()) {
        Json scored_additions = Json::array();
        for (const auto& value : additions) {
            const auto sequence = value.get<std::string>();
            ++calls;
            const auto neural = likelihood(session, sequence);
            if (!std::isfinite(neural)) {
                scoring_exclusions.push_back({{"sequence_sha256", digest(sequence)},
                        {"reason", "impossible-consumed-prefix-neural-mass"}});
                continue;
            }
            scored_additions.push_back(scored(session, native, sequence, coverage, neural));
        }
        if (reason.empty()) {
            for (const auto& value : scored_additions) {
                result["candidates"].push_back(value);
            }
            std::sort(result["candidates"].begin(), result["candidates"].end(),
                    [](const Json& a, const Json& b) { return a.at("sequence").get<std::string>() < b.at("sequence").get<std::string>(); });
            result["union_nn_candidate_id"] = winner_id(result.at("candidates"), native);
        }
    }
    require(result.at("reference_free_candidate_id") == original.at("reference_free_candidate_id"), "merge replaced genuine H");
    for (const auto& item : original.at("candidates")) {
        require(candidate(result, item.at("id")) == item, "merge changed original candidate record");
    }
    report = {{"schema", "prefix-union-merge/1"}, {"new_arm_status", reason.empty() ? "included" : "excluded"},
            {"reason", reason}, {"scalar_calls", calls}, {"proposal_count", additions.size()},
            {"original_count", original.at("candidates").size()}, {"final_count", result.at("candidates").size()},
            {"coverage", coverage}, {"scoring_exclusions", scoring_exclusions},
            {"nomination_counts", proposals.at("counts")}};
    return result;
}
void bridge_command(const std::string& command, const Json& request, const fs::path& output) {
    require(request.at("source_sha256") == source_id(), "bridge source differs");
    if (command == "emit-free-input") {
        keys(request, {"schema", "source_sha256", "state", "snapshot", "advance_complete", "producer", "expected_producer", "parent_index"});
        require(request.at("schema") == "prefix-emit-free-input/1" && request.at("producer") == request.at("expected_producer"), "free input request differs");
        const auto session = advance_origin(request.at("state"), request.at("snapshot"), request.at("advance_complete"), request.at("producer"));
        const auto snapshot = consumed(request.at("snapshot"));
        require(!snapshot.at("abstained").get<bool>(), "no available free prefix: explicit abstention");
        const auto sequence = candidate(snapshot, snapshot.at("reference_free_candidate_id")).at("sequence").get<std::string>();
        require(!sequence.empty(), "available free identity absent");
        if (sequence.size() > 512 || session.consumed_rows > 2048) {
            Json reasons = Json::array();
            if (sequence.size() > 512) {
                reasons.push_back("full-prefix-exceeds-512");
            }
            if (session.consumed_rows > 2048) {
                reasons.push_back("consumed-rows-exceed-2048");
            }
            fresh(output / "arm-excluded.json", {{"schema", "prefix-new-arm-excluded/1"},
                    {"status", "excluded"}, {"reasons", reasons}, {"state", request.at("state")},
                    {"snapshot", request.at("snapshot")},
                    {"reference_free_candidate_id", snapshot.at("reference_free_candidate_id")},
                    {"original_arm_preserved", true}, {"identity_invented", false}});
            return;
        }
        const auto frozen = panels(session, sequence);
        fresh_bytes(output / "tensor.dgs", frame_bytes(session));
        fresh(output / "panels.json", frozen);
        const auto identity = identity_fields(session, snapshot, pin(output / "tensor.dgs"), index(request.at("parent_index")), sequence);
        fresh(output / "identity.json", identity);
        const auto binding = binding_from(identity, pin(output / "panels.json"), request.at("producer"), pin(output / "identity.json"));
        fresh(output / "emission.json", {{"schema", "prefix-free-emission/1"}, {"state", request.at("state")},
                {"snapshot", request.at("snapshot")}, {"advance_complete", request.at("advance_complete")},
                {"producer", request.at("producer")}, {"identity", pin(output / "identity.json")},
                {"binding", binding}, {"descriptor", scoring_descriptor(session, binding)}});
    } else if (command == "normalize" || command == "merge-indels") {
        if (command == "normalize") {
            keys(request, {"schema", "source_sha256", "emission", "producer", "expected_producer", "expected_binding"});
            require(request.at("schema") == "prefix-normalize/1", "normalize schema differs");
        } else {
            keys(request, {"schema", "source_sha256", "emission", "producer", "expected_producer", "expected_binding", "batch", "sidecar", "sidecar_producer", "expected_sidecar_producer", "sidecar_binary", "sidecar_source_files"});
            require(request.at("schema") == "prefix-merge-indels/1", "merge schema differs");
        }
        auto emission = load_emission(request);
        require(request.at("expected_binding") == emission.value.at("binding"), "independently expected binding differs");
        Json coverage = Json::array();
        auto normalized = normalize_candidates(emission.session, emission.snapshot, emission.identity, emission.value.at("binding"), coverage);
        Json report = {{"schema", "prefix-normalization/1"}, {"coverage", coverage},
                {"context_cost", "complete-frozen-panel-unit-emission-mixture-not-pruned-rank"}};
        if (command == "merge-indels") {
            const auto original = consumed(request.at("batch"));
            require(original == normalized, "merge base is not the complete normalized original arm");
            const auto sidecar = consumed(request.at("sidecar"));
            require(sidecar.at("source_batch") == request.at("batch") &&
                            sidecar.at("source_files") == request.at("sidecar_source_files"), "sidecar source/batch differs");
            const auto invocation = stage_evidence(request.at("sidecar_producer"), request.at("expected_sidecar_producer"),
                    request.at("sidecar_binary"), "nominate-prefix", Json::array({request.at("sidecar")}));
            for (const auto& source : request.at("sidecar_source_files")) {
                check_pin(source);
                require(std::find(invocation.at("source_pins").begin(), invocation.at("source_pins").end(), source) != invocation.at("source_pins").end(),
                        "actual sidecar source closure absent from producer command");
            }
            const auto& argv = invocation.at("argv");
            require(argv.size() == 5 && argv.at(3) == sidecar.at("request_sha256") &&
                            argv.at(4) == request.at("sidecar").at("path"), "sidecar actual request/output differs");
            const auto sidecar_request = consumed(pin(argv.at(2).get<std::string>()));
            require(file_digest(argv.at(2).get<std::string>()) == sidecar.at("request_sha256") &&
                            sidecar_request.at("batch_pin") == request.at("batch") &&
                            sidecar_request.at("expected_binding") == request.at("expected_binding") &&
                            sidecar_request.at("scoring_descriptor") == emission.value.at("descriptor") &&
                            sidecar_request.at("expected_scoring_descriptor") == emission.value.at("descriptor"),
                    "sidecar consumed request/prior differs");
            normalized = merge_candidates(emission.session, original, sidecar, emission.value.at("descriptor"), report);
        }
        fresh(output / "batch.json", normalized);
        fresh(output / "descriptor.json", emission.value.at("descriptor"));
        fresh(output / "report.json", report);
    } else {
        require(command == "bridge-fixture", "unknown bridge command");
        keys(request, {"schema", "source_sha256"});
        require(request.at("schema") == "prefix-bridge-fixture/1", "fixture schema differs");
        const std::string header = "DGS1\t4\t16\t1\t6\t0\t32\t100\t1\t0\t0\t0\t0\ttoy\t0\n";
        std::string bytes = header;
        for (std::size_t i = 0; i < 64; ++i) {
            bytes.push_back('\0');
            bytes.push_back('\x30');
        }
        fresh_bytes(output / "released.dgs", bytes);
        Json block{{"tensor", pin(output / "released.dgs")}, {"read_id", "bridge-toy"}, {"parent_id", "bridge-toy"},
                {"chunk_index", 0}, {"block_index", 0}, {"row_begin", 0}, {"row_end", 4},
                {"chunk_row_begin", 0}, {"chunk_row_end", 4}, {"available_score_end", 4},
                {"available_signal_end", 100}, {"chunk_signal_begin", 0}, {"chunk_signal_end", 100},
                {"declared_chunk_lookahead", 100}, {"orientation", "signal-forward"}};
        fresh(output / "release.json", {{"schema", "prefix-release/1"}, {"read_id", "bridge-toy"},
                {"tensor", block.at("tensor")}, {"binding", block}});
        block["release_receipt"] = pin(output / "release.json");
        fresh(output / "advance.json", {{"schema", "prefix-advance/1"}, {"source_sha256", source_id()},
                {"spec", {{"read_id", "bridge-toy"}, {"plan_sha256", std::string(64, 'a')}, {"state_length", 1},
                        {"stay_score", 0.0}, {"resource_manifest", nullptr},
                        {"policy", {{"beam_width", 1}, {"maximum_symbols", 16}, {"minimum_symbols", 1},
                                {"maximum_locations", 8}, {"context_weight", 0.5}}}}},
                {"state", nullptr}, {"update", nullptr}, {"block", block}, {"expected_previous_state_sha256", nullptr}});
    }
}
}
