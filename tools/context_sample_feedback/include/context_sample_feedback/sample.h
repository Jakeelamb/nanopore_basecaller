#pragma once
#include "context_decoder/guarded_io.h"
#include "context_study/packet.h"
#include <map>
#include <optional>
#include <set>

namespace context_sample_feedback {
enum class SourceState { available, missing, path_cap, length_cap };
enum class BeamState { complete, center_bound, no_finalist, unavailable };
enum class SourceRole { population, exploratory, combined, wrong_source_control };
enum Origin : unsigned { native = 1, free = 2, population = 4, sample = 8, combined = 16 };
struct Source {
    std::string case_id, geometry, physical_window, assumption;
    SourceRole role{SourceRole::exploratory};
    SourceState state{SourceState::missing};
    std::vector<std::string> paths;
    std::size_t unique_paths{}, maximum_length{};
};
struct Candidate {
    std::string sequence;
    unsigned origins{};
    double likelihood{};
};
struct Decision {
    Candidate baseline, proposed, accepted;
    double baseline_potential{}, baseline_objective{}, proposed_potential{}, proposed_objective{};
    std::string gate;
    bool abstained{};
};
struct Run {
    context_decoder::GuardedOutcome historical;
    std::map<std::string, context_decoder::GuardedSearch> searches;
    std::map<std::string, BeamState> states;
    std::map<std::string, Source> sources;
    std::vector<Candidate> candidates;
    std::map<std::string, Decision> decisions;
};
Source canonical_source(Source source);
Source union_source(const Source &left, const Source &right);
context_decoder::GuardedWindow overlay(const context_decoder::GuardedWindow &, const Source &);
BeamState beam_state(const context_decoder::GuardedSearch &);
Decision select(const std::vector<Candidate> &, const std::string &native_center, const Source &,
                BeamState, bool free_ok);
Run infer(const context_decoder::GuardedWindow &, const Source &, const Source &,
          const context_decoder::GuardedPolicy & = {});
void verify_historical(const context_study::CandidateCase &,
                       const context_decoder::GuardedOutcome &);
void bind_frame(const context_study::CandidateCase &, const context_decoder::GuardedBoundFrame &);
std::string physical_window(const context_study::CandidateCase &);
std::map<std::string, Source> read_sources(const std::filesystem::path &, const std::string &,
                                           const std::filesystem::path &, const std::string &,
                                           const context_study::Packet &, bool allow_exploratory);
using Table = std::vector<std::map<std::string, std::string>>;
Table read_table(const std::filesystem::path &, const std::string &, const std::set<std::string> &);
void write_trace(const std::filesystem::path &, const context_decoder::GuardedSearch &);
std::string state_name(BeamState);
std::string state_name(SourceState);
std::size_t controls();
}
