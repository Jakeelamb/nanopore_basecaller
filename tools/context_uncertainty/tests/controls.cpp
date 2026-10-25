#include "context_uncertainty/uncertainty.h"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <functional>
#include <limits>
#include <numeric>
#include <set>
#include <sstream>
#include <unistd.h>

namespace context_uncertainty {
namespace {
struct Checks {
    std::size_t assertions{}, paths{}, edge_comparisons{};
    void expect(bool value, const std::string &message) {
        ++assertions;
        require(value, "Uncertainty control: " + message);
    }
    void close(double a, double b, double tolerance, const std::string &message) {
        expect(std::isfinite(a) && std::isfinite(b) && std::abs(a - b) <= tolerance, message);
    }
    void rejects(const std::function<void()> &call, const std::string &message,
                 const std::string &expected = "") {
        bool rejected = false;
        try {
            call();
        } catch (const std::exception &error) {
            rejected =
                expected.empty() || std::string(error.what()).find(expected) != std::string::npos;
        }
        expect(rejected, message);
    }
};
std::pair<std::size_t, std::size_t> independent_transition(std::size_t state, std::size_t base,
                                                           std::size_t k) {
    std::vector<std::size_t> digits(k);
    for (std::size_t i = k; i > 0; --i) {
        digits[i - 1] = state % 4;
        state /= 4;
    }
    const auto oldest = digits.front();
    std::size_t next{};
    for (std::size_t i = 1; i < digits.size(); ++i)
        next = next * 4 + digits[i];
    next = next * 4 + base;
    return {next, next * 4 + oldest};
}
struct Oracle {
    long double partition{};
    std::vector<long double> edges;
    std::size_t paths{};
};
Oracle enumerate(const Frame &frame, bool wrong_layout = false) {
    const auto states = std::size_t{1} << (2 * frame.state_length);
    Oracle result;
    result.edges.resize(frame.timesteps * states * 5);
    std::vector<std::size_t> history;
    std::function<void(std::size_t, std::size_t, long double)> walk;
    walk = [&](std::size_t time, std::size_t state, long double weight) {
        if (time == frame.timesteps) {
            result.partition += weight;
            for (const auto edge : history)
                result.edges[edge] += weight;
            ++result.paths;
            return;
        }
        history.push_back((time * states + state) * 5 + 4);
        walk(time + 1, state, weight * std::exp(static_cast<long double>(frame.stay)));
        history.pop_back();
        for (std::size_t base = 0; base < 4; ++base) {
            const auto [next, native_channel] =
                independent_transition(state, base, frame.state_length);
            const auto channel = wrong_layout ? state * 4 + base : native_channel;
            history.push_back((time * states + state) * 5 + base);
            walk(time + 1, next,
                 weight *
                     std::exp(static_cast<long double>(frame.scores[time * states * 4 + channel])));
            history.pop_back();
        }
    };
    for (std::size_t initial = 0; initial < states; ++initial)
        walk(0, initial, 1.0L / static_cast<long double>(states));
    for (auto &edge : result.edges)
        edge /= result.partition;
    return result;
}
Frame fixture(std::size_t k, std::size_t times) {
    Frame frame{times, k, 0.17, {}};
    const auto states = std::size_t{1} << (2 * k);
    for (std::size_t t = 0; t < times; ++t)
        for (std::size_t channel = 0; channel < states * 4; ++channel)
            frame.scores.push_back(0.07 * static_cast<double>((channel * 13 + t * 7) % 19) -
                                   0.03 * static_cast<double>(channel % 7) +
                                   0.11 * static_cast<double>(t));
    return frame;
}
void exhaustive(Checks &check) {
    const std::array<std::pair<std::size_t, std::size_t>, 3> fixtures{{{1, 4}, {2, 2}, {4, 2}}};
    for (const auto &[k, times] : fixtures) {
        const auto frame = fixture(k, times);
        const auto observed = posterior(frame, true);
        const auto oracle = enumerate(frame);
        check.paths += oracle.paths;
        check.close(observed.log_partition, static_cast<double>(std::log(oracle.partition)), 1e-10,
                    "partition matches independent full path census");
        check.expect(observed.edge_probabilities.size() == oracle.edges.size(),
                     "complete per-edge census");
        for (std::size_t i = 0; i < oracle.edges.size(); ++i) {
            check.close(observed.edge_probabilities[i], static_cast<double>(oracle.edges[i]), 1e-10,
                        "each marginalized edge matches independent paths");
            ++check.edge_comparisons;
        }
        const auto states = std::size_t{1} << (2 * k);
        for (std::size_t t = 0; t < times; ++t) {
            std::array<double, 5> sum{};
            for (std::size_t state = 0; state < states; ++state)
                for (std::size_t event = 0; event < 5; ++event)
                    sum[event] +=
                        static_cast<double>(oracle.edges[(t * states + state) * 5 + event]);
            for (std::size_t base = 0; base < 4; ++base)
                check.close(observed.timesteps[t].emitted[base], sum[base], 1e-10,
                            "base marginal from full edges");
            check.close(observed.timesteps[t].stay, sum[4], 1e-10, "stay marginal from full edges");
        }
        if (k == 1) {
            for (std::size_t state = 0; state < states; ++state) {
                const auto [next, channel] = independent_transition(state, 2, k);
                static_cast<void>(next);
                auto plus = frame, minus = frame;
                plus.scores[channel] += 1e-5;
                minus.scores[channel] -= 1e-5;
                const auto derivative =
                    (posterior(plus).log_partition - posterior(minus).log_partition) / 2e-5;
                check.close(derivative, observed.edge_probabilities[state * 5 + 2], 2e-7,
                            "partition derivative equals selected edge posterior");
            }
        }
    }
}
void numerical(Checks &check) {
    Frame symmetric{5, 1, 2, std::vector<double>(5 * 16, 0)};
    const auto observed = posterior(symmetric);
    const auto denominator = std::exp(2.0) + 4;
    check.close(observed.log_partition, 5 * std::log(denominator), 1e-10,
                "uniform initial distribution has no extra state-count factor");
    check.expect(observed.edge_probabilities.empty(), "scan avoids retained edge-array allocation");
    for (const auto &step : observed.timesteps) {
        check.close(step.stay, std::exp(2.0) / denominator, 1e-12, "analytic stay marginal");
        check.close(step.conditional_entropy, std::log(4.0), 1e-12,
                    "analytic base-conditional entropy");
        for (const auto mass : step.emitted)
            check.close(mass, 1 / denominator, 1e-12, "analytic base marginal");
    }
    Frame extreme{128, 1, 1000, std::vector<double>(128 * 16, -1000)};
    const auto stable = posterior(extreme);
    check.expect(std::isfinite(stable.log_partition), "long high-dynamic-range partition finite");
    check.close(stable.timesteps.front().conditional_entropy, std::log(4.0), 1e-10,
                "conditional entropy survives tiny emission underflow");
    auto invalid = symmetric;
    invalid.scores[0] = std::numeric_limits<double>::quiet_NaN();
    check.rejects([&] { static_cast<void>(posterior(invalid)); }, "nonfinite scores reject");
    invalid = symmetric;
    invalid.scores.pop_back();
    check.rejects([&] { static_cast<void>(posterior(invalid)); }, "wrong score shape rejects");
    check.close(half(0x0001), std::ldexp(1.0, -24), 0, "smallest half subnormal");
    check.close(half(0x3c00), 1, 0, "half one");
    check.close(half(0xc000), -2, 0, "half negative two");
    check.close(half(0x7bff), 65504, 0, "largest finite half");
    check.expect(std::signbit(half(0x8000)), "negative half zero retained");
    for (const auto bits : {0x7c00U, 0x7e01U, 0xfc00U})
        check.rejects([&] { static_cast<void>(half(static_cast<std::uint16_t>(bits))); },
                      "nonfinite half rejected");
    Frame dependent{2, 1, -20, std::vector<double>(32, -4)};
    for (std::size_t previous = 0; previous < 4; ++previous)
        for (std::size_t base = 0; base < 4; ++base) {
            const auto [next, channel] = independent_transition(previous, base, 1);
            static_cast<void>(next);
            dependent.scores[channel] = base == 0 ? 0 : base == 1 ? -0.1 : -10;
        }
    dependent.scores[16 + 5] = 4;
    const auto informed = posterior(dependent);
    check.expect(informed.timesteps[0].emitted[1] > 0.9 &&
                     informed.timesteps[0].emitted[1] > informed.timesteps[0].emitted[0],
                 "state-dependent future changes earlier uncertainty; zero backward guide fails");
    const auto correct_layout = enumerate(dependent), wrong_layout = enumerate(dependent, true);
    check.expect(std::abs(std::log(correct_layout.partition) - std::log(wrong_layout.partition)) >
                     0.1L,
                 "wrong predecessor-times-four channel layout fails state-dependent fixture");
}
void score_io(Checks &check) {
    const auto directory = std::filesystem::current_path() / "results/context-feedback" /
                           ("uncertainty-synthetic-" + std::to_string(::getpid()));
    require(std::filesystem::create_directories(directory),
            "Fresh synthetic control directory required");
    const auto path = directory / "p1_b0_s0.scores";
    const std::string header = "DGS1\t2\t1024\t4\t6\t2\t32\t100\t1\t0\t0\t5\t0\tp1_b0\t0\n";
    auto bytes = header + std::string(4096, '\0');
    for (std::size_t i = header.size(); i < bytes.size(); i += 2) {
        bytes[i] = 0;
        bytes[i + 1] = static_cast<char>(0x49);
    }
    synced_write(path, bytes);
    Chunk chunk;
    chunk.timesteps = 2;
    chunk.scores = pin(path);
    Fields meta{{"T", "2"}, {"C", "1024"}, {"time_offset", "0"}, {"token", "p1_b0"}};
    const auto loaded = read_scores(chunk, meta);
    check.expect(loaded.scores.size() == 2048 && loaded.scores.front() == 5 &&
                     loaded.scores.back() == 5,
                 "actual DGS reader clamps every finite half payload value");
    const auto replace = [&](const std::string &value) {
        std::ofstream stream(path, std::ios::binary | std::ios::trunc);
        stream.write(value.data(), static_cast<std::streamsize>(value.size()));
        stream.close();
    };
    auto changed = bytes;
    changed.back() = 0;
    replace(changed);
    check.rejects([&] { static_cast<void>(read_scores(chunk, meta)); },
                  "score payload corruption rejects at expected root hash before deeper guards",
                  "Missing or changed consumed file");
    auto nonfinite = bytes;
    nonfinite[header.size()] = 1;
    nonfinite[header.size() + 1] = static_cast<char>(0x7e);
    replace(nonfinite);
    chunk.scores = pin(path);
    check.rejects([&] { static_cast<void>(read_scores(chunk, meta)); },
                  "independently pinned nonfinite fixture reaches half guard",
                  "Nonfinite binary16 score");
    replace(bytes + 'x');
    chunk.scores = pin(path);
    check.rejects([&] { static_cast<void>(read_scores(chunk, meta)); },
                  "independently pinned trailing payload reaches length guard",
                  "DGS1 payload length differs");
    replace(bytes.substr(0, bytes.size() - 1));
    chunk.scores = pin(path);
    check.rejects([&] { static_cast<void>(read_scores(chunk, meta)); },
                  "independently pinned truncated payload reaches length guard",
                  "DGS1 payload length differs");
}
void geometry(Checks &check) {
    Frame frame{100, 1, 2, std::vector<double>(1600, 0)};
    Posterior values;
    values.timesteps.resize(100);
    for (std::size_t t = 25; t < 46; ++t) {
        values.timesteps[t].uncertainty = 1;
        values.timesteps[t].conditional_entropy = std::log(4.0);
        values.timesteps[t].stay_entropy = std::log(2.0);
    }
    Parent parent;
    parent.id = "parent";
    parent.contig = "chrFixture";
    parent.cigar = "100=";
    parent.reference_start = 100;
    parent.eligible = true;
    Chunk chunk;
    chunk.id = "parent/0";
    chunk.parent = parent.id;
    chunk.timesteps = 100;
    chunk.retained_end = 100;
    chunk.chunk_end = 100;
    chunk.parent_end = 100;
    Fields meta{{"SEQ", std::string(100, 'A')},
                {"Q", std::string(100, 'I')},
                {"MOVES", std::string(100, '1')}};
    const auto whole = meta;
    const std::vector<std::pair<std::string, std::string>> layouts{{"100=", "100="},
                                                                   {"25=1I74=", "74=1I25="},
                                                                   {"45=1I54=", "54=1I45="},
                                                                   {"25=1D75=", "75=1D25="},
                                                                   {"46=1D54=", "54=1D46="}};
    for (const auto reverse : {false, true}) {
        parent.reverse = reverse;
        for (const auto &[forward, backward] : layouts) {
            const auto &cigar = reverse ? backward : forward;
            parent.cigar = cigar;
            std::map<std::string, std::size_t> excluded;
            const auto proposed = nominate(frame, values, parent, chunk, meta, whole, excluded);
            check.expect(
                !proposed.empty() && proposed.front().read_begin == 25 &&
                    proposed.front().read_end == 46,
                "neural maximum fixes native center without reference-disagreement ranking");
            const auto length = cigar.find('I') != std::string::npos   ? 20U
                                : cigar.find('D') != std::string::npos ? 22U
                                                                       : 21U;
            check.expect(proposed.front().core_ref_end - proposed.front().core_ref_begin == length,
                         "both-strand anchor cuts preserve boundary insertions/deletions");
            check.expect(proposed.front().time_begin == 15 && proposed.front().time_end == 66,
                         "expanded guard and future availability stay in retained chunk");
        }
    }
    parent.reverse = false;
    parent.cigar = "20=1S79=";
    std::map<std::string, std::size_t> excluded;
    const auto clipped = nominate(frame, values, parent, chunk, meta, whole, excluded);
    check.expect(excluded["native_guard_gapped_or_clipped"] > 0 &&
                     std::none_of(clipped.begin(), clipped.end(),
                                  [](const auto &p) { return p.read_begin == 25; }),
                 "clipped flanks exclude the otherwise preferred core");
    parent.cigar = "100=";
    chunk.chunk_start = 20;
    chunk.parent_start = 20;
    chunk.retained_start = 20;
    for (const auto reverse : {false, true}) {
        parent.reverse = reverse;
        for (std::size_t preferred = 30; preferred <= 34; ++preferred) {
            Posterior boundary;
            boundary.timesteps.resize(100);
            for (std::size_t t = preferred; t < preferred + 21; ++t)
                boundary.timesteps[t].uncertainty = 1;
            const auto bounded = nominate(frame, boundary, parent, chunk, meta, whole, excluded);
            check.expect(
                !bounded.empty() && bounded.front().read_begin == 34 &&
                    std::all_of(bounded.begin(), bounded.end(),
                                [](const auto &p) { return p.read_begin >= 34; }),
                "both strands reject retained starts30..33 and admit exact context boundary34");
        }
    }
}
void nominations(Checks &check) {
    std::vector<Proposal> values;
    for (std::size_t i = 0; i < 80; ++i) {
        Proposal p;
        p.parent = i < 40 ? "parentA" : "parentB";
        p.chunk = p.parent + "/0";
        p.read_begin = (i % 40) * 5;
        p.read_end = p.read_begin + 21;
        p.uncertainty = static_cast<double>((i * 17) % 13) / 13;
        p.tie = sha256(std::to_string(i));
        values.push_back(p);
    }
    const auto ordered = select(values, 512);
    std::reverse(values.begin(), values.end());
    const auto reversed = select(values, 512);
    check.expect(ordered.size() == reversed.size() && ordered.size() > 1,
                 "nomination census permutation invariant");
    for (std::size_t i = 0; i < ordered.size(); ++i)
        check.expect(ordered[i].tie == reversed[i].tie, "deterministic entropy/hash ordering");
    for (std::size_t i = 0; i < ordered.size(); ++i)
        for (std::size_t j = i + 1; j < ordered.size(); ++j)
            check.expect(ordered[i].parent != ordered[j].parent ||
                             ordered[i].read_end <= ordered[j].read_begin ||
                             ordered[j].read_end <= ordered[i].read_begin,
                         "selected owned intervals do not overlap");
    std::vector<Proposal> local;
    for (const auto &parent : {std::string("parentA"), std::string("parentB")}) {
        std::vector<Proposal> group;
        for (const auto &item : values)
            if (item.parent == parent)
                group.push_back(item);
        const auto selected = select(std::move(group), 512);
        local.insert(local.end(), selected.begin(), selected.end());
    }
    const auto merged = select(std::move(local), 7), direct = select(values, 7);
    check.expect(merged.size() == direct.size(), "chunk-local greedy prefixes preserve global cap");
    for (std::size_t i = 0; i < merged.size(); ++i)
        check.expect(merged[i].tie == direct[i].tie, "batched nomination equals unbatched greedy");
    check.rejects([&] { static_cast<void>(select(values, 0)); }, "zero cap rejects");
    values.front().uncertainty = std::numeric_limits<double>::quiet_NaN();
    check.rejects([&] { static_cast<void>(select(values, 512)); },
                  "nonfinite rank rejects before sorting");
}
}
std::string controls() {
    Checks check;
    exhaustive(check);
    numerical(check);
    nominations(check);
    score_io(check);
    geometry(check);
    return "{\"schema\":\"uncertainty-controls/"
           "1\",\"synthetic_only\":true,\"biological_qualification\":false,\"absolute_probability_"
           "tolerance\":1e-10,\"assertions\":" +
           std::to_string(check.assertions) +
           ",\"independent_neural_paths\":" + std::to_string(check.paths) +
           ",\"complete_edge_comparisons\":" + std::to_string(check.edge_comparisons) +
           ",\"negative_controls\":{\"wrong_channel_layout\":true,\"nonfinite_half\":true,\"wrong_"
           "shape\":true,\"zero_cap\":true,\"zero_backward_guide\":true,\"score_corruption_root_"
           "hash\":true,\"independent_nonfinite_fixture\":true,\"boundary_indels\":true}}";
}
}
