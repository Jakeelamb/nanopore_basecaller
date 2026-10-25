#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace context_uncertainty {
struct Frame {
    std::size_t timesteps{}, state_length{};
    double stay{};
    std::vector<double> scores;
};
struct Timestep {
    std::array<double, 4> emitted{};
    double stay{}, conditional_entropy{}, stay_entropy{}, uncertainty{};
};
struct Posterior {
    double log_partition{};
    std::vector<Timestep> timesteps;
    std::vector<double> edge_probabilities;
};
struct Pin {
    std::filesystem::path path;
    std::uintmax_t size{};
    std::string sha256;
    bool operator==(const Pin &) const = default;
};
struct Parent {
    std::string id, contig, cigar, reason;
    std::size_t reference_start{};
    bool reverse{}, eligible{};
    Pin metadata;
};
struct Chunk {
    std::string id, parent;
    std::size_t index{}, timesteps{}, time_offset{}, retained_start{}, retained_end{};
    std::size_t chunk_start{}, chunk_end{}, parent_start{}, parent_end{};
    Pin scores, metadata;
};
struct Inputs {
    Pin manifest;
    std::string ancestry;
    std::map<std::string, Parent> parents;
    std::vector<Chunk> chunks;
    std::vector<Pin> sources;
};
struct Proposal {
    std::string chunk, parent, contig, native, tie;
    std::size_t chunk_index{}, chunk_begin{}, chunk_end{}, read_begin{}, read_end{};
    std::size_t time_begin{}, time_end{}, ref_begin{}, ref_end{}, core_ref_begin{}, core_ref_end{};
    bool reverse{};
    double uncertainty{}, emission_entropy{}, stay_entropy{};
};
struct Invocation {
    std::string command;
    std::filesystem::path output;
    std::map<std::string, std::string> options;
};
using Fields = std::map<std::string, std::string>;
void require(bool, const std::string &);
std::size_t natural(const std::string &);
double finite(const std::string &);
double half(std::uint16_t);
std::size_t transition(std::size_t, std::size_t, std::size_t, std::size_t &);
double log_add(double, double);
Posterior posterior(const Frame &, bool retain_edges = false);
std::vector<Proposal> select(std::vector<Proposal>, std::size_t);
std::vector<Proposal> nominate(const Frame &, const Posterior &, const Parent &, const Chunk &,
                               const Fields &, const Fields &,
                               std::map<std::string, std::size_t> &);
std::string sha256(const std::string &);
Pin pin(const std::filesystem::path &);
void check(const Pin &);
std::string pin_json(const Pin &);
std::string quote(const std::string &);
Fields metadata(const std::filesystem::path &);
Inputs read_inputs(const std::filesystem::path &, const std::string &);
Frame read_scores(const Chunk &, const Fields &);
std::string source_identity();
Invocation begin(int, char **);
void finish(const Invocation &, const std::string &, const std::vector<std::string> &,
            const std::vector<Pin> &);
void synced_write(const std::filesystem::path &, const std::string &);
std::string scan(const Inputs &, std::size_t, std::size_t, const std::filesystem::path &);
std::string merge(const Inputs &, const Pin &, const std::filesystem::path &, std::vector<Pin> &);
std::string controls();
}
