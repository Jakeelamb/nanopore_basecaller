#include "indel_feedback/core.h"

#include <algorithm>
#include <fstream>
#include <set>

namespace indel_feedback {
namespace {
std::size_t interval(const Spans& domain, std::size_t position) {
    const auto it = std::upper_bound(domain.begin(), domain.end(), Span{position, std::numeric_limits<std::size_t>::max()});
    if (it == domain.begin()) {
        return domain.size();
    }
    const auto before = std::prev(it);
    return position < before->second ? static_cast<std::size_t>(before - domain.begin()) : domain.size();
}
void valid_spans(const Spans& values, std::size_t maximum) {
    std::size_t previous{};
    for (const auto& [begin, end] : values) {
        require(begin < end && end <= maximum && begin >= previous, "domain interval bound/order/overlap");
        previous = end;
    }
}
Json annotations(const std::string& reference, std::size_t r, const std::string& word,
                 bool insertion, std::size_t q, std::size_t query_width, const Geometry* geometry) {
    const auto end = r + (insertion ? 0 : word.size());
    const bool constant = !word.empty() && word.front() != 'N' && std::all_of(word.begin(), word.end(), [&](char base) { return base == word.front(); });
    const bool hp = constant && ((r > 0 && reference[r - 1] == word.front()) || (end < reference.size() && reference[end] == word.front()));
    bool tandem{};
    for (std::size_t period = 2; period <= 6; ++period) {
        if (r < period || reference.size() - r < period) {
            continue;
        }
        bool repeated = true;
        bool nonconstant{};
        for (std::size_t i = 0; i < period; ++i) {
            repeated = repeated && reference[r - period + i] == reference[r + i] && reference[r + i] != 'N';
            nonconstant = nonconstant || reference[r + i] != reference[r];
        }
        tandem = tandem || (repeated && nonconstant);
    }
    Json boundary = nullptr, overlap = nullptr;
    if (geometry != nullptr) {
        boundary = false;
        overlap = false;
        for (const auto point : geometry->boundaries) {
            const auto low = q > geometry->radius ? q - geometry->radius : 0;
            const auto high = q + query_width + geometry->radius;
            if (low <= point && point <= high) {
                boundary = true;
            }
        }
        for (const auto& [begin, finish] : geometry->overlaps) {
            if (query_width == 0 ? begin <= q && q < finish : begin < q + query_width && q < finish) {
                overlap = true;
            }
        }
    }
    return {{"homopolymer_compatible", hp}, {"short_tandem_context", tandem},
            {"unknown_mechanism", !hp && !tandem}, {"chunk_boundary_near", boundary},
            {"chunk_overlap", overlap}, {"attributes_overlap_not_partition", true}};
}
std::map<std::string, std::string> fasta(const fs::path& path) {
    std::ifstream input(path);
    require(input.good(), "cannot read reference FASTA");
    std::map<std::string, std::string> result;
    std::string line, current;
    while (std::getline(input, line)) {
        require(!line.empty() && line.find('\r') == std::string::npos, "invalid FASTA line");
        if (line.front() == '>') {
            current = line.substr(1, line.find_first_of(" \t", 1) - 1);
            require(!current.empty() && result.emplace(current, "").second, "duplicate/empty FASTA contig");
        } else {
            require(!current.empty(), "FASTA sequence before header");
            dna(line, true);
            result.at(current) += line;
        }
    }
    require(input.eof() && !result.empty(), "FASTA read failed");
    return result;
}
bool autosome(const std::string& contig) {
    const auto name = contig.starts_with("chr") ? contig.substr(3) : contig;
    if (name.empty() || name.front() == '0' || !std::all_of(name.begin(), name.end(), [](char c) { return c >= '0' && c <= '9'; })) {
        return false;
    }
    const auto number = natural(name);
    return number >= 1 && number <= 22;
}
}
Classified classify_alignment(const std::string& sequence, const std::string& quality,
                              const std::string& reference, std::size_t start,
                              const std::string& cigar_text, const Spans& domain,
                              const Geometry* geometry) {
    dna(sequence, true);
    require(sequence.size() == quality.size() && std::all_of(quality.begin(), quality.end(), [](char c) { return c >= 33 && c <= 126; }), "SEQ/QUAL mismatch/alphabet");
    require(start <= reference.size(), "reference start bound");
    valid_spans(domain, reference.size());
    if (geometry != nullptr) {
        valid_spans(geometry->overlaps, sequence.size());
        require(std::is_sorted(geometry->boundaries.begin(), geometry->boundaries.end()) && std::all_of(geometry->boundaries.begin(), geometry->boundaries.end(), [&](auto p) { return p <= sequence.size(); }), "chunk geometry bounds");
    }
    Classified result;
    std::size_t r = start, q{};
    for (const auto& [length, op] : cigar(cigar_text)) {
        const bool query_op = op != 'D';
        const bool ref_op = op == '=' || op == 'X' || op == 'D';
        require((!query_op || length <= sequence.size() - q) && (!ref_op || length <= reference.size() - r), "CIGAR cursor bound");
        const auto r_begin = r, q_begin = q;
        std::size_t eligible{};
        if (op == '=' || op == 'X') {
            for (std::size_t i = 0; i < length; ++i) {
                const bool equal = sequence[q] != 'N' && reference[r] != 'N' && sequence[q] == reference[r];
                require((op == '=') == equal, "EQX disagrees with SEQ/reference");
                if (interval(domain, r) < domain.size()) {
                    require(reference[r] != 'N', "noncanonical eligible reference");
                    equal ? ++result.counts.m : ++result.counts.x;
                    ++eligible;
                } else {
                    ++result.excluded_query_bases;
                }
                ++q; ++r;
            }
        } else if (op == 'I') {
            const auto left = r > 0 ? interval(domain, r - 1) : domain.size();
            const bool included = r > 0 && r < reference.size() && left < domain.size() && interval(domain, r) == left;
            if (included) {
                eligible = length;
                result.counts.i += length;
            } else {
                ++result.excluded_insertion_events;
                result.excluded_query_bases += length;
            }
            q += length;
        } else if (op == 'D') {
            for (std::size_t i = 0; i < length; ++i) {
                if (interval(domain, r) < domain.size()) {
                    require(reference[r] != 'N', "noncanonical eligible deletion");
                    ++eligible; ++result.counts.d;
                } else {
                    ++result.excluded_deletion_bases;
                }
                ++r;
            }
        } else {
            q += length;
        }
        if ((op == 'I' || op == 'D' || op == 'X') && eligible > 0) {
            if (op == 'I') { ++result.insertion_events; }
            if (op == 'D') { ++result.deletion_events; }
            if (op == 'X') { ++result.substitution_events; }
            const auto word = op == 'I' ? sequence.substr(q_begin, length) : reference.substr(r_begin, length);
            result.events.push_back({{"op", std::string(1, op)}, {"reference_begin", r_begin}, {"reference_end", r},
                {"query_begin_alignment_orientation", q_begin}, {"query_end_alignment_orientation", q},
                {"operation_bases", length}, {"eligible_bases", eligible}, {"crossing_domain", eligible != length},
                {"annotations", annotations(reference, r_begin, word, op == 'I', q_begin, q - q_begin, geometry)}});
        }
    }
    require(q == sequence.size(), "CIGAR does not consume complete SEQ");
    return result;
}
Json classify_request(const Json& request) {
    require(request.at("schema") == "indel-classification-request/1", "classifier schema differs");
    const auto side = request.at("side").get<std::string>();
    require(side == "left" || side == "right", "pairer side differs");
    for (const auto& key : {"sam", "reference", "parents", "matched_bed", "pair_parents"}) {
        check_pin(request.at(key));
    }
    const auto reference = fasta(request.at("reference").at("path").get<std::string>());
    std::map<std::string, Counts> totals, expected;
    std::map<std::string, std::size_t> exposure;
    {
        std::ifstream input(request.at("parents").at("path").get<std::string>());
        std::string line;
        while (std::getline(input, line)) {
            require(!line.empty() && totals.emplace(line, Counts{}).second, "duplicate/empty frozen parent");
            exposure.emplace(line, 0);
        }
        require(input.eof() && totals.size() == request.at("expected_parent_count").get<std::size_t>(), "frozen parent count/read differs");
    }
    std::map<std::pair<std::string, std::string>, Spans> domains;
    {
        std::ifstream input(request.at("matched_bed").at("path").get<std::string>());
        std::string line;
        while (std::getline(input, line)) {
            const auto row = split(line);
            require(row.size() == 4 && totals.contains(row[3]) && reference.contains(row[0]), "foreign/malformed paired domain");
            const auto begin = natural(row[1]), end = natural(row[2]);
            domains[{row[3], row[0]}].emplace_back(begin, end);
        }
        require(input.eof(), "matched BED read failed");
        for (const auto& [key, values] : domains) {
            valid_spans(values, reference.at(key.second).size());
            for (const auto& [begin, end] : values) { exposure.at(key.first) += end - begin; }
        }
    }
    {
        std::ifstream input(request.at("pair_parents").at("path").get<std::string>());
        std::string line;
        require(static_cast<bool>(std::getline(input, line)), "missing pairer parent header");
        const auto header = split(line);
        std::map<std::string, std::size_t> columns;
        for (std::size_t i = 0; i < header.size(); ++i) { require(columns.emplace(header[i], i).second, "duplicate pairer column"); }
        while (std::getline(input, line)) {
            const auto row = split(line);
            require(row.size() == header.size() && totals.contains(row.at(columns.at("parent"))), "pairer parent fields differ");
            const auto parent = row.at(columns.at("parent"));
            Counts count{natural(row.at(columns.at(side + "_m"))), natural(row.at(columns.at(side + "_x"))), natural(row.at(columns.at(side + "_i"))), natural(row.at(columns.at(side + "_d")))};
            require(expected.emplace(parent, count).second && exposure.at(parent) == natural(row.at(columns.at("refexposure"))), "pairer duplicate/exposure mismatch");
        }
        require(input.eof() && expected.size() == totals.size(), "pairer parent universe differs");
    }
    Json events = Json::array(), disposition = Json::object();
    std::map<std::string, std::pair<std::string, bool>> children;
    std::map<std::string, std::size_t> dictionary;
    std::ifstream input(request.at("sam").at("path").get<std::string>());
    std::string line;
    std::size_t insertion_events{}, deletion_events{}, substitution_events{}, excluded_insertions{}, excluded_deletions{}, excluded_query{};
    bool records_started{};
    while (std::getline(input, line)) {
        const auto row = split(line);
        require(!row.empty() && !row[0].empty(), "empty SAM line");
        if (line.front() == '@') {
            require(!records_started, "SAM header after records");
            if (row[0] == "@SQ") {
                std::map<std::string, std::string> tags;
                for (std::size_t i = 1; i < row.size(); ++i) {
                    const auto colon = row[i].find(':');
                    require(colon != std::string::npos && tags.emplace(row[i].substr(0, colon), row[i].substr(colon + 1)).second, "SAM SQ malformed");
                }
                require(dictionary.emplace(tags.at("SN"), natural(tags.at("LN"))).second, "SAM duplicate SQ");
            }
            continue;
        }
        records_started = true;
        require(row.size() >= 11, "SAM field count");
        const auto flag = natural(row[1]), mapq = natural(row[4]);
        require(flag <= 65535 && mapq <= 255 && (flag & 1U) == 0, "SAM flag/MAPQ unsupported");
        std::string parent = row[0];
        std::size_t parent_tags{}, nm_tags{}; std::size_t nm{};
        for (std::size_t i = 11; i < row.size(); ++i) {
            if (row[i].starts_with("pi:")) { require(row[i].starts_with("pi:Z:"), "SAM parent type"); parent = row[i].substr(5); ++parent_tags; }
            if (row[i].starts_with("NM:")) { require(row[i].starts_with("NM:i:"), "SAM NM type"); nm = natural(row[i].substr(5)); ++nm_tags; }
        }
        require(parent_tags <= 1 && totals.contains(parent), "foreign/duplicate SAM parent");
        auto [child, inserted] = children.emplace(row[0], std::pair{parent, false});
        static_cast<void>(inserted);
        require(child->second.first == parent, "child parent changed");
        if ((flag & 0x900U) != 0) { continue; }
        require(!child->second.second, "duplicate primary child"); child->second.second = true;
        require(row[9] != "*" && row[10] != "*" && row[9].size() == row[10].size(), "SAM complete SEQ/Q absent");
        dna(row[9], true);
        if ((flag & 4U) != 0) { require(row[5] == "*", "unmapped CIGAR present"); continue; }
        require(reference.contains(row[2]) && natural(row[3]) > 0, "SAM reference/POS differs");
        const auto start = natural(row[3]) - 1;
        const auto key = std::pair{parent, row[2]};
        const Spans empty;
        const bool accepted = autosome(row[2]) && mapq >= 30 && mapq <= 254;
        const auto& domain = accepted && domains.contains(key) ? domains.at(key) : empty;
        auto classified = classify_alignment(row[9], row[10], reference.at(row[2]), start, row[5], domain);
        std::size_t actual_nm{};
        for (const auto& [length, op] : cigar(row[5])) { if (op == 'X' || op == 'I' || op == 'D') { actual_nm += length; } }
        require(nm_tags == 1 && nm == actual_nm, "SAM NM disagrees with complete EQX");
        if (!accepted) { continue; }
        totals.at(parent) += classified.counts;
        insertion_events += classified.insertion_events; deletion_events += classified.deletion_events; substitution_events += classified.substitution_events;
        excluded_insertions += classified.excluded_insertion_events; excluded_deletions += classified.excluded_deletion_bases; excluded_query += classified.excluded_query_bases;
        for (auto& event : classified.events) {
            event["parent"] = parent; event["child"] = row[0]; event["contig"] = row[2]; event["reverse"] = (flag & 16U) != 0;
            events.push_back(std::move(event));
        }
    }
    require(input.eof() && dictionary.size() == reference.size(), "SAM read/dictionary size differs");
    for (const auto& [contig, sequence] : reference) { require(dictionary.contains(contig) && dictionary.at(contig) == sequence.size(), "SAM dictionary/FASTA differs"); }
    for (const auto& [child, item] : children) { static_cast<void>(child); require(item.second, "SAM child has no primary"); }
    Counts aggregate;
    std::size_t zero{};
    for (const auto& [parent, count] : totals) {
        require(count == expected.at(parent) && count.m + count.x + count.d == exposure.at(parent), "classifier/native pairer per-parent counters differ: " + parent);
        aggregate += count; zero += exposure.at(parent) == 0 ? 1U : 0U;
        disposition[parent] = {{"counts", counts_json(count)}, {"reference_exposure", exposure.at(parent)}, {"zero_exposure", exposure.at(parent) == 0}};
    }
    for (const auto& key : {"sam", "reference", "parents", "matched_bed", "pair_parents"}) { check_pin(request.at(key)); }
    return {{"schema", "indel-classification/1"}, {"counts", counts_json(aggregate)}, {"parents", disposition}, {"zero_exposure_parents", zero},
        {"event_counts", {{"i", insertion_events}, {"d", deletion_events}, {"x", substitution_events}}}, {"events", events},
        {"excluded_insertion_events", excluded_insertions}, {"excluded_deletion_bases", excluded_deletions}, {"excluded_query_bases", excluded_query},
        {"annotations_are_overlapping_not_partition", true}, {"native_pairer_reconciled_every_parent", true}, {"request", request}};
}
}
