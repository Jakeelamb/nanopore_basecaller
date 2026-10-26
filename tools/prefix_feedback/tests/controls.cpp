#include "prefix_feedback/session.h"
#include <algorithm>
#include <cmath>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <set>

namespace prefix_feedback {
namespace {
void near(double actual, double expected) { require(std::abs(actual - expected) <= 1e-10 * std::max(1.0, std::abs(expected)), "numerical tolerance exceeded"); }
void rejects(const std::function<void()>& action) {
    bool rejected = false;
    try { action(); } catch (const std::exception&) { rejected = true; }
    require(rejected, "negative control accepted");
}
Block block(std::size_t begin, std::size_t rows, std::size_t index, std::size_t k = 1) {
    const auto channels = std::size_t{1} << (2 * (k + 1));
    Block result{{{"block_index", index}, {"read_id", "tiny"}, {"orientation", "signal-forward"}, {"available_signal_end", 24576}, {"chunk_index", 0}, {"chunk_row_begin", begin}, {"chunk_row_end", begin + rows}}, begin, begin + rows, {}};
    for (std::size_t row = begin; row < begin + rows; ++row) {
        for (std::size_t channel = 0; channel < channels; ++channel) { result.scores.push_back(static_cast<double>((row * 7 + channel * 3) % 11) / 7.0 - 1.0); }
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
        if (row == rows) { masses[sequence] += mass; return; }
        visit(row + 1, old, sequence, mass * std::exp(static_cast<long double>(stay)));
        for (std::size_t symbol = 0; symbol < 4; ++symbol) {
            const auto target = (old * 4 + symbol) % state_count;
            const auto dropped = old / (state_count / 4);
            const auto channel = target * 4 + dropped;
            visit(row + 1, target, sequence + std::string("ACGT")[symbol], mass * std::exp(static_cast<long double>(scores.scores[row * width + channel])));
        }
    };
    for (std::size_t initial = 0; initial < state_count; ++initial) { visit(0, initial, "", 1.0L / static_cast<long double>(state_count)); }
    return masses;
}
std::map<std::string, double> neural_batch(const Session& session) {
    std::map<std::string, double> result;
    for (const auto& candidate : batch(session, "prior").at("candidates")) { result[candidate.at("sequence")] = candidate.at("neural_log_likelihood"); }
    return result;
}
}
int controls() {
    std::size_t executed{};
    auto run = [&](const char* name, const std::function<void()>& action) { action(); ++executed; std::cout << "PASS " << name << '\n'; };
    run("independent-unpruned-full-census-mass-rank", [] {
        for (std::size_t k = 1; k <= 2; ++k) {
            auto session = start({"tiny", std::string(64, 'a'), k, -0.3, {4096, 8, 0, 8, 0.5}});
            const auto input = block(0, 4, 0, k);
            advance(session, input, std::nullopt);
            const auto expected = enumerate(input, -0.3, k);
            const auto actual = neural_batch(session);
            require(actual.size() == expected.size(), "finalist sequence census differs");
            for (const auto& [sequence, mass] : expected) { require(actual.contains(sequence), "missing enumerated finalist"); near(actual.at(sequence), static_cast<double>(std::log(mass))); }
            const auto output = batch(session, "prior");
            std::string winner; long double best = -1;
            for (const auto& [sequence, mass] : expected) { if (mass > best) { best = mass; winner = sequence; } }
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
        for (const auto& [sequence, mass] : neural_batch(whole)) { near(mass, neural_batch(split).at(sequence)); }
        require(whole.signal == split.signal, "split forward state differs");
        rejects([&] { advance(split, block(2, 2, 2), std::nullopt); });
        rejects([&] { advance(split, block(5, 1, 2), std::nullopt); });
    });
    run("unavailable-future-block-invariance", [] {
        auto a = start({"tiny", std::string(64, 'a'), 1, -0.3, {16, 8, 1, 8, 0.5}}); auto b = a;
        auto future_a = block(2, 2, 1); auto future_b = future_a;
        for (auto& value : future_b.scores) { value += 50.0; }
        advance(a, block(0, 2, 0), std::nullopt); advance(b, block(0, 2, 0), std::nullopt);
        require(batch(a, "same") == batch(b, "same") && state_json(a) == state_json(b), "future altered preceding output/request prefix");
        advance(a, future_a, std::nullopt); advance(b, future_b, std::nullopt);
        require(neural_batch(a) != neural_batch(b), "future mutation control had no effect when released");
    });
    run("context-emission-only-with-wrong-location-escape", [] {
        auto a = start({"tiny", std::string(64, 'a'), 1, -0.3, {4096, 8, 0, 8, 20.0}});
        auto b = a;
        Location location{"wrong", "chr1", "+", 0, 1, 1, 0, 1, 1000, 0, "1M", "TTTTTTTT", {{"confidence_feature", "minimap2-MAPQ-not-posterior"}, {"continuation_orientation", "signal-forward"}}};
        a.locations = {location};
        advance(a, block(0, 3, 0), std::nullopt); advance(b, block(0, 3, 0), std::nullopt);
        require(a.signal == b.signal, "wrong context contaminated free beam");
        std::map<std::string, double> ranks;
        for (const auto& candidate : batch(a, "prior").at("candidates")) { ranks[candidate.at("sequence")] = candidate.at("partial_rank"); }
        near(ranks.at(""), likelihood(a, ""));
        near(ranks.at("A"), likelihood(a, "A"));
        near(ranks.at("AA"), likelihood(a, "AA") - 20.0);
    });
    run("ambiguous-location-channel-marginal-and-permutation", [] {
        auto a = start({"tiny", std::string(64, 'a'), 1, -0.3, {4096, 8, 0, 8, 1.0}});
        Location x{"x", "chr1", "+", 0, 1, 1, 0, 1, 1000, 0, "1M", "AAAA", {}};
        auto y = x; y.id = "y"; y.continuation = "TTTT";
        a.locations = {x, y};
        auto old = a.conditioned; a.conditioned.clear();
        for (const auto& node : old) { for (std::size_t index = 0; index < 2; ++index) { auto next = node; next.location = index; next.mass -= std::log(2.0); a.conditioned.push_back(next); } }
        auto b = a; std::reverse(b.locations.begin(), b.locations.end());
        advance(a, block(0, 3, 0), std::nullopt); advance(b, block(0, 3, 0), std::nullopt);
        auto result = batch(a, "prior"); auto other = batch(b, "prior");
        require(result.at("candidates") == other.at("candidates"), "location permutation changed candidates");
        for (const auto& candidate : result.at("candidates")) {
            if (candidate.at("sequence") == "AA") { near(candidate.at("partial_rank"), candidate.at("neural_log_likelihood").get<double>() + std::log((1.0 + std::exp(-1.0)) / 2.0)); }
        }
    });
    run("no-location-no-finalist-tie-and-bounds", [] {
        auto a = start({"tiny", std::string(64, 'a'), 1, 0.0, {4096, 1, 1, 8, 0.0}});
        auto input = block(0, 1, 0); std::fill(input.scores.begin(), input.scores.end(), 0.0);
        advance(a, input, std::nullopt);
        require(batch(a, "prior").at("provisional_prefix") == "A", "tie is not lexical");
        advance(a, block(1, 1, 1), std::nullopt); require(a.symbol_bound, "symbol bound not disclosed");
        auto empty = start({"tiny", std::string(64, 'a'), 1, 0.0, {1, 0, 0, 8, 0.0}});
        empty.spec.policy.minimum_symbols = 1;
        advance(empty, block(0, 1, 0), std::nullopt);
        require(batch(empty, "prior").at("abstained") == true, "no finalist not explicit");
        auto pruned = start({"tiny", std::string(64, 'a'), 1, 0.0, {1, 8, 1, 8, 0.5}});
        advance(pruned, block(0, 2, 0), std::nullopt); require(pruned.signal_pruned && pruned.conditioned_pruned, "pruning not disclosed");
    });
    run("CIGAR-both-strands-and-foreign-prefix-rejections", [] {
        const std::string plus = "prefix\t10\t0\t10\t+\tchr1\t1000\t20\t31\t9\t11\t42\tcg:Z:5M1D5M\n";
        const std::string minus = "prefix\t10\t0\t10\t-\tchr1\t1000\t20\t29\t9\t10\t0\tcg:Z:5M1I4M\n";
        require(parse_paf(plus + minus, {{"length", 10}}).size() == 2, "competing strands lost");
        require(parse_paf("", {{"length", 10}}).empty(), "missing location not empty");
        rejects([&] { parse_paf(plus, {{"length", 11}}); });
        rejects([&] { parse_paf(plus + plus, {{"length", 10}}); });
        rejects([&] { parse_paf("prefix\t10\t0\t10\t+\tchr1\t1000\t20\t30\t9\t10\t0\tcg:Z:11M\n", {{"length", 10}}); });
    });
    run("edit-reconstruction-both-strands", [] {
        for (const auto& source : {"ACGT", "AAAA", ""}) {
            for (const auto& target : {"AGT", "ACGTT", "TCGA", ""}) {
                require(apply_edits(source, edits(source, target)) == target, "forward edit reconstruction");
                const auto reverse_source = reverse_complement(source); const auto reverse_target = reverse_complement(target);
                require(apply_edits(reverse_source, edits(reverse_source, reverse_target)) == reverse_target, "reverse edit reconstruction");
            }
        }
    });
    run("foreign-state-endpoint-update-rejects-before-consumption", [] {
        auto a = start({"tiny", std::string(64, 'a'), 1, 0.0, {16, 8, 1, 8, 0.5}});
        advance(a, block(0, 2, 0), std::nullopt);
        const auto before = state_id(a);
        rejects([&] { advance(a, block(2, 2, 1), Json{{"schema", "prefix-location/1"}, {"source_sha256", "foreign"}, {"plan_sha256", std::string(64, 'a')}, {"read_id", "tiny"}}); });
        require(state_id(a) == before, "rejected update mutated state");
    });
    std::cout << Json{{"executed", executed}, {"failed", 0}, {"skipped", 0}, {"tiny_tolerance", 1e-10}}.dump() << '\n';
    return 0;
}
}
