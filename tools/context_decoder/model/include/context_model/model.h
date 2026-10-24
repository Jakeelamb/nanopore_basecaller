#pragma once
#include "context_study/packet.h"
#include <cstddef>
#include <map>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace context_model {
struct MutationRates {
    double insertion{}, deletion{}, substitution{};
};
struct ModelPolicy {
    std::size_t maximum_center{108};
    MutationRates rates;
    double novel_mass{0.5};
};
struct WeightedPath {
    std::string sequence;
    double mass{};
    std::string component{};
};
class ContextDistribution {
  public:
    const std::vector<WeightedPath> &paths() const { return paths_; }
    const std::string &provenance() const { return provenance_; }
    static ContextDistribution uniform(const std::vector<std::string> &, std::string);
    static ContextDistribution weighted(const std::vector<WeightedPath> &, std::string);

  private:
    std::vector<WeightedPath> paths_;
    std::string provenance_;
};
struct ContextInput {
    std::optional<ContextDistribution> distribution;
    std::string reason;
    std::string donor;
};
struct ContextLogMass {
    double graph{}, background{}, mixture{}, log_ratio{};
};
struct ScoredCandidate {
    std::string sequence;
    double signal{};
    ContextLogMass context;
    double objective{};
};
struct ModelScores {
    std::vector<ScoredCandidate> candidates;
    ScoredCandidate baseline, raw, accepted;
    std::string gate;
    bool abstained{};
};
struct Work {
    std::size_t context_cells{}, length_cells{};
    std::size_t total() const;
};
using Arms = std::map<std::string, ContextInput>;
using Assignment = std::map<std::string, Arms>;
inline constexpr std::size_t maximum_work_cells = 25000000;
std::vector<ModelPolicy> fixed_policies();
void validate(const ModelPolicy &);
double log_sequence_mass(std::string_view, std::string_view, const MutationRates &);
double log_length_normalizer(std::size_t, const ModelPolicy &);
ContextLogMass context_mass(std::string_view, const ContextDistribution &, const ModelPolicy &);
Assignment assign_contexts(const context_study::Packet &);
Work price(const context_study::CandidateCase &, const Arms &, const std::vector<ModelPolicy> &);
void enforce_work(const Work &, std::size_t);
ModelScores score_model(const context_study::CandidateCase &, const ContextInput &,
                        const ModelPolicy &);
std::string context_digest(const ContextInput &);
std::string candidate_digest(const context_study::CandidateCase &);
std::string qualify();
std::string score_packet(const context_study::Packet &, const std::filesystem::path &, std::size_t,
                         std::size_t, std::size_t, bool);
}
