#pragma once
#include "context_study/candidate.h"
#include "context_study/packet.h"
#include <array>
#include <cstdint>
#include <set>

namespace context_study {
struct Range {
    std::uint32_t minimum{}, maximum{};
    bool operator==(const Range &) const = default;
};
using Counts = std::array<Range, 5>;
struct ExactEvent {
    std::string id, reference, alternate, archived_native, reason;
    std::size_t begin{}, end{};
    bool resolved{};
};
struct OracleTruth {
    std::string geometry, reference;
    std::array<std::vector<GenomicSpan>, 2> masks;
    std::vector<ExactEvent> events;
};
using TruthPacket = std::map<std::string, OracleTruth>;
TruthPacket read_truth(const std::filesystem::path &path, const std::string &hash,
                       const Packet &cases);
class EditDag {
    std::string reference_, query_;
    std::size_t columns_{};
    std::vector<std::uint32_t> forward_, backward_;
    std::size_t index(std::size_t r, std::size_t q) const;
    bool edge(std::size_t r, std::size_t q, std::size_t nr, std::size_t nq,
              std::uint32_t cost) const;

  public:
    EditDag(std::string reference, std::string query);
    std::uint32_t optimum() const;
    std::set<std::size_t> cuts(std::size_t r) const;
    Counts counts(const std::vector<GenomicSpan> &local_masks) const;
};
enum class AlleleCall { alt, ref, other, unresolved };
const char *call_name(AlleleCall call);
AlleleCall event_call(const std::string &query, const ExactEvent &event);
const char *effect(const Range &candidate, const Range &baseline, bool resolved, bool exposed,
                   bool identical);
struct Observation {
    std::array<Counts, 2> counts;
    bool boundary{};
    std::vector<AlleleCall> events;
};
Observation observe(const CandidateCase &input, const Candidate &candidate,
                    const OracleTruth &truth);
std::string evaluate_packet(const Packet &packet, const TruthPacket &truth,
                            const std::filesystem::path &output);
std::string run_controls();
}
