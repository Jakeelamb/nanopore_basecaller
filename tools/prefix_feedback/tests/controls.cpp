#include "prefix_feedback/resource_evidence.h"
#include "prefix_feedback/session.h"

#include <unistd.h>

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <set>
#include <tuple>

namespace prefix_feedback {
namespace {
void near(double actual, double expected) {
    require(std::abs(actual - expected) <= 1e-10 * std::max(1.0, std::abs(expected)),
            "numerical tolerance exceeded");
}
void rejects(const std::function<void()>& action) {
    bool rejected = false;
    try {
        action();
    } catch (const std::exception&) {
        rejected = true;
    }
    require(rejected, "negative control accepted");
}
Block block(std::size_t begin, std::size_t rows, std::size_t index, std::size_t k = 1) {
    const auto channels = std::size_t{1} << (2 * (k + 1));
    Block result{{{"block_index", index},
                  {"read_id", "tiny"},
                  {"orientation", "signal-forward"},
                  {"available_signal_end", 24576},
                  {"chunk_index", 0},
                  {"chunk_row_begin", begin},
                  {"chunk_row_end", begin + rows}},
                 begin,
                 begin + rows,
                 {}};
    for (std::size_t row = begin; row < begin + rows; ++row) {
        for (std::size_t channel = 0; channel < channels; ++channel) {
            result.scores.push_back(static_cast<double>((row * 7 + channel * 3) % 11) / 7.0 - 1.0);
        }
    }
    return result;
}
std::map<std::string, long double> enumerate(const Block& scores, double stay, std::size_t k) {
    // Independent probability-domain path census. No production transition,
    // likelihood, merger or log_add calls enter this oracle.
    std::map<std::string, long double> masses;
    const auto state_count = std::size_t{1} << (2 * k);
    const auto width = state_count * 4;
    const auto rows = scores.row_end - scores.row_begin;
    std::function<void(std::size_t, std::size_t, std::string, long double)> visit;
    visit = [&](std::size_t row, std::size_t old, std::string sequence, long double mass) {
        if (row == rows) {
            masses[sequence] += mass;
            return;
        }
        visit(row + 1, old, sequence, mass * std::exp(static_cast<long double>(stay)));
        for (std::size_t symbol = 0; symbol < 4; ++symbol) {
            const auto target = (old * 4 + symbol) % state_count;
            const auto dropped = old / (state_count / 4);
            const auto channel = target * 4 + dropped;
            visit(row + 1, target, sequence + std::string("ACGT")[symbol],
                  mass * std::exp(static_cast<long double>(scores.scores[row * width + channel])));
        }
    };
    for (std::size_t initial = 0; initial < state_count; ++initial) {
        visit(0, initial, "", 1.0L / static_cast<long double>(state_count));
    }
    return masses;
}
std::map<std::string, double> neural_batch(const Session& session) {
    std::map<std::string, double> result;
    for (const auto& candidate : batch(session, "prior").at("candidates")) {
        result[candidate.at("sequence")] = candidate.at("neural_log_likelihood");
    }
    return result;
}
using StateKey = std::tuple<std::string, std::size_t, std::string>;
struct OracleLocation {
    std::string id;
    std::size_t anchor;
    std::string continuation;
};
using Schedule = std::map<std::size_t, std::vector<OracleLocation>>;
std::vector<OracleLocation> oracle_locations(const Json& update) {
    std::vector<OracleLocation> result;
    for (const auto& location : update.at("locations")) {
        result.push_back(
                {location.at("id"), location.at("query_length"), location.at("continuation")});
    }
    return result;
}
std::map<StateKey, long double> enumerate_states(const Session& session, const Schedule& schedule) {
    // Exhaustive probability-domain enumeration includes initial state, every
    // stay/emission timing, and every normalized location choice at a rebind.
    // It never calls production transition, penalty, merger, or scalar code.
    const auto k = session.spec.state_length;
    const auto states = std::size_t{1} << (2 * k);
    const auto width = states * 4;
    std::vector<double> scores;
    for (const auto& input : session.consumed) {
        scores.insert(scores.end(), input.scores.begin(), input.scores.end());
    }
    std::map<StateKey, long double> result;
    std::function<void(std::size_t, std::size_t, std::string, OracleLocation, long double)> visit;
    visit = [&](std::size_t row, std::size_t state, std::string sequence, OracleLocation location,
                long double mass) {
        if (row == session.consumed_rows) {
            result[{sequence, state, location.id}] += mass;
            return;
        }
        auto consume = [&](const OracleLocation& current, long double weight) {
            visit(row + 1, state, sequence, current,
                  weight * std::exp(static_cast<long double>(session.spec.stay_score)));
            if (sequence.size() >= session.spec.policy.maximum_symbols) {
                return;
            }
            for (std::size_t symbol = 0; symbol < 4; ++symbol) {
                const auto target = (state * 4 + symbol) % states;
                const auto channel = 4 * target + state / (states / 4);
                long double cost{};
                if (!current.id.empty() && sequence.size() >= current.anchor &&
                    sequence.size() - current.anchor < current.continuation.size() &&
                    std::string("ACGT")[symbol] !=
                            current.continuation[sequence.size() - current.anchor]) {
                    cost = static_cast<long double>(session.spec.policy.context_weight);
                }
                visit(row + 1, target, sequence + std::string("ACGT")[symbol], current,
                      weight * std::exp(static_cast<long double>(scores[row * width + channel]) -
                                        cost));
            }
        };
        const auto update = schedule.find(row);
        if (update == schedule.end()) {
            consume(location, mass);
        } else if (update->second.empty()) {
            consume({"", 0, ""}, mass);
        } else {
            for (const auto& replacement : update->second) {
                consume(replacement, mass / static_cast<long double>(update->second.size()));
            }
        }
    };
    for (std::size_t initial = 0; initial < states; ++initial) {
        visit(0, initial, "", {"", 0, ""}, 1.0L / static_cast<long double>(states));
    }
    return result;
}
std::map<std::string, double> check_search(const Session& session,
                                           const Schedule& schedule,
                                           bool contextual) {
    const auto expected = enumerate_states(session, schedule);
    const auto& nodes = contextual ? session.conditioned : session.signal;
    require(nodes.size() == expected.size(),
            "actual retained state/location census differs from oracle");
    std::set<StateKey> seen;
    std::map<std::string, long double> grouped_expected;
    std::map<std::string, double> grouped_actual;
    for (const auto& node : nodes) {
        const auto location = contextual && !session.locations.empty()
                                      ? session.locations.at(node.location).id
                                      : "";
        const StateKey key{node.sequence, node.state, location};
        require(seen.insert(key).second && expected.contains(key),
                "actual retained state/location missing/duplicated");
        near(node.mass, static_cast<double>(std::log(expected.at(key))));
        auto [position, inserted] = grouped_actual.emplace(node.sequence, node.mass);
        if (!inserted) {
            position->second = log_add(position->second, node.mass);
        }
    }
    for (const auto& [key, mass] : expected) {
        grouped_expected[std::get<0>(key)] += mass;
    }
    require(grouped_actual.size() == grouped_expected.size(),
            "actual grouped search census differs");
    for (const auto& [sequence, mass] : grouped_expected) {
        near(grouped_actual.at(sequence), static_cast<double>(std::log(mass)));
    }
    return grouped_actual;
}
struct Choice {
    std::size_t position;
    std::string continuation;
    std::string strand = "+";
};
struct Fixture {
    fs::path root;
    std::size_t serial{};
    Json resources;
    Json manifest;
    Fixture() {
        static std::size_t count{};
        const auto* declared = std::getenv("TMPDIR");
        require(declared != nullptr && *declared != '\0', "declared result TMPDIR required");
        const fs::path temporary(declared);
        const auto owned = fs::canonical(fs::path(source_witness().at("root").get<std::string>()) /
                                         "results/prefix-feedback");
        require(temporary.is_absolute() && fs::is_directory(temporary) &&
                        fs::canonical(temporary) == temporary,
                "canonical existing result TMPDIR required");
        const auto relative = temporary.lexically_relative(owned);
        require(!relative.empty() && !relative.is_absolute() && *relative.begin() != "..",
                "control TMPDIR outside monitored prefix results");
        root = temporary / ("prefix-control-fixtures-" + std::to_string(::getpid()) + "-" +
                            std::to_string(count++));
        require(fs::create_directory(root), "fresh control fixture directory required");
        std::cout << Json{{"fixture_root", root.string()}, {"retained", true}}.dump() << '\n';
        auto file = [&](const std::string& name, const std::string& bytes) {
            const auto path = root / name;
            text(path, bytes);
            return pin(path);
        };
        resources = {
                {"mapper", file("mapper.literal", "synthetic mapper identity, never executed\n")},
                {"reference_index", file("reference-index.literal",
                                         "synthetic index, never used by a native mapper\n")},
                {"reference", file("reference.fasta", ">chr1\n" + std::string(4096, 'A') + "\n")},
                {"reference_fai", file("reference.fasta.fai", "chr1\t4096\t6\t4096\t4097\n")},
                {"samtools",
                 file("samtools.literal", "synthetic samtools identity, never executed\n")},
                {"producer_sources",
                 Json::array({file("recorder.literal",
                                   "synthetic receipt source, not an execution claim\n")})}};
        const auto stdout_path = root / "build.stdout";
        text(stdout_path, "");
        const auto index_argv = Json::array({resources.at("mapper").at("path"), "-d",
                                             resources.at("reference_index").at("path"),
                                             resources.at("reference").at("path")});
        const auto fai_argv = Json::array({resources.at("samtools").at("path"), "faidx",
                                           resources.at("reference").at("path")});
        const auto index_receipt = command(
                "reference-index-build", index_argv,
                Json::array({resources.at("mapper"), resources.at("reference")}), stdout_path,
                Json::object(), Json::array({resources.at("reference_index")}));
        const auto fai_receipt =
                command("reference-fai-build", fai_argv,
                        Json::array({resources.at("samtools"), resources.at("reference")}),
                        stdout_path, Json::object(), Json::array({resources.at("reference_fai")}));
        auto lineage = resources;
        lineage.erase("producer_sources");
        lineage["schema"] = "prefix-reference-lineage/1";
        lineage["complete"] = true;
        auto build = [&](const Json& receipt, const Json& argv) {
            return Json{{"receipt", receipt},
                        {"argv", argv},
                        {"cwd", source_witness().at("root")},
                        {"environment", {{"LC_ALL", "C"}}},
                        {"producer_sources", resources.at("producer_sources")}};
        };
        lineage["index_build"] = build(index_receipt, index_argv);
        lineage["fai_build"] = build(fai_receipt, fai_argv);
        const auto lineage_path = root / "lineage.json";
        fresh(lineage_path, lineage);
        resources["index_provenance"] = pin(lineage_path);
        const auto manifest_path = root / "resources.json";
        fresh(manifest_path, {{"schema", "prefix-resources/1"},
                              {"plan_sha256", std::string(64, 'a')},
                              {"resources", resources}});
        manifest = pin(manifest_path);
    }
    static void text(const fs::path& path, const std::string& bytes) {
        require(!fs::exists(path), "fresh literal fixture file required");
        std::ofstream output(path, std::ios::binary);
        output << bytes;
        output.close();
        require(output.good(), "literal fixture write failed");
    }
    Json command(const std::string& role,
                 const Json& argv,
                 const Json& inputs,
                 const fs::path& stdout_path,
                 const Json& binding,
                 const Json& produced = Json::array()) {
        const auto prefix = root / ("command-" + std::to_string(serial++));
        const fs::path stderr_path(prefix.string() + ".stderr");
        text(stderr_path, "");
        const fs::path time_path(prefix.string() + ".time");
        text(time_path, "synthetic clock fixture, not native timing\n");
        const auto command_identity = Json{{"role", role},
                                           {"argv", argv},
                                           {"cwd", source_witness().at("root")},
                                           {"environment", {{"LC_ALL", "C"}}},
                                           {"inputs", inputs},
                                           {"binding", binding},
                                           {"source_pins", resources.at("producer_sources")},
                                           {"stdout", pin(stdout_path)},
                                           {"produced_files", produced}};
        const fs::path terminal_path(prefix.string() + ".terminal.json");
        fresh(terminal_path, {{"group_empty", true},
                              {"cgroup_empty", true},
                              {"reaped", true},
                              {"command", command_identity},
                              {"fixture_kind", "synthetic-not-native-execution"}});
        const fs::path receipt_path(prefix.string() + ".json");
        fresh(receipt_path, {{"role", role},
                             {"argv", argv},
                             {"cwd", source_witness().at("root")},
                             {"environment", {{"LC_ALL", "C"}}},
                             {"inputs", inputs},
                             {"produced_files", produced},
                             {"binding", binding},
                             {"complete", true},
                             {"exit_status", 0},
                             {"terminal", true},
                             {"stdout", pin(stdout_path)},
                             {"stderr", pin(stderr_path)},
                             {"time", pin(time_path)},
                             {"terminal_proof", pin(terminal_path)},
                             {"source_pins", resources.at("producer_sources")},
                             {"fixture_kind", "synthetic-not-native-execution"}});
        return pin(receipt_path);
    }
    Json update(const Session& session, const std::vector<Choice>& choices) {
        const auto output = batch(session, "fixture");
        const auto sequence = output.at("provisional_prefix").get<std::string>();
        require(!sequence.empty(), "positive mapper fixture requires a genuine provisional prefix");
        const auto qlen = sequence.size();
        const auto prefix = root / ("update-" + std::to_string(serial++));
        const fs::path query(prefix.string() + ".fasta");
        text(query, ">prefix\n" + sequence + "\n");
        std::string paf;
        for (const auto& choice : choices) {
            paf += "prefix\t" + std::to_string(qlen) + "\t0\t" + std::to_string(qlen) + '\t' +
                   choice.strand + "\tchr1\t4096\t" + std::to_string(choice.position) + '\t' +
                   std::to_string(choice.position + qlen) + '\t' + std::to_string(qlen) + '\t' +
                   std::to_string(qlen) + "\t0\tcg:Z:" + std::to_string(qlen) + "M\n";
        }
        const fs::path paf_path(prefix.string() + ".paf");
        text(paf_path, paf);
        Json positions = parse_paf(paf, {{"length", qlen}});
        for (std::size_t index = 0; index < choices.size(); ++index) {
            const auto& choice = choices[index];
            auto& location = positions.at(index);
            const auto begin = choice.strand == "+" ? choice.position + qlen
                                                    : choice.position - choice.continuation.size();
            const auto end = begin + choice.continuation.size();
            const fs::path fasta(prefix.string() + ".reference-" + std::to_string(index) +
                                 ".fasta");
            text(fasta, ">fixture-reference\n" +
                                (choice.strand == "+" ? choice.continuation
                                                      : reverse_complement(choice.continuation)) +
                                "\n");
            const auto binding = Json{{"location_id", location.at("id")},
                                      {"contig", "chr1"},
                                      {"reference_begin", begin},
                                      {"reference_end", end},
                                      {"strand", choice.strand}};
            const auto region = "chr1:" + std::to_string(begin + 1) + "-" + std::to_string(end);
            const auto receipt =
                    command("reference-continuation",
                            Json::array({resources.at("samtools").at("path"), "faidx",
                                         resources.at("reference").at("path"), region}),
                            Json::array({resources.at("reference"), resources.at("reference_fai"),
                                         resources.at("samtools")}),
                            fasta, binding);
            location["continuation"] = choice.continuation;
            location["evidence"] = {{"confidence_feature", "minimap2-MAPQ-not-posterior"},
                                    {"continuation_orientation", "signal-forward"},
                                    {"reference_receipt", receipt},
                                    {"fasta", pin(fasta)},
                                    {"reference_begin", begin},
                                    {"reference_end", end},
                                    {"reference", resources.at("reference")},
                                    {"reference_fai", resources.at("reference_fai")},
                                    {"samtools", resources.at("samtools")},
                                    {"index_provenance", resources.at("index_provenance")}};
        }
        const auto binding =
                Json{{"state_sha256", state_id(session)},
                     {"query_sha256", digest(sequence)},
                     {"available_score_end", session.consumed_rows},
                     {"available_signal_end", session.last_binding.at("available_signal_end")}};
        const auto producer = command(
                "prefix-location",
                Json::array({resources.at("mapper").at("path"), "-x", "map-ont", "-c",
                             "--secondary=yes", "-N", "7", "-t", "2",
                             resources.at("reference_index").at("path"), query.string()}),
                Json::array({pin(query), resources.at("mapper"), resources.at("reference_index")}),
                paf_path, binding);
        return {{"schema", "prefix-location/1"},
                {"source_sha256", source_id()},
                {"plan_sha256", session.spec.plan_sha256},
                {"read_id", session.spec.read_id},
                {"state_sha256", state_id(session)},
                {"query_sequence", sequence},
                {"query_sha256", digest(sequence)},
                {"query_length", qlen},
                {"query", pin(query)},
                {"available_score_end", session.consumed_rows},
                {"available_signal_end", session.last_binding.at("available_signal_end")},
                {"orientation", "signal-forward"},
                {"producer_receipt", producer},
                {"paf", pin(paf_path)},
                {"locations", positions},
                {"mapper", resources.at("mapper")},
                {"reference_index", resources.at("reference_index")},
                {"resource_manifest", manifest}};
    }
};
}
int controls() {
    std::size_t executed{};
    auto run = [&](const char* name, const std::function<void()>& action) {
        action();
        ++executed;
        std::cout << "PASS " << name << '\n';
    };
    run("independent-unpruned-full-census-mass-rank", [] {
        for (std::size_t k = 1; k <= 2; ++k) {
            auto session = start({"tiny", std::string(64, 'a'), k, -0.3, {4096, 8, 0, 8, 0.5}});
            const auto input = block(0, 4, 0, k);
            advance(session, input, std::nullopt);
            const auto expected = enumerate(input, -0.3, k);
            const auto actual = neural_batch(session);
            require(actual.size() + 1 == expected.size() && !actual.contains(""),
                    "eligible finalist sequence census differs");
            for (const auto& [sequence, mass] : expected) {
                if (sequence.empty()) {
                    near(likelihood(session, sequence), static_cast<double>(std::log(mass)));
                } else {
                    require(actual.contains(sequence), "missing enumerated finalist");
                    near(actual.at(sequence), static_cast<double>(std::log(mass)));
                }
            }
            check_search(session, {}, false);
            const auto retained = check_search(session, {}, true);
            const auto output = batch(session, "prior");
            std::string winner;
            long double best = -1;
            for (const auto& candidate : output.at("candidates")) {
                near(candidate.at("partial_rank"), retained.at(candidate.at("sequence")));
            }
            for (const auto& [sequence, mass] : expected) {
                if (!sequence.empty() && mass > best) {
                    best = mass;
                    winner = sequence;
                }
            }
            require(output.at("provisional_prefix") == winner, "final rank differs");
        }
    });
    run("split-step-identical-masses-and-score-ownership", [] {
        auto whole = start({"tiny", std::string(64, 'a'), 1, -0.3, {4096, 8, 0, 8, 0.0}});
        auto split = whole;
        advance(whole, block(0, 4, 0), std::nullopt);
        advance(split, block(0, 2, 0), std::nullopt);
        advance(split, block(2, 2, 1), std::nullopt);
        require(neural_batch(whole).size() == neural_batch(split).size(), "split census differs");
        for (const auto& [sequence, mass] : neural_batch(whole)) {
            near(mass, neural_batch(split).at(sequence));
        }
        require(whole.signal == split.signal, "split forward state differs");
        rejects([&] { advance(split, block(2, 2, 2), std::nullopt); });
        rejects([&] { advance(split, block(5, 1, 2), std::nullopt); });
    });
    run("unavailable-future-block-invariance", [] {
        auto a = start({"tiny", std::string(64, 'a'), 1, -0.3, {16, 8, 1, 8, 0.5}});
        auto b = a;
        auto future_a = block(2, 2, 1);
        auto future_b = future_a;
        for (auto& value : future_b.scores) {
            value += 50.0;
        }
        advance(a, block(0, 2, 0), std::nullopt);
        advance(b, block(0, 2, 0), std::nullopt);
        require(batch(a, "same") == batch(b, "same") && state_json(a) == state_json(b),
                "future altered preceding output/request prefix");
        advance(a, future_a, std::nullopt);
        advance(b, future_b, std::nullopt);
        require(neural_batch(a) != neural_batch(b),
                "future mutation control had no effect when released");
    });
    run("context-emission-only-with-wrong-location-escape", [] {
        auto a = start({"tiny", std::string(64, 'a'), 1, -0.3, {4096, 8, 0, 8, 20.0}});
        auto b = a;
        Location location{"wrong",
                          "chr1",
                          "+",
                          0,
                          1,
                          1,
                          0,
                          1,
                          1000,
                          0,
                          "1M",
                          "TTTTTTTT",
                          {{"confidence_feature", "minimap2-MAPQ-not-posterior"},
                           {"continuation_orientation", "signal-forward"}}};
        a.locations = {location};
        advance(a, block(0, 3, 0), std::nullopt);
        advance(b, block(0, 3, 0), std::nullopt);
        require(a.signal == b.signal, "wrong context contaminated free beam");
        std::map<std::string, double> ranks;
        for (const auto& candidate : batch(a, "prior").at("candidates")) {
            ranks[candidate.at("sequence")] = candidate.at("partial_rank");
        }
        double empty_mass = -std::numeric_limits<double>::infinity();
        for (const auto& node : a.conditioned) {
            if (node.sequence.empty()) {
                empty_mass = log_add(empty_mass, node.mass);
            }
        }
        near(empty_mass, likelihood(a, ""));
        near(ranks.at("A"), likelihood(a, "A"));
        near(ranks.at("AA"), likelihood(a, "AA") - 20.0);
    });
    run("ambiguous-location-channel-marginal-and-permutation", [] {
        auto a = start({"tiny", std::string(64, 'a'), 1, -0.3, {4096, 8, 0, 8, 1.0}});
        Location x{"x", "chr1", "+", 0, 1, 1, 0, 1, 1000, 0, "1M", "AAAA", {}};
        auto y = x;
        y.id = "y";
        y.continuation = "TTTT";
        a.locations = {x, y};
        auto old = a.conditioned;
        a.conditioned.clear();
        for (const auto& node : old) {
            for (std::size_t index = 0; index < 2; ++index) {
                auto next = node;
                next.location = index;
                next.mass -= std::log(2.0);
                a.conditioned.push_back(next);
            }
        }
        auto b = a;
        std::reverse(b.locations.begin(), b.locations.end());
        advance(a, block(0, 3, 0), std::nullopt);
        advance(b, block(0, 3, 0), std::nullopt);
        auto result = batch(a, "prior");
        auto other = batch(b, "prior");
        require(result.at("candidates") == other.at("candidates"),
                "location permutation changed candidates");
        for (const auto& candidate : result.at("candidates")) {
            if (candidate.at("sequence") == "AA") {
                near(candidate.at("partial_rank"),
                     candidate.at("neural_log_likelihood").get<double>() +
                             std::log((1.0 + std::exp(-1.0)) / 2.0));
            }
        }
    });
    run("no-location-no-finalist-tie-and-bounds", [] {
        auto a = start({"tiny", std::string(64, 'a'), 1, 0.0, {4096, 1, 1, 8, 0.0}});
        auto input = block(0, 1, 0);
        std::fill(input.scores.begin(), input.scores.end(), 0.0);
        advance(a, input, std::nullopt);
        require(batch(a, "prior").at("provisional_prefix") == "A", "tie is not lexical");
        advance(a, block(1, 1, 1), std::nullopt);
        require(a.symbol_bound, "symbol bound not disclosed");
        auto empty = start({"tiny", std::string(64, 'a'), 1, 0.0, {1, 8, 2, 8, 0.0}});
        advance(empty, block(0, 1, 0), std::nullopt);
        require(batch(empty, "prior").at("abstained") == true, "no finalist not explicit");
        auto pruned = start({"tiny", std::string(64, 'a'), 1, 0.0, {1, 8, 1, 8, 0.5}});
        advance(pruned, block(0, 2, 0), std::nullopt);
        require(pruned.signal_pruned && pruned.conditioned_pruned, "pruning not disclosed");
    });
    run("CIGAR-both-strands-and-foreign-prefix-rejections", [] {
        const std::string plus =
                "prefix\t10\t0\t10\t+\tchr1\t1000\t20\t31\t9\t11\t42\tcg:Z:5M1D5M\n";
        const std::string minus =
                "prefix\t10\t0\t10\t-\tchr1\t1000\t20\t29\t9\t10\t0\tcg:Z:5M1I4M\n";
        require(parse_paf(plus + minus, {{"length", 10}}).size() == 2, "competing strands lost");
        require(parse_paf("", {{"length", 10}}).empty(), "missing location not empty");
        rejects([&] { parse_paf(plus, {{"length", 11}}); });
        rejects([&] { parse_paf(plus + plus, {{"length", 10}}); });
        rejects([&] {
            parse_paf("prefix\t10\t0\t10\t+\tchr1\t1000\t20\t30\t9\t10\t0\tcg:Z:11M\n",
                      {{"length", 10}});
        });
    });
    run("edit-reconstruction-both-strands", [] {
        for (const auto& source : {"ACGT", "AAAA", ""}) {
            for (const auto& target : {"AGT", "ACGTT", "TCGA", ""}) {
                require(apply_edits(source, edits(source, target)) == target,
                        "forward edit reconstruction");
                const auto reverse_source = reverse_complement(source);
                const auto reverse_target = reverse_complement(target);
                require(apply_edits(reverse_source, edits(reverse_source, reverse_target)) ==
                                reverse_target,
                        "reverse edit reconstruction");
            }
        }
    });
    run("foreign-state-endpoint-update-rejects-before-consumption", [] {
        auto a = start({"tiny", std::string(64, 'a'), 1, 0.0, {16, 8, 1, 8, 0.5}});
        advance(a, block(0, 2, 0), std::nullopt);
        const auto before = state_id(a);
        rejects([&] {
            advance(a, block(2, 2, 1),
                    Json{{"schema", "prefix-location/1"},
                         {"source_sha256", "foreign"},
                         {"plan_sha256", std::string(64, 'a')},
                         {"read_id", "tiny"}});
        });
        require(state_id(a) == before, "rejected update mutated state");
    });
    run("accepted-successive-location-rebinds-full-state-marginals-and-ranks", [] {
        Fixture fixture;
        auto session = start(
                {"tiny", std::string(64, 'a'), 2, -0.3, {4096, 8, 0, 8, 0.7}, fixture.manifest});
        auto free_only = session;
        Schedule schedule;
        advance(session, block(0, 1, 0, 2), std::nullopt);
        advance(free_only, block(0, 1, 0, 2), std::nullopt);
        const std::vector<Choice> initial_locations{{100, "ATTA"}, {200, "TAAT", "-"}};
        const std::vector<Choice> revised_locations{{300, "CGTA"}};
        const std::vector<Choice> no_locations;
        for (std::size_t row = 1; row < 4; ++row) {
            const auto& choices = row == 1   ? initial_locations
                                  : row == 2 ? revised_locations
                                             : no_locations;
            const auto update = fixture.update(session, choices);
            schedule[row] = oracle_locations(update);
            advance(session, block(row, 1, row, 2), update);
            advance(free_only, block(row, 1, row, 2), std::nullopt);
            check_search(session, {}, false);
            const auto ranks = check_search(session, schedule, true);
            const auto output = batch(session, "prior");
            require(output.at("candidates").size() + 1 == ranks.size(),
                    "contextual eligible finalist census differs");
            for (const auto& candidate : output.at("candidates")) {
                near(candidate.at("partial_rank"), ranks.at(candidate.at("sequence")));
            }
            std::string expected_winner;
            double highest = -std::numeric_limits<double>::infinity();
            for (const auto& [sequence, mass] : ranks) {
                if (!sequence.empty() && mass > highest) {
                    highest = mass;
                    expected_winner = sequence;
                }
            }
            require(output.at("provisional_prefix") == expected_winner,
                    "contextual finalist rank winner differs");
            require(session.signal == free_only.signal,
                    "accepted location update changed independent signal branch");
        }
        require(session.updates.size() == 3 && session.locations.empty(),
                "accepted changed/removed location history lost");
    });
    run("accepted-location-permutation-and-identical-boundary-split-stepping", [] {
        Fixture fixture;
        auto a = start(
                {"tiny", std::string(64, 'a'), 1, -0.3, {4096, 8, 0, 8, 0.7}, fixture.manifest});
        advance(a, block(0, 1, 0), std::nullopt);
        auto b = a;
        auto split = a;
        const auto update_a = fixture.update(a, {{100, "ATTA"}, {200, "TAAT", "-"}});
        const auto update_b = fixture.update(b, {{200, "TAAT", "-"}, {100, "ATTA"}});
        advance(a, block(1, 3, 1), update_a);
        advance(b, block(1, 3, 1), update_b);
        advance(split, block(1, 1, 1), update_a);
        advance(split, block(2, 2, 2), std::nullopt);
        const Schedule first{{1, oracle_locations(update_a)}};
        const Schedule permuted{{1, oracle_locations(update_b)}};
        const auto rank_a = check_search(a, first, true);
        const auto rank_b = check_search(b, permuted, true);
        const auto rank_split = check_search(split, first, true);
        require(rank_a.size() == rank_b.size() && rank_a.size() == rank_split.size(),
                "permutation/split census differs");
        for (const auto& [sequence, mass] : rank_a) {
            near(mass, rank_b.at(sequence));
            near(mass, rank_split.at(sequence));
        }
        require(a.signal == b.signal && a.signal == split.signal,
                "location permutation/split changed free branch");
        require(a.conditioned == split.conditioned,
                "identical update boundary split changed retained state masses");
    });
    run("accepted-continuation-and-deep-pin-census-lineage-rejections", [] {
        Fixture fixture;
        auto session = start(
                {"tiny", std::string(64, 'a'), 1, -0.3, {4096, 8, 0, 8, 0.7}, fixture.manifest});
        advance(session, block(0, 1, 0), std::nullopt);
        const auto update = fixture.update(session, {{100, "ATTA"}, {200, "TAAT", "-"}});
        const auto resources = validate_resources(fixture.manifest, session.spec.plan_sha256);
        require(parse_locations(update, resources).size() == 2,
                "accepted nonempty continuation fixture rejected");
        auto reject_deep = [&](const std::function<void()>& action, const std::string& expected) {
            std::string error;
            try {
                action();
            } catch (const std::exception& caught) {
                error = caught.what();
            }
            require(error.find(expected) != std::string::npos &&
                            error.find("source-root") == std::string::npos,
                    "negative did not reach intended deep guard");
        };
        for (const auto& key : {"reference", "reference_fai", "samtools"}) {
            auto changed = update;
            changed["locations"][0]["evidence"][key]["sha256"] = std::string(64, 'f');
            reject_deep([&] { parse_locations(changed, resources); }, "consumed input pin differs");
        }
        for (const auto& key : {"mapper", "reference_index"}) {
            auto changed = update;
            changed[key]["sha256"] = std::string(64, 'f');
            auto copy = session;
            reject_deep([&] { advance(copy, block(1, 1, 1), changed); },
                        "consumed input pin differs");
            require(state_id(copy) == state_id(session),
                    "deep rejected mapper pin mutated session");
        }
        auto changed = update;
        auto receipt = read_json(changed.at("locations")
                                         .at(0)
                                         .at("evidence")
                                         .at("reference_receipt")
                                         .at("path")
                                         .get<std::string>());
        receipt["inputs"] = Json::array({resources.at("samtools"), resources.at("reference_fai"),
                                         resources.at("reference")});
        const auto receipt_path = fixture.root / "foreign-input-census.json";
        fresh(receipt_path, receipt);
        changed["locations"][0]["evidence"]["reference_receipt"] = pin(receipt_path);
        reject_deep([&] { parse_locations(changed, resources); },
                    "reference continuation exact input census differs");
        changed = update;
        auto mapper_receipt =
                read_json(changed.at("producer_receipt").at("path").get<std::string>());
        mapper_receipt["inputs"][1] = resources.at("samtools");
        const auto mapper_path = fixture.root / "foreign-mapper-input-census.json";
        fresh(mapper_path, mapper_receipt);
        changed["producer_receipt"] = pin(mapper_path);
        auto copy_for_mapper = session;
        reject_deep([&] { advance(copy_for_mapper, block(1, 1, 1), changed); },
                    "mapper exact input census differs");
        changed = update;
        receipt = read_json(changed.at("locations")
                                    .at(0)
                                    .at("evidence")
                                    .at("reference_receipt")
                                    .at("path")
                                    .get<std::string>());
        auto terminal = read_json(receipt.at("terminal_proof").at("path").get<std::string>());
        terminal["command"]["role"] = "foreign-command";
        const auto terminal_path = fixture.root / "foreign-terminal.json";
        fresh(terminal_path, terminal);
        receipt["terminal_proof"] = pin(terminal_path);
        const auto terminal_receipt_path = fixture.root / "foreign-terminal-receipt.json";
        fresh(terminal_receipt_path, receipt);
        changed["locations"][0]["evidence"]["reference_receipt"] = pin(terminal_receipt_path);
        reject_deep([&] { parse_locations(changed, resources); },
                    "producer terminal command binding differs");
        const auto foreign = fixture.root / "foreign-reference.fasta";
        Fixture::text(foreign, ">chr1\n" + std::string(4096, 'T') + "\n");
        auto lineage = read_json(resources.at("index_provenance").at("path").get<std::string>());
        lineage["reference"] = pin(foreign);
        const auto lineage_path = fixture.root / "foreign-lineage.json";
        fresh(lineage_path, lineage);
        auto foreign_resources = resources;
        foreign_resources["index_provenance"] = pin(lineage_path);
        const auto manifest_path = fixture.root / "foreign-resources.json";
        fresh(manifest_path, {{"schema", "prefix-resources/1"},
                              {"plan_sha256", session.spec.plan_sha256},
                              {"resources", foreign_resources}});
        reject_deep([&] { validate_resources(pin(manifest_path), session.spec.plan_sha256); },
                    "reference/index lineage identity differs");
        foreign_resources["reference"] = pin(foreign);
        const auto coherent_path = fixture.root / "coherent-foreign-resources.json";
        fresh(coherent_path, {{"schema", "prefix-resources/1"},
                              {"plan_sha256", session.spec.plan_sha256},
                              {"resources", foreign_resources}});
        reject_deep([&] { validate_resources(pin(coherent_path), session.spec.plan_sha256); },
                    "reference/index build relationship differs");
        // Current-pin checking also catches a changed inode body without any
        // source/request-root mutation. This is a literal fixture, never a real tool.
        std::ofstream modified(resources.at("mapper").at("path").get<std::string>(), std::ios::app);
        modified << "changed\n";
        modified.close();
        auto copy = session;
        reject_deep([&] { advance(copy, block(1, 1, 1), update); }, "consumed input pin differs");
    });
    run("valid-zero-symbol-output-is-explicit-abstention", [] {
        auto session = start({"tiny", std::string(64, 'a'), 1, 0.0, {1, 0, 0, 1, 0.0}});
        advance(session, block(0, 1, 0), std::nullopt);
        const auto output = batch(session, "prior");
        require(output.at("candidates").empty() && output.at("abstained") == true &&
                        output.at("reference_free_candidate_id").is_null() &&
                        output.at("signal_only_candidate_id").is_null() &&
                        output.at("provisional_candidate_id").is_null() &&
                        output.at("union_nn_candidate_id").is_null() &&
                        output.at("mapper_request_eligible") == false,
                "zero-symbol abstention contract inconsistent");
        require(likelihood(session, "AA") == -std::numeric_limits<double>::infinity(),
                "impossible sequence mass differs");
        rejects([&] {
            advance(session, block(1, 1, 1),
                    Json{{"schema", "prefix-location/1"},
                         {"source_sha256", source_id()},
                         {"plan_sha256", std::string(64, 'a')},
                         {"read_id", "tiny"}});
        });
    });
    executed += resource_controls();
    std::cout << Json{{"executed", executed},
                      {"failed", 0},
                      {"skipped", 0},
                      {"tiny_tolerance", 1e-10}}
                         .dump()
              << '\n';
    return 0;
}
}
