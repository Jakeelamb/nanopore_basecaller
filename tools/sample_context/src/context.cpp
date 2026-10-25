#include "sample_context/context.h"
#include <algorithm>
#include <charconv>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <tuple>

namespace sample_context {
namespace {
constexpr std::string_view run = "11d77535b149da7c6f7153939924a9fe29559cc7";
constexpr std::size_t maximum_line = 20000000;
bool eligible_lineage(LineageMode mode) {
    return mode == LineageMode::strict_qualified ||
           mode == LineageMode::exploratory_published_protocol;
}
bool exploratory(LineageMode mode) {
    return mode == LineageMode::unavailable_exploratory ||
           mode == LineageMode::exploratory_published_protocol;
}
std::string context_role(LineageMode mode) {
    return exploratory(mode) ? "exploratory_published_protocol" : "strict";
}
std::string assumption_tag(LineageMode mode) {
    return mode == LineageMode::exploratory_published_protocol
               ? "published_protocol_pi_dx_preservation_v1"
               : ".";
}
struct Header {
    std::map<std::string, Reference> references;
    std::set<std::string> groups;
};
std::map<std::string, std::string> tags(const std::vector<std::string> &fields, std::size_t start) {
    std::map<std::string, std::string> result;
    for (std::size_t i = start; i < fields.size(); ++i) {
        const auto at = fields[i].find(':');
        require(at != std::string::npos && at > 0, "Malformed SAM header tag");
        require(result.emplace(fields[i].substr(0, at), fields[i].substr(at + 1)).second,
                "Duplicate SAM header tag");
    }
    return result;
}
bool hex(std::string_view value, std::size_t width) {
    return value.size() == width && value.find_first_not_of("0123456789abcdef") == value.npos;
}
bool read_name(std::string_view value) {
    return !value.empty() && value != "*" && value.size() <= 512 &&
           std::all_of(value.begin(), value.end(), [](char ch) {
               const auto byte = static_cast<unsigned char>(ch);
               return byte >= 33U && byte <= 126U && ch != '@';
           });
}
void header_line(Header &header, const std::string &line) {
    const auto fields = split(line, '\t');
    if (fields.front() == "@SQ") {
        const auto values = tags(fields, 1);
        require(values.contains("SN") && values.contains("LN") && values.contains("M5") &&
                    hex(values.at("M5"), 32),
                "Supporting reference lacks M5");
        require(header.references
                    .emplace(values.at("SN"), Reference{integer(values.at("LN")), values.at("M5")})
                    .second,
                "Duplicate supporting reference");
    } else if (fields.front() == "@RG") {
        const auto values = tags(fields, 1);
        const auto description =
            values.contains("DS") ? split(values.at("DS"), ' ') : std::vector<std::string>{};
        require(values.contains("ID") && values.contains("SM") && values.at("SM") == "hg002" &&
                    values.contains("PU") && values.at("PU") == "PAW71238" &&
                    std::count(description.begin(), description.end(),
                               "runid=" + std::string(run)) == 1,
                "Supporting RG donor/flowcell/run differs");
        require(header.groups.insert(values.at("ID")).second, "Duplicate supporting RG");
    }
}
void validate_header(const Header &header, const Packet &packet) {
    require(header.groups == packet.groups && !header.groups.empty(),
            "Supporting RG census differs");
    for (const auto &[name, reference] : packet.references) {
        const auto actual = header.references.find(name);
        require(actual != header.references.end() && actual->second.length == reference.length &&
                    actual->second.md5 == reference.md5,
                "Supporting SAM/reference M5 differs");
    }
}
std::optional<std::size_t> mapped(const Read &read, std::uint64_t position) {
    for (const auto &segment : read.segments)
        if (segment.reference_begin <= position && position < segment.reference_end) {
            if (segment.operation == 'M' || segment.operation == '=' || segment.operation == 'X')
                return segment.read_begin +
                       static_cast<std::size_t>(position - segment.reference_begin);
            return std::nullopt;
        }
    return std::nullopt;
}
std::optional<std::pair<std::size_t, std::size_t>> anchor(const Read &read, std::uint64_t begin,
                                                          std::string_view expected) {
    std::optional<std::size_t> first, previous;
    for (std::size_t i = 0; i < expected.size(); ++i) {
        const auto at = mapped(read, begin + i);
        if (!at || (previous && *at != *previous + 1) || read.sequence.at(*at) != expected[i])
            return std::nullopt;
        if (!first)
            first = at;
        previous = at;
    }
    if (!first || !previous)
        return std::nullopt;
    return std::pair{*first, *previous + 1};
}
std::string eligibility(const Read &read) {
    if ((read.flags & (1U | 4U | 256U | 512U | 1024U | 2048U)) != 0)
        return "nonprimary_paired_duplicate_or_failed";
    if (read.mapq < 30 || read.mapq == 255)
        return "mapping_quality";
    if (read.quality == "*")
        return "base_quality_unavailable";
    return "eligible";
}
void lineage_add(std::map<std::string, Lineage> &all, const Read &read) {
    Lineage value{read.parent, read.duplex, read.group, false, {}, !read.parent.has_value()};
    if (read.parent)
        value.observed_parents.insert(*read.parent);
    const auto [it, inserted] = all.emplace(read.name, value);
    if (!inserted) {
        auto &node = it->second;
        node.observed_parents.insert(value.observed_parents.begin(), value.observed_parents.end());
        node.absent_parent_seen = node.absent_parent_seen || value.absent_parent_seen;
        if (node.conflicting || node.parent != value.parent || node.duplex != value.duplex ||
            node.group != value.group) {
            node.conflicting = true;
            node.parent.reset();
        }
    }
}
struct Vote {
    std::string sequence;
    bool conflict{};
    std::set<std::string> reads;
};
std::map<std::string, std::string>
blocked_components(const std::map<std::string, Lineage> &all, const Packet &packet,
                   const std::map<std::string, Family> &families) {
    std::map<std::string, std::string> links;
    const auto find = [&links](const std::string &name) {
        links.try_emplace(name, name);
        auto root = name;
        while (links.at(root) != root)
            root = links.at(root);
        auto current = name;
        while (links.at(current) != current) {
            auto next = links.at(current);
            links.at(current) = root;
            current = next;
        }
        return root;
    };
    for (const auto &[name, node] : all) {
        static_cast<void>(find(name));
        for (const auto &parent : node.observed_parents) {
            const auto a = find(name), b = find(parent);
            if (a != b)
                links.at(std::max(a, b)) = std::min(a, b);
        }
    }
    std::map<std::string, std::string> blocked;
    for (const auto &[name, parent] : links) {
        static_cast<void>(parent);
        if (packet.targets.contains(name) || packet.exclusions.contains(name))
            blocked[find(name)] = "target_family_excluded";
    }
    for (const auto &[name, node] : all) {
        const auto root = find(name);
        if (!blocked.contains(root) && (node.conflicting || !packet.groups.contains(node.group)))
            blocked[root] = "lineage_conflict_or_foreign_RG";
        if (!blocked.contains(root) && (!node.duplex || *node.duplex != 0))
            blocked[root] = "duplex_complement_or_unknown";
        if (!blocked.contains(root) && families.at(name).status == "lineage_cycle_or_depth")
            blocked[root] = "lineage_cycle_or_depth";
    }
    std::map<std::string, std::string> result;
    for (const auto &[name, node] : all) {
        static_cast<void>(node);
        const auto found = blocked.find(find(name));
        if (found != blocked.end())
            result.emplace(name, found->second);
    }
    return result;
}
}
void require(bool value, const std::string &message) {
    if (!value)
        throw std::runtime_error(message);
}
std::vector<std::string> split(std::string_view value, char delimiter) {
    std::vector<std::string> result;
    std::size_t begin{};
    while (true) {
        const auto at = value.find(delimiter, begin);
        result.emplace_back(value.substr(begin, at == value.npos ? value.npos : at - begin));
        if (at == value.npos)
            return result;
        begin = at + 1;
    }
}
std::uint64_t integer(std::string_view value) {
    std::uint64_t result{};
    const auto parsed = std::from_chars(value.data(), value.data() + value.size(), result);
    require(!value.empty() && parsed.ec == std::errc{} && parsed.ptr == value.data() + value.size(),
            "Invalid unsigned integer");
    return result;
}
std::string reverse_complement(std::string_view value) {
    std::string result;
    result.reserve(value.size());
    for (auto it = value.rbegin(); it != value.rend(); ++it) {
        const auto at = std::string_view("ACGT").find(*it);
        require(at != std::string_view::npos, "Non-ACGT context DNA");
        result += std::string_view("TGCA")[at];
    }
    return result;
}
bool Case::same_geometry(const Case &other) const {
    return std::tie(parent, contig, reverse, covered, ref_begin, ref_end, core_begin, core_end,
                    left, right, reference) ==
           std::tie(other.parent, other.contig, other.reverse, other.covered, other.ref_begin,
                    other.ref_end, other.core_begin, other.core_end, other.left, other.right,
                    other.reference);
}
std::string Case::physical_window() const {
    return sha256("sample-physical-window/1\t" + contig + '\t' + (reverse ? "-" : "+") + '\t' +
                  std::to_string(ref_begin) + '\t' + std::to_string(ref_end) + '\t' +
                  std::to_string(core_begin) + '\t' + std::to_string(core_end) + '\t' + left +
                  '\t' + right + '\n');
}
Read parse_read(const std::string &line) {
    const auto fields = split(line, '\t');
    require(fields.size() >= 11 && line.size() <= maximum_line, "Malformed/oversized SAM record");
    Read result;
    result.name = fields[0];
    require(read_name(result.name), "Invalid SAM read name");
    const auto flags = integer(fields[1]), quality = integer(fields[4]);
    require(flags <= 65535 && quality <= 255, "SAM flag/MAPQ exceeds bound");
    result.flags = static_cast<unsigned>(flags);
    result.mapq = static_cast<unsigned>(quality);
    result.contig = fields[2];
    result.sequence = fields[9];
    result.quality = fields[10];
    require(result.quality == "*" || result.quality.size() == result.sequence.size(),
            "SAM SEQ/Q lengths differ");
    if (result.quality != "*")
        for (const auto ch : result.quality)
            require(static_cast<unsigned char>(ch) >= 33U && static_cast<unsigned char>(ch) <= 126U,
                    "SAM quality outside printable Phred+33");
    std::set<std::string> seen;
    for (std::size_t i = 11; i < fields.size(); ++i) {
        if (fields[i].starts_with("RG:") || fields[i].starts_with("pi:") ||
            fields[i].starts_with("dx:")) {
            require(fields[i].size() >= 5 && fields[i][4] == ':' &&
                        seen.insert(fields[i].substr(0, 2)).second,
                    "Malformed/duplicate lineage SAM tag");
            if (fields[i].starts_with("RG:Z:"))
                result.group = fields[i].substr(5);
            else if (fields[i].starts_with("pi:Z:")) {
                require(read_name(std::string_view(fields[i]).substr(5)),
                        "Invalid supporting parent tag");
                result.parent = fields[i].substr(5);
            } else if (fields[i] == "dx:i:0")
                result.duplex = 0;
            else if (fields[i] == "dx:i:1")
                result.duplex = 1;
            else if (fields[i] == "dx:i:-1")
                result.duplex = -1;
            else
                throw std::runtime_error("Unsupported lineage SAM tag type/value");
        }
    }
    if ((result.flags & 4U) != 0 || fields[5] == "*")
        return result;
    const auto position = integer(fields[3]);
    require(position > 0 && result.sequence != "*",
            "Mapped supporting read lacks sequence/position");
    result.reference_begin = position - 1;
    std::uint64_t reference = result.reference_begin;
    std::size_t read{};
    std::uint64_t count{};
    bool digits{};
    for (const auto ch : fields[5]) {
        if (ch >= '0' && ch <= '9') {
            require(count <= 10000000, "CIGAR length exceeds bound");
            count = count * 10 + static_cast<unsigned>(ch - '0');
            digits = true;
            continue;
        }
        require(digits && count > 0 && count <= 10000000 &&
                    std::string_view("MIDNSHP=X").find(ch) != std::string_view::npos,
                "Invalid supporting CIGAR");
        const auto n = static_cast<std::size_t>(count);
        const auto consumes_read = std::string_view("MIS=X").find(ch) != std::string_view::npos;
        const auto consumes_reference =
            std::string_view("MDN=X").find(ch) != std::string_view::npos;
        require(!consumes_read ||
                    n <= result.sequence.size() - std::min(read, result.sequence.size()),
                "CIGAR consumes beyond SEQ");
        require(!consumes_reference ||
                    count <= std::numeric_limits<std::uint64_t>::max() - reference,
                "CIGAR reference overflow");
        const auto read_end = read + (consumes_read ? n : 0);
        const auto reference_end = reference + (consumes_reference ? count : 0);
        result.segments.push_back({ch, reference, reference_end, read, read_end});
        read = read_end;
        reference = reference_end;
        count = 0;
        digits = false;
    }
    require(!digits && read == result.sequence.size(), "CIGAR/SEQ length differs");
    result.reference_end = reference;
    return result;
}
Cuts unique_cuts(std::string_view query, std::string_view reference, std::size_t left,
                 std::size_t right) {
    require(0 < left && left < right && right < reference.size(), "Invalid reference core cuts");
    const auto m = query.size(), n = reference.size(), width = n + 1;
    if (m > 4096 || n > 4096 || (m + 1) > 2000000 / width)
        return {CutStatus::cell_bound, 0, 0};
    std::vector<int> forward((m + 1) * width), backward(forward.size());
    const auto at = [width](std::size_t i, std::size_t j) { return i * width + j; };
    for (std::size_t i = 0; i <= m; ++i)
        for (std::size_t j = 0; j <= n; ++j) {
            if (i == 0)
                forward[at(i, j)] = static_cast<int>(j);
            else if (j == 0)
                forward[at(i, j)] = static_cast<int>(i);
            else
                forward[at(i, j)] =
                    std::min({forward[at(i - 1, j)] + 1, forward[at(i, j - 1)] + 1,
                              forward[at(i - 1, j - 1)] +
                                  static_cast<int>(query[i - 1] != reference[j - 1])});
        }
    for (std::size_t i = m + 1; i-- > 0;)
        for (std::size_t j = n + 1; j-- > 0;) {
            if (i == m)
                backward[at(i, j)] = static_cast<int>(n - j);
            else if (j == n)
                backward[at(i, j)] = static_cast<int>(m - i);
            else
                backward[at(i, j)] = std::min(
                    {backward[at(i + 1, j)] + 1, backward[at(i, j + 1)] + 1,
                     backward[at(i + 1, j + 1)] + static_cast<int>(query[i] != reference[j])});
        }
    const auto best = forward[at(m, n)];
    std::set<std::size_t> starts, ends;
    for (std::size_t i = 0; i <= m; ++i) {
        if (forward[at(i, left - 1)] + 1 + backward[at(i, left)] == best)
            starts.insert(i);
        if (i > 0 && forward[at(i - 1, left - 1)] +
                             static_cast<int>(query[i - 1] != reference[left - 1]) +
                             backward[at(i, left)] ==
                         best)
            starts.insert(i);
        if (forward[at(i, right)] + 1 + backward[at(i, right + 1)] == best)
            ends.insert(i);
        if (i < m && forward[at(i, right)] + static_cast<int>(query[i] != reference[right]) +
                             backward[at(i + 1, right + 1)] ==
                         best)
            ends.insert(i);
    }
    if (starts.size() != 1 || ends.size() != 1 || *starts.begin() > *ends.begin())
        return {CutStatus::ambiguous, 0, 0};
    return {CutStatus::resolved, *starts.begin(), *ends.begin()};
}
Projection project(const Case &input, const Read &read) {
    if (input.reference.find_first_not_of("ACGT") != std::string::npos)
        return {"reference_ambiguous", ""};
    const auto low = input.reverse ? reverse_complement(input.right) : input.left;
    const auto high = input.reverse ? reverse_complement(input.left) : input.right;
    if (input.contig != read.contig || input.ref_begin < read.reference_begin ||
        input.ref_end > read.reference_end)
        return {"guard_not_covered", ""};
    for (const auto &segment : read.segments)
        if (segment.operation == 'N' && segment.reference_begin < input.ref_end &&
            input.ref_begin < segment.reference_end)
            return {"structural_skip", ""};
    const auto left = anchor(read, input.ref_begin, low),
               right = anchor(read, input.core_end, high);
    if (!left || !right || left->second > right->first)
        return {"guard_gapped_clipped_or_mismatched", ""};
    if (read.quality == "*" || read.quality.size() != read.sequence.size())
        return {"base_quality_unavailable", ""};
    for (std::size_t i = left->first; i < right->second; ++i)
        if (static_cast<unsigned char>(read.quality.at(i)) < 43U)
            return {"base_quality_below_10", ""};
    const auto view =
        std::string_view(read.sequence).substr(left->first, right->second - left->first);
    const auto cuts = unique_cuts(view, input.reference,
                                  static_cast<std::size_t>(input.core_begin - input.ref_begin),
                                  static_cast<std::size_t>(input.core_end - input.ref_begin));
    if (cuts.status == CutStatus::cell_bound)
        return {"projection_cell_bound", ""};
    if (cuts.status != CutStatus::resolved)
        return {"core_cut_ambiguous", ""};
    if (cuts.begin != left->second - left->first || cuts.end != right->first - left->first)
        return {"CIGAR_and_edit_core_cut_disagree", ""};
    auto sequence = read.sequence.substr(left->second, right->first - left->second);
    if (sequence.size() > 4096 || sequence.find_first_not_of("ACGT") != std::string::npos)
        return {"core_outside_DNA_bound", ""};
    if (input.reverse)
        sequence = reverse_complement(sequence);
    return {"resolved", std::move(sequence)};
}
Family family(const std::string &name, const std::map<std::string, Lineage> &all,
              const Packet &packet) {
    if (!eligible_lineage(packet.lineage))
        return {"producer_lineage_unqualified", "", {name}};
    std::set<std::string> seen;
    std::vector<std::string> ancestry;
    auto current = name;
    while (true) {
        if (!seen.insert(current).second || seen.size() > 64)
            return {"lineage_cycle_or_depth", "", ancestry};
        ancestry.push_back(current);
        if (packet.targets.contains(current) || packet.exclusions.contains(current))
            return {"target_family_excluded", "", ancestry};
        const auto found = all.find(current);
        if (found == all.end())
            return {"resolved", current, ancestry};
        const auto &node = found->second;
        if (node.conflicting || !packet.groups.contains(node.group))
            return {"lineage_conflict_or_foreign_RG", "", ancestry};
        if (!node.duplex || *node.duplex != 0)
            return {"duplex_complement_or_unknown", "", ancestry};
        if (!node.parent)
            return {"resolved", current, ancestry};
        current = *node.parent;
    }
}
Packet read_packet(const std::filesystem::path &path) {
    std::ifstream stream(path);
    require(stream.good(), "Cannot open sample cases");
    std::string line;
    require(static_cast<bool>(std::getline(stream, line)), "Empty sample cases");
    const auto header = split(line, '\t');
    require(header.size() == 8 && header[0] == "SCHEMA" && header[1] == "sample-context-cases/2" &&
                hex(header[2], 64) && (header[3] == "." || hex(header[3], 64)) &&
                hex(header[4], 64) && hex(header[5], 64),
            "Sample case header differs");
    Packet result;
    result.source_cases = header[2];
    result.lineage_contract = header[3];
    result.reference_proof = header[4];
    result.assembly_proof = header[5];
    require((header[6] == "strict" || header[6] == "exploratory_published_protocol") &&
                (header[7] == "unavailable" ||
                 (header[3] != "." && ((header[6] == "strict" && header[7] == "strict_qualified") ||
                                       (header[6] == "exploratory_published_protocol" &&
                                        header[7] == "assumption_qualified")))),
            "Context role/lineage mode differs");
    result.lineage = header[7] == "strict_qualified" ? LineageMode::strict_qualified
                     : header[7] == "assumption_qualified"
                         ? LineageMode::exploratory_published_protocol
                     : header[6] == "strict" ? LineageMode::unavailable_strict
                                             : LineageMode::unavailable_exploratory;
    std::set<std::string> ids;
    std::map<std::string, Case> geometries;
    while (std::getline(stream, line)) {
        const auto row = split(line, '\t');
        require(!row.empty() && line.size() <= maximum_line, "Invalid sample packet row");
        if (row[0] == "TARGET") {
            require(row.size() == 2 && !row[1].empty() && result.targets.insert(row[1]).second,
                    "Duplicate/malformed target family");
        } else if (row[0] == "EXCLUDE") {
            require(row.size() == 2 && !row[1].empty() && result.exclusions.insert(row[1]).second,
                    "Duplicate/malformed target ancestor exclusion");
        } else if (row[0] == "RG") {
            require(row.size() == 2 && result.groups.insert(row[1]).second,
                    "Duplicate/malformed input RG");
        } else if (row[0] == "SQ") {
            require(
                row.size() == 4 && hex(row[3], 32) &&
                    result.references.emplace(row[1], Reference{integer(row[2]), row[3]}).second,
                "Duplicate/malformed input reference");
        } else {
            require(row.size() == 15 && row[0] == "CASE" && ids.insert(row[1]).second &&
                        (row[4] == "+" || row[4] == "-") && hex(row[12], 64) &&
                        (row[14] == "covered" || row[14] == "needs_ranges"),
                    "Malformed/duplicate sample CASE");
            Case input{row[1],          row[2],          row[3],
                       row[12],         row[9],          row[10],
                       row[13],         row[4] == "-",   row[14] == "covered",
                       integer(row[5]), integer(row[6]), integer(row[7]),
                       integer(row[8])};
            require(integer(row[11]) == 10 && input.left.size() == 10 && input.right.size() == 20 &&
                        input.left.find_first_not_of("ACGT") == std::string::npos &&
                        input.right.find_first_not_of("ACGT") == std::string::npos &&
                        input.ref_begin < input.core_begin && input.core_begin < input.core_end &&
                        input.core_end < input.ref_end &&
                        input.core_begin - input.ref_begin == (input.reverse ? 20U : 10U) &&
                        input.ref_end - input.core_end == (input.reverse ? 10U : 20U) &&
                        input.reference.size() == input.ref_end - input.ref_begin &&
                        input.reference.find_first_not_of("ACGTN") == std::string::npos,
                    "Sample guard geometry differs");
            const auto [it, inserted] = geometries.emplace(input.geometry, input);
            require(inserted || it->second.same_geometry(input),
                    "Conflicting identical geometry digest");
            result.cases.push_back(std::move(input));
        }
    }
    require(!stream.bad() && !result.cases.empty() && result.cases.size() <= 1024 &&
                result.targets.size() == 64 && !result.groups.empty() && !result.references.empty(),
            "Incomplete sample packet census");
    for (const auto &input : result.cases)
        require(result.targets.contains(input.parent) && result.references.contains(input.contig) &&
                    input.ref_end <= result.references.at(input.contig).length,
                "Case outside bound parent/reference");
    return result;
}
std::string build(const Packet &packet, const std::filesystem::path &sam,
                  const std::filesystem::path &output) {
    const auto before = pin(sam);
    require(before.size <= 2ULL * 1024 * 1024 * 1024, "Supporting SAM exceeds 2 GiB source bound");
    std::ifstream first(sam);
    require(first.good(), "Cannot open supporting SAM");
    std::string line;
    Header header;
    std::map<std::string, Lineage> lineages;
    std::uint64_t records{};
    bool body{};
    while (std::getline(first, line)) {
        require(!line.empty() && line.size() <= maximum_line,
                "Blank/oversized supporting SAM line");
        if (line.front() == '@') {
            require(!body, "SAM header after body");
            header_line(header, line);
            continue;
        }
        body = true;
        const auto read = parse_read(line);
        lineage_add(lineages, read);
        require(++records <= 2000000, "Supporting record census exceeds bound");
    }
    require(!first.bad(), "Supporting SAM read failed");
    validate_header(header, packet);
    std::map<std::string, Case> physical;
    for (const auto &input : packet.cases) {
        const auto [it, inserted] = physical.emplace(input.physical_window(), input);
        require(inserted || (it->second.reference == input.reference &&
                             it->second.covered == input.covered),
                "Identical physical windows disagree on source reference/coverage");
    }
    std::map<std::string, Family> families;
    for (const auto &[name, node] : lineages) {
        static_cast<void>(node);
        families.emplace(name, family(name, lineages, packet));
    }
    const auto blocked = blocked_components(lineages, packet, families);
    for (auto &[name, value] : families) {
        if (eligible_lineage(packet.lineage) && blocked.contains(name))
            value.status = blocked.at(name);
    }
    std::ostringstream lineage_audit;
    lineage_audit << "read_id\tfamily_root\tstatus\tparent_id\tdx\tread_group\tknown_ancestry_"
                     "json\tobserved_parent_ids_json\tparent_absent_seen\n";
    for (const auto &[name, node] : lineages) {
        const auto &value = families.at(name);
        lineage_audit << name << '\t' << value.root << '\t' << value.status << '\t'
                      << node.parent.value_or(".") << '\t'
                      << (node.duplex ? std::to_string(*node.duplex) : ".") << '\t' << node.group
                      << '\t';
        lineage_audit << '[';
        bool comma{};
        for (const auto &ancestor : value.ancestry) {
            if (comma)
                lineage_audit << ',';
            lineage_audit << quote(ancestor);
            comma = true;
        }
        lineage_audit << "]\t[";
        comma = false;
        for (const auto &parent : node.observed_parents) {
            if (comma)
                lineage_audit << ',';
            lineage_audit << quote(parent);
            comma = true;
        }
        lineage_audit << "]\t" << (node.absent_parent_seen ? 1 : 0) << '\n';
    }
    std::map<std::pair<std::string, std::string>, Vote> votes;
    std::map<std::string, std::uint64_t> reasons;
    std::ostringstream observations;
    observations << "physical_window_sha256\tfamily_sha256\tread_id\tstatus\tsequence_sha256\n";
    std::ifstream second(sam);
    while (std::getline(second, line)) {
        if (line.front() == '@')
            continue;
        const auto read = parse_read(line);
        auto reason = eligibility(read);
        const auto &resolved = families.at(read.name);
        if (reason == "eligible" && resolved.status != "resolved")
            reason = resolved.status;
        if (reason != "eligible") {
            ++reasons[reason];
            continue;
        }
        const auto family_id = sha256(std::string(run) + '\n' + resolved.root + '\n');
        for (const auto &[geometry, input] : physical) {
            if (!input.covered || input.contig != read.contig ||
                read.reference_begin >= input.ref_end || input.ref_begin >= read.reference_end)
                continue;
            const auto projected = project(input, read);
            observations << geometry << '\t' << family_id << '\t' << read.name << '\t'
                         << projected.status << '\t'
                         << (projected.status == "resolved" ? sha256(projected.sequence) : ".")
                         << '\n';
            if (projected.status != "resolved") {
                ++reasons[projected.status];
                continue;
            }
            auto [it, inserted] =
                votes.try_emplace({geometry, resolved.root}, Vote{projected.sequence, false, {}});
            if (!inserted && it->second.sequence != projected.sequence)
                it->second.conflict = true;
            it->second.reads.insert(read.name);
        }
    }
    require(!second.bad() && pin(sam) == before, "Supporting SAM changed/read failed");
    std::map<std::string, std::map<std::string, std::set<std::string>>> paths;
    std::ostringstream provenance;
    provenance << "physical_window_sha256\tfamily_sha256\tfamily_root\tstatus\tsequence_"
                  "sha256\tread_ids_json\n";
    for (const auto &[key, vote] : votes) {
        const auto &[geometry, root] = key;
        const auto family_id = sha256(std::string(run) + '\n' + root + '\n');
        provenance << geometry << '\t' << family_id << '\t' << root << '\t'
                   << (vote.conflict ? "conflicting_family" : "resolved") << '\t'
                   << (vote.conflict ? "." : sha256(vote.sequence)) << '\t';
        provenance << '[';
        bool comma{};
        for (const auto &name : vote.reads) {
            if (comma)
                provenance << ',';
            provenance << quote(name);
            comma = true;
        }
        provenance << "]\n";
        if (vote.conflict)
            ++reasons["conflicting_family"];
        else
            paths[geometry][vote.sequence].insert(family_id);
    }
    std::ostringstream contexts, census;
    contexts << "case_id\tgeometry_sha256\tphysical_window_sha256\tsequence_"
                "sha256\tsequence\tfamily_count\tfamily_sha256s\tcontext_role\tassumption_"
                "tag\tstrict_read_level_qualified\tpromotion_eligible\n";
    census << "case_id\tgeometry_sha256\tphysical_window_"
              "sha256\tcoverage\tstatus\tpaths\tfamilies\tcontext_role\tassumption_tag\tstrict_"
              "read_level_qualified\n";
    std::uint64_t available{}, path_rows{};
    for (const auto &input : packet.cases) {
        const auto window = input.physical_window();
        const auto found = paths.find(window);
        const auto size = found == paths.end() ? 0 : found->second.size();
        const auto status = !input.covered                      ? "encoded_ranges_missing"
                            : !eligible_lineage(packet.lineage) ? "producer_lineage_unqualified"
                            : size == 0                         ? "no_resolved_support"
                            : exploratory(packet.lineage)       ? "exploratory_available"
                                                                : "available";
        std::size_t count{};
        if (found != paths.end())
            for (const auto &[sequence, ids] : found->second) {
                count += ids.size();
                contexts << input.id << '\t' << input.geometry << '\t' << window << '\t'
                         << sha256(sequence) << '\t' << sequence << '\t' << ids.size() << '\t';
                bool comma{};
                for (const auto &id : ids) {
                    if (comma)
                        contexts << ',';
                    contexts << id;
                    comma = true;
                }
                contexts << '\t' << context_role(packet.lineage) << '\t'
                         << assumption_tag(packet.lineage) << '\t'
                         << (packet.lineage == LineageMode::strict_qualified ? 1 : 0) << "\t0\n";
                ++path_rows;
            }
        census << input.id << '\t' << input.geometry << '\t' << window << '\t'
               << (input.covered ? "covered" : "needs_ranges") << '\t' << status << '\t' << size
               << '\t' << count << '\t' << context_role(packet.lineage) << '\t'
               << assumption_tag(packet.lineage) << '\t'
               << (packet.lineage == LineageMode::strict_qualified ? 1 : 0) << '\n';
        available +=
            static_cast<std::uint64_t>(std::string_view(status) == "available" ||
                                       std::string_view(status) == "exploratory_available");
    }
    fresh(output / "contexts.tsv", contexts.str());
    fresh(output / "cases.tsv", census.str());
    fresh(output / "families.tsv", provenance.str());
    fresh(output / "observations.tsv", observations.str());
    fresh(output / "lineage.tsv", lineage_audit.str());
    std::ostringstream excluded;
    excluded << "reason\tobservations\n";
    for (const auto &[name, count] : reasons)
        excluded << name << '\t' << count << '\n';
    fresh(output / "excluded.tsv", excluded.str());
    std::ostringstream result;
    result << "{\"schema\":\"sample-context-result/2\",\"cases\":" << packet.cases.size()
           << ",\"physical_windows\":" << physical.size() << ",\"available_cases\":" << available
           << ",\"path_rows\":" << path_rows << ",\"supporting_records\":" << records
           << ",\"supporting_names\":" << lineages.size()
           << ",\"source_cases_sha256\":" << quote(packet.source_cases)
           << ",\"lineage_contract_sha256\":" << quote(packet.lineage_contract)
           << ",\"reference_proof_sha256\":" << quote(packet.reference_proof)
           << ",\"assembly_proof_sha256\":" << quote(packet.assembly_proof)
           << ",\"context_role\":" << quote(context_role(packet.lineage))
           << ",\"assumption_tag\":" << quote(assumption_tag(packet.lineage))
           << ",\"strict_read_level_qualified\":"
           << (packet.lineage == LineageMode::strict_qualified ? "true" : "false")
           << ",\"consumer_ready\":"
           << (packet.lineage == LineageMode::strict_qualified ? "true" : "false")
           << ",\"exploratory_consumer_ready\":"
           << (packet.lineage == LineageMode::exploratory_published_protocol ? "true" : "false")
           << ",\"promotion_eligible\":false,\"biological_qualification\":false,\"independent_"
              "donor_confirmation\":false,\"probability_weights_emitted\":false,\"minimum_base_"
              "quality\":10,\"minimum_mapping_quality\":30,\"family_vote_policy\":\"one resolved "
              "family per physical window; conflicting DNA excluded\"}";
    return result.str();
}
}
