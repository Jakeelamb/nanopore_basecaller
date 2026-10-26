#include "prefix_feedback/session.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <set>
#include <tuple>

namespace prefix_feedback {
namespace {
constexpr double impossible = -std::numeric_limits<double>::infinity();
constexpr char bases[] = "ACGT";
using Key = std::tuple<std::string, std::size_t, std::size_t>;
Json policy_json(const Policy& value) {
    return {{"beam_width", value.beam_width},
            {"maximum_symbols", value.maximum_symbols},
            {"minimum_symbols", value.minimum_symbols},
            {"maximum_locations", value.maximum_locations},
            {"context_weight", value.context_weight}};
}
Policy parse_policy(const Json& value) {
    require(value.size() == 5, "unknown policy field");
    return {value.at("beam_width"), value.at("maximum_symbols"), value.at("minimum_symbols"),
            value.at("maximum_locations"), value.at("context_weight")};
}
Json location_json(const Location& value) {
    return {{"id", value.id},
            {"contig", value.contig},
            {"strand", value.strand},
            {"query_begin", value.query_begin},
            {"query_end", value.query_end},
            {"query_length", value.query_length},
            {"reference_begin", value.reference_begin},
            {"reference_end", value.reference_end},
            {"reference_length", value.reference_length},
            {"mapq", value.mapq},
            {"cigar", value.cigar},
            {"continuation", value.continuation},
            {"evidence", value.evidence}};
}
Json locations_json(const std::vector<Location>& values) {
    Json result = Json::array();
    for (const auto& value : values) {
        result.push_back(location_json(value));
    }
    return result;
}
Json nodes_json(const std::vector<Node>& values) {
    Json result = Json::array();
    for (const auto& value : values) {
        result.push_back({value.sequence, value.state, value.location, value.mass});
    }
    return result;
}
std::vector<Node> nodes(const Json& values, std::size_t state_count, std::size_t location_count) {
    std::vector<Node> result;
    std::set<Key> keys;
    for (const auto& value : values) {
        require(value.size() == 4, "node fields differ");
        Node item{value.at(0), value.at(1), value.at(2), value.at(3)};
        dna(item.sequence);
        require(item.state < state_count &&
                        item.location < std::max(std::size_t{1}, location_count) &&
                        std::isfinite(item.mass),
                "node state/location/mass differs");
        require(keys.emplace(item.sequence, item.state, item.location).second, "duplicate node");
        result.push_back(std::move(item));
    }
    return result;
}
std::map<std::string, double> masses(const std::vector<Node>& beam) {
    std::map<std::string, double> result;
    for (const auto& node : beam) {
        auto [position, inserted] = result.emplace(node.sequence, node.mass);
        if (!inserted) {
            position->second = log_add(position->second, node.mass);
        }
    }
    return result;
}
std::optional<std::string> winner(const std::vector<Node>& beam, std::size_t minimum) {
    std::optional<std::string> sequence;
    double best = impossible;
    for (const auto& [candidate, mass] : masses(beam)) {
        if (!candidate.empty() && candidate.size() >= minimum && mass > best) {
            sequence = candidate;
            best = mass;
        }
    }
    return sequence;
}
void relocate(Session& session, const Json& update) {
    require(update.at("schema") == "prefix-location/1" &&
                    update.at("source_sha256") == source_id() &&
                    update.at("plan_sha256") == session.spec.plan_sha256 &&
                    update.at("read_id") == session.spec.read_id,
            "location source/plan/read differs");
    const auto chosen = winner(session.conditioned, session.spec.policy.minimum_symbols);
    require(chosen.has_value(), "empty/absent prefix is mapper abstention");
    const auto& expected = *chosen;
    require(update.at("state_sha256") == state_id(session) &&
                    update.at("query_sequence") == expected &&
                    update.at("query_sha256") == digest(expected) &&
                    update.at("query_length") == expected.size(),
            "missing/foreign provisional prefix/state");
    require(update.at("available_score_end") == session.consumed_rows &&
                    update.at("available_signal_end") ==
                            session.last_binding.at("available_signal_end") &&
                    update.at("orientation") == "signal-forward",
            "location endpoint/orientation differs");
    check_pin(update.at("query"));
    require(read_text(update.at("query").at("path").get<std::string>()) ==
                    ">prefix\n" + expected + "\n",
            "mapper query file differs");
    check_pin(update.at("producer_receipt"));
    check_pin(update.at("paf"));
    check_pin(update.at("mapper"));
    check_pin(update.at("reference_index"));
    const auto resources =
            validate_resources(session.spec.resource_manifest, session.spec.plan_sha256);
    require(update.at("resource_manifest") == session.spec.resource_manifest &&
                    update.at("mapper") == resources.at("mapper") &&
                    update.at("reference_index") == resources.at("reference_index"),
            "mapper/index frozen resource identity differs");
    const auto receipt = read_json(update.at("producer_receipt").at("path").get<std::string>());
    require(receipt.at("complete") == true && receipt.at("exit_status") == 0 &&
                    receipt.at("role") == "prefix-location" &&
                    receipt.at("inputs").at(0) == update.at("query") &&
                    receipt.at("stdout") == update.at("paf") && receipt.at("terminal") == true,
            "mapper receipt linkage differs");
    require(receipt.at("binding") ==
                    Json{{"state_sha256", update.at("state_sha256")},
                         {"query_sha256", update.at("query_sha256")},
                         {"available_score_end", update.at("available_score_end")},
                         {"available_signal_end", update.at("available_signal_end")}},
            "mapper receipt endpoint/state differs");
    require(receipt.at("argv") == Json::array({update.at("mapper").at("path"), "-x", "map-ont",
                                               "-c", "--secondary=yes", "-N", "7", "-t", "2",
                                               update.at("reference_index").at("path"),
                                               update.at("query").at("path")}),
            "mapper exact argv differs");
    require(receipt.at("inputs") == Json::array({update.at("query"), update.at("mapper"),
                                                 update.at("reference_index")}),
            "mapper exact input census differs");
    require(receipt.at("cwd") == source_witness().at("root") &&
                    receipt.at("environment").at("LC_ALL") == "C",
            "mapper cwd/environment differs");
    validate_command_evidence(receipt, resources.at("producer_sources"));
    auto parsed = parse_paf(read_text(update.at("paf").at("path").get<std::string>()),
                            {{"length", expected.size()}});
    auto locations = parse_locations(update, resources);
    require(locations.size() <= session.spec.policy.maximum_locations &&
                    parsed.size() == locations.size(),
            "location cap/census differs");
    for (std::size_t index = 0; index < locations.size(); ++index) {
        auto actual = location_json(locations[index]);
        actual.erase("continuation");
        actual.erase("evidence");
        require(actual == parsed.at(index), "retained mapper location/CIGAR differs");
    }
    std::map<std::pair<std::string, std::size_t>, double> merged;
    for (const auto& node : session.conditioned) {
        auto [position, inserted] =
                merged.emplace(std::make_pair(node.sequence, node.state), node.mass);
        if (!inserted) {
            position->second = log_add(position->second, node.mass);
        }
    }
    session.conditioned.clear();
    const auto count = std::max(std::size_t{1}, locations.size());
    const auto prior = -std::log(static_cast<double>(count));
    for (const auto& [key, mass] : merged) {
        for (std::size_t index = 0; index < count; ++index) {
            session.conditioned.push_back({key.first, key.second, index, mass + prior});
        }
    }
    if (session.updates.empty()) {
        session.first_locations = locations;
    }
    session.locations = std::move(locations);
    session.updates.push_back(update);
}
double penalty(const Session& session, const Node& node, char base) {
    if (session.locations.empty() || session.spec.policy.context_weight == 0.0) {
        return 0.0;
    }
    const auto& location = session.locations.at(node.location);
    if (node.sequence.size() < location.query_length ||
        location.query_end != location.query_length) {
        return 0.0;
    }
    const auto offset = node.sequence.size() - location.query_length;
    if (offset >= location.continuation.size()) {
        return 0.0;
    }
    return base == location.continuation[offset] ? 0.0 : session.spec.policy.context_weight;
}
void step(Session& session, std::vector<Node>& beam, std::span<const double> row, bool contextual) {
    std::map<Key, double> expanded;
    auto add = [&](const Node& node, const std::string& sequence, std::size_t state, double mass) {
        if (!std::isfinite(mass)) {
            return;
        }
        auto [position, inserted] = expanded.emplace(Key{sequence, state, node.location}, mass);
        if (!inserted) {
            position->second = log_add(position->second, mass);
        }
    };
    for (const auto& node : beam) {
        add(node, node.sequence, node.state, node.mass + session.spec.stay_score);
        if (node.sequence.size() == session.spec.policy.maximum_symbols) {
            session.symbol_bound = true;
            continue;
        }
        for (std::size_t base = 0; base < 4; ++base) {
            std::size_t next{};
            const auto channel = transition(node.state, base, session.spec.state_length, next);
            const auto cost = contextual ? penalty(session, node, bases[base]) : 0.0;
            if (contextual && !session.locations.empty()) {
                const auto& location = session.locations.at(node.location);
                if (node.sequence.size() >= location.query_length &&
                    node.sequence.size() - location.query_length >= location.continuation.size()) {
                    session.context_bound = true;
                }
            }
            add(node, node.sequence + bases[base], next, node.mass + row[channel] - cost);
        }
    }
    std::map<std::string, double> ranks;
    for (const auto& [key, mass] : expanded) {
        auto [position, inserted] = ranks.emplace(std::get<0>(key), mass);
        if (!inserted) {
            position->second = log_add(position->second, mass);
        }
    }
    std::vector<std::pair<std::string, double>> ordered(ranks.begin(), ranks.end());
    std::sort(ordered.begin(), ordered.end(), [](const auto& a, const auto& b) {
        return a.second != b.second ? a.second > b.second : a.first < b.first;
    });
    const bool pruned = ordered.size() > session.spec.policy.beam_width;
    if (pruned) {
        ordered.resize(session.spec.policy.beam_width);
    }
    std::set<std::string> retained;
    for (const auto& item : ordered) {
        retained.insert(item.first);
    }
    beam.clear();
    for (const auto& [key, mass] : expanded) {
        if (retained.contains(std::get<0>(key))) {
            beam.push_back({std::get<0>(key), std::get<1>(key), std::get<2>(key), mass});
        }
    }
    if (contextual) {
        session.conditioned_pruned = session.conditioned_pruned || pruned;
    } else {
        session.signal_pruned = session.signal_pruned || pruned;
    }
}
double fixed_cost(const Session& session, const std::string& sequence) {
    double best = std::numeric_limits<double>::infinity();
    for (const auto& location : session.first_locations) {
        double cost{};
        if (location.query_end != location.query_length) {
            return 0.0;
        }
        for (std::size_t index = location.query_length;
             index < sequence.size() &&
             index - location.query_length < location.continuation.size();
             ++index) {
            if (sequence[index] != location.continuation[index - location.query_length]) {
                cost += session.spec.policy.context_weight;
            }
        }
        best = std::min(best, cost);
    }
    return std::isfinite(best) ? best : 0.0;
}
}
double log_add(double a, double b) {
    if (a == impossible) {
        return b;
    }
    if (b == impossible) {
        return a;
    }
    const auto maximum = std::max(a, b);
    return maximum + std::log1p(std::exp(std::min(a, b) - maximum));
}
std::size_t transition(std::size_t previous, std::size_t base, std::size_t k, std::size_t& next) {
    require(k >= 1 && k <= 4 && previous < (std::size_t{1} << (2 * k)) && base < 4,
            "CRF transition bounds");
    next = ((previous << 2) & ((std::size_t{1} << (2 * k)) - 1)) | base;
    return 4 * next + (previous >> (2 * (k - 1)));
}
Session start(const Spec& spec) {
    require(!spec.read_id.empty() && spec.plan_sha256.size() == 64 && spec.state_length >= 1 &&
                    spec.state_length <= 4 && std::isfinite(spec.stay_score),
            "session identity/prior bounds");
    const auto& policy = spec.policy;
    require(policy.beam_width >= 1 && policy.beam_width <= 4096 && policy.maximum_symbols <= 8192 &&
                    policy.minimum_symbols <= policy.maximum_symbols &&
                    policy.maximum_locations >= 1 && policy.maximum_locations <= 32 &&
                    std::isfinite(policy.context_weight) && policy.context_weight >= 0.0,
            "policy bounds");
    Session session;
    session.spec = spec;
    const auto states = std::size_t{1} << (2 * spec.state_length);
    for (std::size_t state = 0; state < states; ++state) {
        session.signal.push_back({"", state, 0, -std::log(static_cast<double>(states))});
    }
    session.conditioned = session.signal;
    return session;
}
Json state_json(const Session& session) {
    Json blocks = Json::array();
    for (const auto& block : session.consumed) {
        blocks.push_back(block.binding);
    }
    return {{"schema", "prefix-session/1"},
            {"source_sha256", source_id()},
            {"spec",
             {{"read_id", session.spec.read_id},
              {"plan_sha256", session.spec.plan_sha256},
              {"state_length", session.spec.state_length},
              {"stay_score", session.spec.stay_score},
              {"policy", policy_json(session.spec.policy)},
              {"resource_manifest", session.spec.resource_manifest}}},
            {"consumed_rows", session.consumed_rows},
            {"next_block", session.next_block},
            {"signal", nodes_json(session.signal)},
            {"conditioned", nodes_json(session.conditioned)},
            {"locations", locations_json(session.locations)},
            {"first_locations", locations_json(session.first_locations)},
            {"consumed", blocks},
            {"updates", session.updates},
            {"last_binding", session.last_binding},
            {"signal_pruned", session.signal_pruned},
            {"conditioned_pruned", session.conditioned_pruned},
            {"symbol_bound", session.symbol_bound},
            {"context_bound", session.context_bound}};
}
Session restore(const Json& state) {
    require(state.at("schema") == "prefix-session/1" && state.at("source_sha256") == source_id() &&
                    state.size() == 16,
            "session source/schema/fields differ");
    const auto& value = state.at("spec");
    auto result = start({value.at("read_id"), value.at("plan_sha256"), value.at("state_length"),
                         value.at("stay_score"), parse_policy(value.at("policy")),
                         value.at("resource_manifest")});
    result.consumed_rows = state.at("consumed_rows");
    result.next_block = state.at("next_block");
    const auto resources =
            result.spec.resource_manifest.is_null()
                    ? Json::object()
                    : validate_resources(result.spec.resource_manifest, result.spec.plan_sha256);
    result.locations = parse_locations({{"locations", state.at("locations")}}, resources);
    result.first_locations =
            parse_locations({{"locations", state.at("first_locations")}}, resources);
    const auto states = std::size_t{1} << (2 * result.spec.state_length);
    result.signal = nodes(state.at("signal"), states, 0);
    result.conditioned = nodes(state.at("conditioned"), states, result.locations.size());
    result.updates = state.at("updates");
    result.last_binding = state.at("last_binding");
    result.signal_pruned = state.at("signal_pruned");
    result.conditioned_pruned = state.at("conditioned_pruned");
    result.symbol_bound = state.at("symbol_bound");
    result.context_bound = state.at("context_bound");
    std::size_t cursor{};
    for (const auto& binding : state.at("consumed")) {
        auto block = load_block(binding, result.spec);
        require(block.row_begin == cursor, "restored score ownership gap/duplicate");
        cursor = block.row_end;
        result.consumed.push_back(std::move(block));
    }
    require(cursor == result.consumed_rows && result.next_block == result.consumed.size(),
            "restored cursor differs");
    return result;
}
std::string state_id(const Session& session) { return digest(state_json(session).dump()); }
void advance(Session& session, const Block& block, const std::optional<Json>& update) {
    const auto channels = std::size_t{1} << (2 * (session.spec.state_length + 1));
    require(block.row_begin == session.consumed_rows && block.row_end > block.row_begin &&
                    block.row_end - block.row_begin <= 512 &&
                    block.scores.size() == (block.row_end - block.row_begin) * channels,
            "score rows repeated/gap/shape");
    require(std::all_of(block.scores.begin(), block.scores.end(),
                        [](double value) { return std::isfinite(value); }),
            "nonfinite scores");
    require(block.binding.at("block_index") == session.next_block &&
                    block.binding.at("read_id") == session.spec.read_id &&
                    block.binding.at("orientation") == "signal-forward",
            "block sequence/parent/orientation differs");
    if (!session.last_binding.is_null()) {
        require(block.binding.at("available_signal_end").get<std::size_t>() >=
                        session.last_binding.at("available_signal_end").get<std::size_t>(),
                "signal endpoint regressed");
        const auto previous_chunk = session.last_binding.at("chunk_index").get<std::size_t>();
        const auto chunk = block.binding.at("chunk_index").get<std::size_t>();
        require(chunk == previous_chunk || chunk == previous_chunk + 1, "chunk index gap");
        if (chunk == previous_chunk) {
            require(block.binding.at("chunk_row_begin") == session.last_binding.at("chunk_row_end"),
                    "chunk rows repeated/gap");
        }
    }
    if (update.has_value()) {
        require(session.consumed_rows > 0,
                "initial location must be a declared prior, not mapped native");
        relocate(session, *update);
    }
    for (std::size_t row = 0; row < block.row_end - block.row_begin; ++row) {
        const auto scores = std::span<const double>(block.scores).subspan(row * channels, channels);
        step(session, session.signal, scores, false);
        step(session, session.conditioned, scores, true);
    }
    session.consumed.push_back(block);
    session.consumed_rows = block.row_end;
    ++session.next_block;
    session.last_binding = block.binding;
}
double likelihood(const Session& session, const std::string& sequence) {
    dna(sequence);
    if (sequence.size() > session.consumed_rows) {
        return impossible;
    }
    const auto states = std::size_t{1} << (2 * session.spec.state_length);
    std::vector<std::map<std::size_t, double>> dp(sequence.size() + 1);
    for (std::size_t state = 0; state < states; ++state) {
        dp[0][state] = -std::log(static_cast<double>(states));
    }
    const auto channels = states * 4;
    for (const auto& block : session.consumed) {
        for (std::size_t row = 0; row < block.row_end - block.row_begin; ++row) {
            auto next = std::vector<std::map<std::size_t, double>>(sequence.size() + 1);
            auto add = [&](std::size_t length, std::size_t state, double mass) {
                auto [position, inserted] = next[length].emplace(state, mass);
                if (!inserted) {
                    position->second = log_add(position->second, mass);
                }
            };
            for (std::size_t length = 0; length <= sequence.size(); ++length) {
                for (const auto& [state, mass] : dp[length]) {
                    add(length, state, mass + session.spec.stay_score);
                    if (length < sequence.size()) {
                        std::size_t target{};
                        const auto channel =
                                transition(state, std::string("ACGT").find(sequence[length]),
                                           session.spec.state_length, target);
                        add(length + 1, target, mass + block.scores[row * channels + channel]);
                    }
                }
            }
            dp = std::move(next);
        }
    }
    double result = impossible;
    for (const auto& [state, mass] : dp.back()) {
        static_cast<void>(state);
        result = log_add(result, mass);
    }
    return result;
}
Json batch(const Session& session, const std::string& previous_state) {
    const auto free = masses(session.signal);
    const auto guided = masses(session.conditioned);
    const auto free_winner = winner(session.signal, session.spec.policy.minimum_symbols);
    const auto conditioned_winner =
            winner(session.conditioned, session.spec.policy.minimum_symbols);
    const auto free_sequence = free_winner.value_or("");
    const auto provisional = conditioned_winner.value_or("");
    std::set<std::string> sequences;
    for (const auto& [sequence, mass] : free) {
        static_cast<void>(mass);
        if (!sequence.empty() && sequence.size() >= session.spec.policy.minimum_symbols) {
            sequences.insert(sequence);
        }
    }
    for (const auto& [sequence, mass] : guided) {
        static_cast<void>(mass);
        if (!sequence.empty() && sequence.size() >= session.spec.policy.minimum_symbols) {
            sequences.insert(sequence);
        }
    }
    Json candidates = Json::array();
    std::string union_id;
    double union_mass = impossible;
    std::string rerank_id;
    double best_rerank = impossible;
    for (const auto& sequence : sequences) {
        const auto neural = likelihood(session, sequence);
        require(std::isfinite(neural), "eligible candidate has impossible neural mass");
        const auto id = digest(sequence);
        if (neural > union_mass) {
            union_mass = neural;
            union_id = id;
        }
        const auto cost = guided.contains(sequence)
                                  ? Json(std::max(0.0, neural - guided.at(sequence)))
                                  : Json(nullptr);
        const auto rerank = neural - fixed_cost(session, sequence);
        if (free.contains(sequence) && rerank > best_rerank) {
            best_rerank = rerank;
            rerank_id = id;
        }
        candidates.push_back(
                {{"id", id},
                 {"sequence", sequence},
                 {"neural_log_likelihood", neural},
                 {"context_cost", cost},
                 {"partial_rank",
                  guided.contains(sequence) ? Json(guided.at(sequence)) : Json(nullptr)},
                 {"fixed_policy_rerank", rerank},
                 {"signal_only_member", free.contains(sequence)},
                 {"conditioned_member", guided.contains(sequence)},
                 {"edits", edits(free_sequence, sequence)},
                 {"eligibility_reasons",
                  Json::array({"finite-consumed-row-neural-mass", "provisional-prefix-only"})}});
    }
    Json result{{"schema", "feedback-next/1"},
                {"source_sha256", source_id()},
                {"plan_sha256", session.spec.plan_sha256},
                {"read_id", session.spec.read_id},
                {"parent_id", session.spec.read_id},
                {"binding", session.last_binding},
                {"previous_state_sha256", previous_state},
                {"state_sha256", state_id(session)},
                {"orientation", "signal-forward"},
                {"initial_prior", "uniform-all-CRF-states"},
                {"location_prior", "uniform-retained-locations-at-each-update"},
                {"locations", locations_json(session.locations)},
                {"location_updates", session.updates},
                {"candidates", candidates},
                {"signal_only_candidate_id",
                 !free_winner.has_value() ? Json(nullptr) : Json(digest(free_sequence))},
                {"provisional_candidate_id",
                 !conditioned_winner.has_value() ? Json(nullptr) : Json(digest(provisional))},
                {"provisional_prefix", provisional},
                {"fixed_policy_rerank_candidate_id",
                 rerank_id.empty() ? Json(nullptr) : Json(rerank_id)},
                {"policy", policy_json(session.spec.policy)},
                {"search",
                 {{"signal_pruned", session.signal_pruned},
                  {"conditioned_pruned", session.conditioned_pruned},
                  {"symbol_bound", session.symbol_bound},
                  {"context_bound", session.context_bound},
                  {"neural_mass", "exact-forward-marginal-over-consumed-rows"},
                  {"partial_rank", "retained-path-location-marginal-with-emission-cost"}}},
                {"abstained", sequences.empty()},
                {"causality", "chunk-delayed-saved-score-replay"},
                {"confidence", {{"kind", "uncalibrated"}, {"posterior_probability", nullptr}}}};
    result["reference_free_candidate_id"] = result.at("signal_only_candidate_id");
    result["empty_prefix_contract"] =
            "zero-base-output-is-explicit-abstention-and-is-not-an-eligible-candidate";
    result["mapper_request_eligible"] = conditioned_winner.has_value();
    result["immutable_prefix"] = "";
    result["revision_semantics"] = "entire-prefix-provisional-zero-irreversible-commits";
    result["available_native_passthrough"] = nullptr;
    result["union_nn_candidate_id"] = union_id.empty() ? Json(nullptr) : Json(union_id);
    result["binding"]["prefix_length"] = provisional.size();
    result["binding"]["source_sha256"] = source_id();
    result["binding"]["plan_sha256"] = session.spec.plan_sha256;
    result["binding"]["resource_manifest"] = session.spec.resource_manifest;
    result["binding"]["previous_state_sha256"] = previous_state;
    result["binding"]["location_producer_receipt"] =
            session.updates.empty() ? Json(nullptr) : session.updates.back().at("producer_receipt");
    result["binding"]["availability"] = {
            {"kind", "released-score-block"},   {"row_begin", session.consumed.back().row_begin},
            {"row_end", session.consumed_rows}, {"available_row_end", session.consumed_rows},
            {"whole_chunk_lookahead", true},    {"signal_geometry", nullptr}};
    result["batch_sha256"] = digest(result.dump());
    return result;
}
Json edits(const std::string& source, const std::string& target) {
    dna(source);
    dna(target);
    require(source.size() <= 8192 && target.size() <= 8192, "edit reconstruction bounds");
    const auto width = target.size() + 1;
    std::vector<std::size_t> dp((source.size() + 1) * width);
    for (std::size_t i = 0; i <= source.size(); ++i) {
        dp[i * width] = i;
    }
    for (std::size_t j = 0; j <= target.size(); ++j) {
        dp[j] = j;
    }
    for (std::size_t i = 1; i <= source.size(); ++i) {
        for (std::size_t j = 1; j <= target.size(); ++j) {
            dp[i * width + j] =
                    std::min({dp[(i - 1) * width + j] + 1, dp[i * width + j - 1] + 1,
                              dp[(i - 1) * width + j - 1] +
                                      static_cast<std::size_t>(source[i - 1] != target[j - 1])});
        }
    }
    Json reverse = Json::array();
    auto i = source.size();
    auto j = target.size();
    while (i > 0 || j > 0) {
        if (i > 0 && j > 0 &&
            dp[i * width + j] == dp[(i - 1) * width + j - 1] +
                                         static_cast<std::size_t>(source[i - 1] != target[j - 1])) {
            --i;
            --j;
            if (source[i] != target[j]) {
                reverse.push_back({{"offset", i},
                                   {"ref", source.substr(i, 1)},
                                   {"alt", target.substr(j, 1)}});
            }
        } else if (i > 0 && dp[i * width + j] == dp[(i - 1) * width + j] + 1) {
            --i;
            reverse.push_back({{"offset", i}, {"ref", source.substr(i, 1)}, {"alt", ""}});
        } else {
            --j;
            reverse.push_back({{"offset", i}, {"ref", ""}, {"alt", target.substr(j, 1)}});
        }
    }
    std::reverse(reverse.begin(), reverse.end());
    require(apply_edits(source, reverse) == target, "edit reconstruction differs");
    return reverse;
}
std::string apply_edits(const std::string& source, const Json& changes) {
    std::string result;
    std::size_t cursor{};
    for (const auto& change : changes) {
        const auto offset = change.at("offset").get<std::size_t>();
        const auto ref = change.at("ref").get<std::string>();
        require(offset >= cursor && offset <= source.size() &&
                        source.substr(offset, ref.size()) == ref,
                "edit source/overlap differs");
        result += source.substr(cursor, offset - cursor) + change.at("alt").get<std::string>();
        cursor = offset + ref.size();
    }
    return result + source.substr(cursor);
}
}
