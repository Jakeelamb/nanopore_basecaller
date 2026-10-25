#pragma once
#include "context_study/packet.h"
#include <cstdint>

namespace context_decision_union {
inline constexpr std::uint64_t maximum_work_cells = 2000000000;
struct Selection {
    context_study::Choice choice;
    std::size_t eligible{}, native{}, escape{}, conditioned{}, graph_only{};
};
Selection choose(const context_study::CandidateCase &);
std::uint64_t replay_bound(const context_study::Packet &);
std::string diagnose(const context_study::Packet &, const std::filesystem::path &);
void verify_sources();
std::string source_json();
std::size_t controls();
}
