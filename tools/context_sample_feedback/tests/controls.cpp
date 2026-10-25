#include "context_sample_feedback/sample.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <functional>
#include <limits>
#include <numeric>
#include <unistd.h>

namespace context_sample_feedback {
namespace {
using context_study::require;
context_decoder::Frame rows(const std::vector<std::array<double, 4>> &values) {
    context_decoder::Frame result{values.size(), 1, 0, -20.0, {}};
    for (const auto &row : values)
        for (std::size_t destination = 0; destination < 4; ++destination)
            for (std::size_t previous = 0; previous < 4; ++previous)
                result.scores.push_back(row[destination]);
    return result;
}
Source available(std::vector<std::string> paths) {
    Source source;
    source.state = SourceState::available;
    source.paths = std::move(paths);
    return canonical_source(std::move(source));
}
std::size_t distance(const std::string &a, const std::string &b) {
    std::vector<std::vector<std::size_t>> matrix(a.size() + 1,
                                                 std::vector<std::size_t>(b.size() + 1));
    for (std::size_t i = 0; i <= a.size(); ++i)
        matrix[i][0] = i;
    for (std::size_t j = 0; j <= b.size(); ++j)
        matrix[0][j] = j;
    for (std::size_t i = 1; i <= a.size(); ++i)
        for (std::size_t j = 1; j <= b.size(); ++j)
            matrix[i][j] =
                std::min({matrix[i - 1][j] + 1, matrix[i][j - 1] + 1,
                          matrix[i - 1][j - 1] + static_cast<std::size_t>(a[i - 1] != b[j - 1])});
    return matrix.back().back();
}
std::map<std::string, long double> enumerate(const context_decoder::Frame &frame) {
    std::map<std::string, long double> result;
    const std::string alphabet = "ACGT";
    const auto states = std::size_t{1} << (2 * frame.state_length);
    std::function<void(std::size_t, std::size_t, std::string, long double)> visit;
    visit = [&](std::size_t t, std::size_t state, std::string sequence, long double mass) {
        if (t == frame.timesteps) {
            result[sequence] += mass;
            return;
        }
        visit(t + 1, state, sequence, mass * std::exp(static_cast<long double>(frame.stay_score)));
        for (std::size_t base = 0; base < 4; ++base) {
            const auto destination = (state * 4 + base) % states;
            const auto channel = destination * 4 + state / (states / 4);
            visit(t + 1, destination, sequence + alphabet[base],
                  mass *
                      std::exp(static_cast<long double>(frame.scores[t * states * 4 + channel])));
        }
    };
    visit(0, frame.initial_state, "", 1.0L);
    return result;
}
}
std::size_t controls() {
    std::size_t count{};
    auto check = [&](bool value, const char *message) {
        require(value, message);
        ++count;
    };
    auto source = available({"C", "", "C", "A"});
    check(source.paths == std::vector<std::string>({"", "A", "C"}),
          "duplicate/order/deletion canonicalization differs");
    check(available({}).state == SourceState::missing &&
              available({""}).state == SourceState::available,
          "empty set differs from deletion");
    check(available({std::string(109, 'A')}).state == SourceState::length_cap,
          "path length cap absent");
    std::vector<std::string> many;
    for (std::size_t i = 0; i < 33; ++i)
        many.push_back(std::string(i, 'A'));
    check(available(many).state == SourceState::path_cap, "unique path cap absent");
    check(available(std::vector<std::string>(64, "A")).state == SourceState::available,
          "cap applied before canonicalization");
    check(union_source(available({"C"}), available({"A", "C"})).paths ==
              std::vector<std::string>({"A", "C"}),
          "population/sample union differs");
    check(union_source(available({"C"}), Source{}).paths == std::vector<std::string>({"C"}),
          "empty-source union discarded available paths");
    check(union_source(available({"C"}), available(many)).state == SourceState::path_cap,
          "capped source silently refilled combined arm");
    const std::vector<Candidate> candidates{
        {"AAA", native, 0.0}, {"CCC", sample, -0.3}, {"CCCC", combined, -0.6}};
    const auto decision = select(candidates, "AAA", available({"CCC"}), BeamState::complete, true);
    check(decision.accepted.sequence == "CCC" && decision.baseline.sequence == "AAA",
          "common U feasible selection differs");
    check(decision.baseline_potential == -3 && decision.baseline_objective == -1.5,
          "contextual NN baseline not recorded");
    check(select(candidates, "AAA", available({"CCCC"}), BeamState::complete, true)
                  .proposed.sequence != "CCCC",
          "infeasible candidate selected");
    check(select(candidates, "AAA", Source{}, BeamState::unavailable, true).accepted.sequence ==
              "AAA",
          "missing source NN fallback differs");
    const std::vector<Candidate> shifted{{"AAA", native, -1}, {"C", sample, 0}};
    check(select(shifted, "AAA", Source{}, BeamState::unavailable, true).accepted.sequence == "C",
          "NN(U) incorrectly forces native identity");
    check(
        select(shifted, "AAA", available({"C"}), BeamState::center_bound, true).accepted.sequence ==
            "AAA",
        "bounded beam did not abstain at native");
    check(select(shifted, "AAA", available({"C"}), BeamState::complete, false).accepted.sequence ==
              "AAA",
          "free failure did not stop source arm");
    check(select({{"C", sample, 0}, {"A", free, 0}}, "C", Source{}, BeamState::unavailable, true)
                  .accepted.sequence == "C",
          "native tie preference differs");
    check(select({{"C", sample, 0}, {"A", free, 0}, {"T", native, -1}}, "T", Source{},
                 BeamState::unavailable, true)
                  .accepted.sequence == "A",
          "lexical tie preference differs");
    for (std::size_t seed = 0; seed < 8; ++seed) {
        context_decoder::Frame frame{4, 1, seed % 4, -0.7, {}};
        for (std::size_t i = 0; i < 64; ++i)
            frame.scores.push_back(-static_cast<double>((i * 17 + seed) % 31) / 10.0);
        context_decoder::GuardedWindow window{
            frame, "A", "T", "C", {context_decoder::Availability::missing, {}}};
        const auto raw = enumerate(frame);
        for (const auto &center :
             {std::string{}, std::string{"A"}, std::string{"C"}, std::string{"AC"}}) {
            const auto expected = std::log(raw.at("A" + center + "T"));
            const auto actual = context_decoder::guarded_likelihood(window, center);
            check(std::abs(static_cast<long double>(actual) - expected) < 1e-11L,
                  "full likelihood differs from raw path enumeration");
        }
        auto context = available({"", "AC", "C"});
        const auto copied = overlay(window, context);
        check(window.center_context.sequences.empty() &&
                  copied.scores.scores == window.scores.scores &&
                  copied.scores.initial_state == window.scores.initial_state &&
                  copied.left_guard == window.left_guard &&
                  copied.right_guard == window.right_guard,
              "context overlay changed original scores/guards/state");
        for (const auto &path : context.paths)
            check(context_decoder::context_potential(path, context.paths, true) ==
                      -static_cast<double>(distance(path, path)),
                  "terminal potential differs from independent edit table");
        std::vector<Candidate> pool;
        for (const auto &[sequence, mass] : raw)
            if (sequence.size() >= 2 && sequence.front() == 'A' && sequence.back() == 'T')
                pool.push_back({sequence.substr(1, sequence.size() - 2), sample,
                                static_cast<double>(std::log(mass))});
        auto ordered = pool;
        std::sort(ordered.begin(), ordered.end(), [](const auto &a, const auto &b) {
            if ((a.sequence == "C") != (b.sequence == "C"))
                return a.sequence == "C";
            return a.sequence < b.sequence;
        });
        auto baseline = ordered.front();
        for (const auto &candidate : ordered)
            if (candidate.likelihood > baseline.likelihood)
                baseline = candidate;
        const auto phi = [&](const std::string &sequence) {
            std::size_t closest = std::numeric_limits<std::size_t>::max();
            for (const auto &path : context.paths)
                closest = std::min(closest, distance(sequence, path));
            return -static_cast<double>(closest);
        };
        auto winner = baseline;
        auto objective = -std::numeric_limits<double>::infinity();
        for (const auto &candidate : ordered)
            if (candidate.likelihood >= baseline.likelihood - 0.5) {
                const auto value = candidate.likelihood + 0.5 * phi(candidate.sequence);
                if (value > objective) {
                    winner = candidate;
                    objective = value;
                }
            }
        const auto accepted =
            objective - (baseline.likelihood + 0.5 * phi(baseline.sequence)) >= 0.5
                ? winner.sequence
                : baseline.sequence;
        const auto actual = select(pool, "C", context, BeamState::complete, true);
        check(actual.baseline.sequence == baseline.sequence &&
                  actual.accepted.sequence == accepted &&
                  actual.baseline_objective == baseline.likelihood + 0.5 * phi(baseline.sequence),
              "common-U decision differs from independent tiny raw-path enumeration");
    }
    context_decoder::GuardedWindow witness{
        rows({{0, -0.1, -9, -9}, {0, -0.1, -9, -9}, {0, -0.1, -9, -9}, {-9, -9, -9, 0}}),
        "",
        "T",
        "AAA",
        {context_decoder::Availability::usable, {"AAA"}}};
    context_decoder::GuardedPolicy policy;
    policy.beam_width = 1;
    policy.max_center = 3;
    const auto new_source = available({"CCCC"});
    const auto result = infer(witness, new_source, available({"AAA"}), policy);
    check(std::none_of(result.historical.candidates.begin(), result.historical.candidates.end(),
                       [](const auto &candidate) { return candidate.choice.sequence == "CCC"; }),
          "new partial-search fixture already exists in old H");
    const auto finalist =
        std::find_if(result.candidates.begin(), result.candidates.end(),
                     [](const auto &candidate) { return candidate.sequence == "CCC"; });
    check(finalist != result.candidates.end() && (finalist->origins & sample) != 0 &&
              (finalist->origins & (free | population)) == 0 &&
              new_source.paths.front() != finalist->sequence,
          "new sample finalist origin was injected or forged");
    check(result.decisions.at("sample").accepted.sequence == "CCC",
          "new partial-search winner absent");
    const auto raw = enumerate(witness.scores);
    check(std::abs(finalist->likelihood - static_cast<double>(std::log(raw.at("CCCT")))) < 1e-11,
          "new partial-search witness full likelihood differs");
    auto duplicated = new_source;
    duplicated.paths = {"CCCC", "CCCC"};
    duplicated = canonical_source(std::move(duplicated));
    check(infer(witness, duplicated, available({"AAA"}), policy)
                  .decisions.at("sample")
                  .accepted.sequence == "CCC",
          "source duplication changed output");
    const auto failed =
        select(result.candidates, witness.native_center, new_source, BeamState::no_finalist, true);
    check(failed.abstained && failed.accepted.sequence == witness.native_center,
          "no-finalist native abstention absent");
    auto capped = witness;
    auto capped_policy = policy;
    capped_policy.beam_width = 128;
    capped_policy.max_center = 1;
    capped.native_center = "A";
    const auto cap_result = infer(capped, new_source, available({"A"}), capped_policy);
    const auto free_state = cap_result.states.at("free");
    const auto free_state_message = "free-bound fixture reached " + state_name(free_state);
    check(free_state == BeamState::center_bound, free_state_message.c_str());
    check(!cap_result.searches.at("free").finalists.empty(),
          "free-bound fixture lacks failed-beam finalists");
    check(!cap_result.searches.at("free").pruned,
          "free-bound fixture unexpectedly pruned a center");
    check(cap_result.candidates.size() == 1, "failed free-beam finalists were admitted to U");
    check(cap_result.candidates.front().sequence == "A" &&
              cap_result.candidates.front().origins == native,
          "failed free-beam finalists were admitted to U");
    for (const auto &[arm, cap_decision] : cap_result.decisions) {
        static_cast<void>(arm);
        check(cap_decision.abstained && cap_decision.accepted.sequence == "A" &&
                  cap_decision.gate == "free_search_native_abstention",
              "free-bound source arm did not abstain at native");
    }
    const auto directory = std::filesystem::temp_directory_path() /
                           ("sample-feedback-source-controls-" + std::to_string(::getpid()));
    require(!std::filesystem::exists(directory), "source control directory already exists");
    std::filesystem::create_directory(directory);
    context_study::CandidateCase input;
    input.id = "ordinary/0/ordinary";
    input.geometry = std::string(64, 'a');
    input.contig = "chr1";
    input.reference = {1, 4};
    input.core = {2, 3};
    input.left = "A";
    input.right = "T";
    context_study::Packet packet{"", {input}};
    const std::string census_header = "case_id\tgeometry_sha256\tphysical_window_"
                                      "sha256\tcoverage\tstatus\tpaths\tfamilies\tcontext_"
                                      "role\tassumption_tag\tstrict_read_level_qualified\n";
    const std::string paths_header =
        "case_id\tgeometry_sha256\tphysical_window_sha256\tsequence_sha256\tsequence\tfamily_"
        "count\tfamily_sha256s\tcontext_role\tassumption_tag\tstrict_read_level_"
        "qualified\tpromotion_eligible\n";
    auto table_control = [&](const std::string &label, const std::string &path,
                             const std::string &role, const std::string &geometry,
                             const std::string &promotion, bool consent, bool reject) {
        const auto census_file = directory / (label + "-cases.tsv");
        const auto paths_file = directory / (label + "-contexts.tsv");
        const auto identity = input.id + '\t' + geometry + '\t' + physical_window(input);
        const auto flags = role + "\tpublished_protocol_pi_dx_preservation_v1\t0";
        context_study::synced_write(census_file, census_header + identity +
                                                     "\tcovered\texploratory_available\t1\t1\t" +
                                                     flags + '\n');
        context_study::synced_write(paths_file, paths_header + identity + '\t' +
                                                    context_study::sha256(path) + '\t' + path +
                                                    "\t1\t" + std::string(64, 'b') + '\t' + flags +
                                                    '\t' + promotion + '\n');
        bool rejected{};
        try {
            const auto parsed =
                read_sources(census_file, context_study::file_sha256(census_file), paths_file,
                             context_study::file_sha256(paths_file), packet, consent);
            require(parsed.at(input.id).paths == std::vector<std::string>{path},
                    "genuine source path/deletion changed");
        } catch (const std::exception &) {
            rejected = true;
        }
        check(rejected == reject, "source table role/geometry/consent/deletion control differs");
    };
    table_control("positive", "AC", "exploratory_published_protocol", input.geometry, "0", true,
                  false);
    table_control("deletion", "", "exploratory_published_protocol", input.geometry, "0", true,
                  false);
    table_control("role", "AC", "strict", input.geometry, "0", true, true);
    table_control("geometry", "AC", "exploratory_published_protocol", std::string(64, 'c'), "0",
                  true, true);
    table_control("promotion", "AC", "exploratory_published_protocol", input.geometry, "1", true,
                  true);
    table_control("consent", "AC", "exploratory_published_protocol", input.geometry, "0", false,
                  true);
    std::filesystem::remove_all(directory);
    return count;
}
}
