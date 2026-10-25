#include "context_study/oracle.h"
#include "wire_fields.h"
#include <algorithm>
#include <limits>
#include <sstream>
#include <stdexcept>

namespace context_study {
std::size_t EditDag::index(std::size_t r, std::size_t q) const {
    return r * columns_ + q;
}
EditDag::EditDag(std::string reference, std::string query)
    : reference_(std::move(reference)), query_(std::move(query)), columns_(query_.size() + 1) {
    require(dna(reference_) && dna(query_) && reference_.size() + 1 <= 4194304 / columns_,
            "alignment size/DNA exceeds bound");
    const auto rows = reference_.size() + 1;
    forward_.resize(rows * columns_);
    backward_.resize(rows * columns_);
    for (std::size_t r = 0; r < rows; ++r) {
        forward_[index(r, 0)] = static_cast<std::uint32_t>(r);
        backward_[index(r, query_.size())] = static_cast<std::uint32_t>(reference_.size() - r);
    }
    for (std::size_t q = 0; q < columns_; ++q) {
        forward_[index(0, q)] = static_cast<std::uint32_t>(q);
        backward_[index(reference_.size(), q)] = static_cast<std::uint32_t>(query_.size() - q);
    }
    for (std::size_t r = 1; r < rows; ++r)
        for (std::size_t q = 1; q < columns_; ++q) {
            forward_[index(r, q)] =
                std::min({forward_[index(r - 1, q)] + 1, forward_[index(r, q - 1)] + 1,
                          forward_[index(r - 1, q - 1)] +
                              static_cast<std::uint32_t>(reference_[r - 1] != query_[q - 1])});
        }
    for (std::size_t r = reference_.size(); r-- > 0;)
        for (std::size_t q = query_.size(); q-- > 0;) {
            backward_[index(r, q)] =
                std::min({backward_[index(r + 1, q)] + 1, backward_[index(r, q + 1)] + 1,
                          backward_[index(r + 1, q + 1)] +
                              static_cast<std::uint32_t>(reference_[r] != query_[q])});
        }
}
std::uint32_t EditDag::optimum() const {
    return forward_.back();
}
bool EditDag::edge(std::size_t r, std::size_t q, std::size_t nr, std::size_t nq,
                   std::uint32_t cost) const {
    return forward_[index(r, q)] + cost + backward_[index(nr, nq)] == optimum();
}
std::set<std::size_t> EditDag::cuts(std::size_t r) const {
    require(r <= reference_.size(), "event cut out of reference bounds");
    std::set<std::size_t> result;
    for (std::size_t q = 0; q < columns_; ++q)
        if (forward_[index(r, q)] + backward_[index(r, q)] == optimum())
            result.insert(q);
    return result;
}
Counts EditDag::counts(const std::vector<GenomicSpan> &masks) const {
    constexpr auto infinity = std::numeric_limits<std::uint32_t>::max();
    std::vector<Counts> bounds(forward_.size());
    for (auto &cell : bounds)
        for (auto &value : cell)
            value.minimum = infinity;
    bounds[0] = {};
    auto inside = [&](std::size_t r) {
        return std::any_of(masks.begin(), masks.end(),
                           [&](const auto &span) { return span.begin <= r && r < span.end; });
    };
    auto insertion = [&](std::size_t r) {
        return r > 0 && std::any_of(masks.begin(), masks.end(), [&](const auto &span) {
                   return span.begin <= r - 1 && r < span.end;
               });
    };
    auto advance = [&](std::size_t r, std::size_t q, std::size_t nr, std::size_t nq,
                       std::uint32_t cost, std::size_t category, bool counted) {
        if (!edge(r, q, nr, nq, cost))
            return;
        auto &destination = bounds[index(nr, nq)];
        const auto &source = bounds[index(r, q)];
        for (std::size_t k = 0; k < source.size(); ++k) {
            const std::uint32_t delta =
                static_cast<std::uint32_t>(counted && (k == category || (k == 4 && category != 0)));
            destination[k].minimum = std::min(destination[k].minimum, source[k].minimum + delta);
            destination[k].maximum = std::max(destination[k].maximum, source[k].maximum + delta);
        }
    };
    for (std::size_t r = 0; r <= reference_.size(); ++r)
        for (std::size_t q = 0; q <= query_.size(); ++q) {
            if (bounds[index(r, q)][0].minimum == infinity)
                continue;
            if (r < reference_.size() && q < query_.size()) {
                const bool mismatch = reference_[r] != query_[q];
                advance(r, q, r + 1, q + 1, static_cast<std::uint32_t>(mismatch), mismatch ? 1 : 0,
                        inside(r));
            }
            if (q < query_.size())
                advance(r, q, r, q + 1, 1, 2, insertion(r));
            if (r < reference_.size())
                advance(r, q, r + 1, q, 1, 3, inside(r));
        }
    return bounds.back();
}
TruthPacket read_truth(const std::filesystem::path &path, const std::string &hash,
                       const Packet &cases) {
    const auto raw = read_records(path, hash, "context-oracle-truth/1");
    TruthPacket result;
    std::map<std::string, const CandidateCase *> bound;
    for (const auto &input : cases.cases)
        bound.emplace(input.id, &input);
    for (const auto &fields : raw.records) {
        const auto width = wire::truth_widths.find(fields[0]);
        require(width != wire::truth_widths.end() && fields.size() == width->second,
                "unknown truth record or field count");
        require(bound.contains(fields[1]), "foreign truth case");
        if (fields[0] == "TRUTH") {
            using namespace wire::TRUTH;
            require(digest(fields[geometry_sha256]) &&
                        fields[geometry_sha256] == bound.at(fields[case_id])->geometry &&
                        dna(fields[reference_forward]),
                    "truth geometry/DNA mismatch");
            require(fields[reference_forward].size() ==
                        bound.at(fields[case_id])->reference.end -
                            bound.at(fields[case_id])->reference.begin,
                    "truth fragment geometry differs");
            require(result
                        .emplace(
                            fields[case_id],
                            OracleTruth{fields[geometry_sha256], fields[reference_forward], {}, {}})
                        .second,
                    "duplicate truth case");
            continue;
        }
        require(result.contains(fields[1]), "TRUTH must precede dependent records");
        auto &truth = result.at(fields[1]);
        if (fields[0] == "MASK") {
            using namespace wire::MASK;
            require(fields[name] == "100" || fields[name] == "500", "unknown mask name");
            const GenomicSpan span{natural(fields[begin]), natural(fields[end])};
            require(span.begin < span.end, "empty/inverted mask span");
            auto &intervals = truth.masks[fields[name] == "100" ? 0U : 1U];
            require(intervals.empty() || intervals.back().end <= span.begin,
                    "unsorted/overlapping masks");
            intervals.push_back(span);
        } else {
            using namespace wire::EVENT;
            ExactEvent event{fields[event_id],
                             fields[reference_window],
                             fields[alt_haplotype],
                             fields[archived_native_forward],
                             fields[reason],
                             natural(fields[event_start]),
                             natural(fields[event_end]),
                             boolean(fields[resolved])};
            require(!event.id.empty() && dna(event.reference) && dna(event.alternate) &&
                        dna(event.archived_native),
                    "invalid event identity/DNA");
            require(event.begin <= event.end && event.end <= event.reference.size() &&
                        (!event.resolved || event.begin < event.end),
                    "invalid event interval");
            require(!event.resolved || event.alternate != event.reference.substr(
                                                              event.begin, event.end - event.begin),
                    "resolved ALT must differ from REF haplotype");
            require(event.resolved || (!event.reason.empty() && event.reason != "."),
                    "unresolved event needs reason");
            require(std::none_of(truth.events.begin(), truth.events.end(),
                                 [&](const auto &previous) { return previous.id == event.id; }),
                    "duplicate event");
            const auto &input = *bound.at(fields[case_id]);
            const auto native_view =
                oriented(input.left + input.native +
                             input.right.substr(0, input.right.size() - input.future),
                         input.reverse);
            require(native_view == event.archived_native,
                    "archive native view differs from candidate binding");
            truth.events.push_back(std::move(event));
        }
    }
    require(result.size() == cases.cases.size(), "missing truth cases");
    return result;
}
const char *call_name(AlleleCall call) {
    switch (call) {
    case AlleleCall::alt:
        return "alt";
    case AlleleCall::ref:
        return "ref";
    case AlleleCall::other:
        return "other";
    case AlleleCall::unresolved:
        return "unresolved";
    }
    throw std::invalid_argument("invalid allele call");
}
AlleleCall event_call(const std::string &query, const ExactEvent &event) {
    if (!event.resolved)
        return AlleleCall::unresolved;
    const EditDag dag(event.reference, query);
    const auto start = dag.cuts(event.begin), end = dag.cuts(event.end);
    if (start.size() != 1 || end.size() != 1 || *start.begin() > *end.begin())
        return AlleleCall::unresolved;
    const auto projected = query.substr(*start.begin(), *end.begin() - *start.begin());
    if (projected == event.alternate)
        return AlleleCall::alt;
    if (projected == event.reference.substr(event.begin, event.end - event.begin))
        return AlleleCall::ref;
    return AlleleCall::other;
}
const char *effect(const Range &candidate, const Range &baseline, bool resolved, bool exposed,
                   bool identical) {
    if (!exposed)
        return "no_exposure";
    if (!resolved)
        return "unresolved";
    if (identical)
        return "neutral";
    if (candidate.maximum < baseline.minimum)
        return "helpful";
    if (candidate.minimum > baseline.maximum)
        return "harmful";
    if (candidate.minimum == candidate.maximum && baseline.minimum == baseline.maximum &&
        candidate.minimum == baseline.minimum)
        return "neutral";
    return "unresolved";
}
Observation observe(const CandidateCase &input, const Candidate &candidate,
                    const OracleTruth &truth) {
    const auto query = oriented(input.left + candidate.sequence + input.right, input.reverse);
    const EditDag dag(truth.reference, query);
    const auto start = dag.cuts(input.core.begin - input.reference.begin);
    const auto end = dag.cuts(input.core.end - input.reference.begin);
    const auto expected = input.reverse ? input.right.size() : input.left.size();
    Observation result{};
    result.boundary = start.size() == 1 && end.size() == 1 && *start.begin() == expected &&
                      *end.begin() == expected + candidate.sequence.size();
    for (std::size_t mask = 0; mask < 2; ++mask) {
        std::vector<GenomicSpan> local;
        for (const auto &interval : truth.masks[mask]) {
            const auto begin = std::max(interval.begin, input.core.begin),
                       end_pos = std::min(interval.end, input.core.end);
            if (begin < end_pos)
                local.push_back({begin - input.reference.begin, end_pos - input.reference.begin});
        }
        result.counts[mask] = dag.counts(local);
    }
    const auto event_query = oriented(input.left + candidate.sequence +
                                          input.right.substr(0, input.right.size() - input.future),
                                      input.reverse);
    for (const auto &event : truth.events)
        result.events.push_back(event_call(event_query, event));
    return result;
}
}
