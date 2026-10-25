#pragma once
#include "context_study/packet.h"
#include <cstdint>

namespace context_decision {
inline constexpr std::uint64_t maximum_work_cells = 2000000000;
struct Decision {
    context_study::Choice proposed, accepted;
    std::size_t eligible{}, feasible{};
};
Decision choose(const context_study::CandidateCase &, bool partial, double weight = 0.5);
std::uint64_t price(const context_study::CandidateCase &);
std::vector<std::size_t> indices(const context_study::Packet &, const std::string &);
std::string evaluate(const context_study::Packet &, const std::string &,
                     const std::filesystem::path &);
std::size_t controls();
}
