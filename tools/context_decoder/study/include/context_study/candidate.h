#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace context_study {
struct ParentSpan {
    std::size_t begin{}, end{};
};
struct GenomicSpan {
    std::size_t begin{}, end{};
};
struct GuardedLogMass {
    double value{};
};
struct Candidate {
    std::string sequence;
    unsigned origins{};
    std::optional<GuardedLogMass> log_mass;
};
inline constexpr unsigned native_origin = 1, escape_origin = 2, conditioned_origin = 4,
                          graph_origin = 8;
struct Choice {
    std::string sequence;
    double log_mass{}, potential{}, objective{};
    std::string gate{"."};
    bool abstained{};
};
inline constexpr std::array<const char *, 6> roles{
    "native",       "reference_free", "final_rerank_winner",
    "final_rerank", "context_winner", "selected"};
struct CandidateCase {
    std::string id, domain, parent, contig, geometry, ancestry;
    bool reverse{};
    ParentSpan read, owned;
    GenomicSpan reference, core;
    std::size_t future{};
    std::string left, right, native, availability;
    bool escape_capped{}, conditioned_capped{}, escape_empty{}, conditioned_empty{};
    std::vector<std::string> paths, reference_paths;
    std::map<std::string, Candidate> candidates;
    std::map<std::string, Choice> saved;
};
using Replay = std::map<std::string, Choice>;
void require(bool condition, const std::string &message);
bool dna(const std::string &sequence);
std::string oriented(const std::string &sequence, bool reverse);
std::size_t distance(const std::string &query, const std::string &reference);
Replay replay(const CandidateCase &input);
void verify_replay(const CandidateCase &input, const Replay &result);
}
