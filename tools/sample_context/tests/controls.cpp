#include "sample_context/context.h"
#include <algorithm>
#include <chrono>
#include <fstream>
#include <functional>
#include <limits>
#include <sstream>
#include <unistd.h>

namespace sample_context {
namespace {
struct Checks {
    std::size_t assertions{}, alignments{}, complete_deletions{}, deep_components{},
        conflicting_parents{};
    void expect(bool value, const std::string &message) {
        ++assertions;
        require(value, message);
    }
    template <class F> void rejects(F f, const std::string &message) {
        bool rejected{};
        try {
            f();
        } catch (const std::exception &) {
            rejected = true;
        }
        expect(rejected, message);
    }
};
const std::string run_id = "11d77535b149da7c6f7153939924a9fe29559cc7";
const std::string left = "ACGTACGTAC", right = "GATCGTACGATCGTAGCTAG", core = "TCGGA";
Case fixture(bool reverse = false) {
    Case value;
    value.id = "ordinary/fixture/ordinary";
    value.parent = "target0";
    value.contig = "chr1";
    value.geometry = std::string(64, 'a');
    value.left = left;
    value.right = right;
    value.reverse = reverse;
    value.covered = true;
    value.ref_begin = 100;
    const auto low = reverse ? reverse_complement(right) : left,
               high = reverse ? reverse_complement(left) : right;
    value.reference = low + (reverse ? reverse_complement(core) : core) + high;
    value.core_begin = value.ref_begin + low.size();
    value.core_end = value.core_begin + core.size();
    value.ref_end = value.ref_begin + value.reference.size();
    return value;
}
Case complete_deletion(bool reverse = false) {
    auto value = fixture(reverse);
    value.left = std::string(10, 'A');
    value.right = std::string(20, 'G');
    const auto low = reverse ? reverse_complement(value.right) : value.left,
               high = reverse ? reverse_complement(value.left) : value.right;
    value.reference = low + std::string(5, reverse ? 'G' : 'C') + high;
    value.core_begin = value.ref_begin + low.size();
    value.core_end = value.core_begin + 5;
    value.ref_end = value.ref_begin + value.reference.size();
    return value;
}
std::string sam(const std::string &name, const std::string &sequence, const std::string &cigar,
                const std::string &extra = "", unsigned flags = 0, std::uint64_t position = 101) {
    return name + '\t' + std::to_string(flags) + "\tchr1\t" + std::to_string(position) + "\t60\t" +
           cigar + "\t*\t0\t0\t" + sequence + '\t' + std::string(sequence.size(), 'I') +
           "\tRG:Z:group\tdx:i:0" + extra;
}
std::vector<std::string> binary_strings(std::size_t maximum) {
    std::vector<std::string> values{""}, level{""};
    for (std::size_t n = 0; n < maximum; ++n) {
        std::vector<std::string> next;
        for (const auto &s : level)
            for (const auto ch : std::string("AC"))
                next.push_back(s + ch);
        values.insert(values.end(), next.begin(), next.end());
        level = std::move(next);
    }
    return values;
}
Cuts enumerate(const std::string &query, const std::string &reference, std::size_t left_cut,
               std::size_t right_cut) {
    int best = std::numeric_limits<int>::max();
    std::set<std::size_t> starts, ends;
    std::function<void(std::size_t, std::size_t, int, std::optional<std::size_t>,
                       std::optional<std::size_t>)>
        visit;
    visit = [&](std::size_t i, std::size_t j, int cost, std::optional<std::size_t> begin,
                std::optional<std::size_t> end) {
        if (cost > best)
            return;
        if (i == query.size() && j == reference.size()) {
            require(begin && end, "Exhaustive cut missing");
            if (cost < best) {
                best = cost;
                starts.clear();
                ends.clear();
            }
            starts.insert(*begin);
            ends.insert(*end);
            return;
        }
        if (i < query.size() && j < reference.size())
            visit(i + 1, j + 1, cost + static_cast<int>(query[i] != reference[j]),
                  j + 1 == left_cut ? std::optional{i + 1} : begin,
                  j == right_cut ? std::optional{i} : end);
        if (j < reference.size())
            visit(i, j + 1, cost + 1, j + 1 == left_cut ? std::optional{i} : begin,
                  j == right_cut ? std::optional{i} : end);
        if (i < query.size())
            visit(i + 1, j, cost + 1, begin, end);
    };
    visit(0, 0, 0, std::nullopt, std::nullopt);
    if (starts.size() != 1 || ends.size() != 1 || *starts.begin() > *ends.begin())
        return {CutStatus::ambiguous, 0, 0};
    return {CutStatus::resolved, *starts.begin(), *ends.begin()};
}
void projection_controls(Checks &c) {
    for (const auto reverse : {false, true}) {
        const auto input = fixture(reverse);
        const auto low = reverse ? reverse_complement(right) : left;
        const auto high = reverse ? reverse_complement(left) : right;
        const auto center = reverse ? reverse_complement(core) : core;
        const auto flags = reverse ? 16U : 0U;
        auto record = parse_read(sam("read", low + center + high,
                                     std::to_string(input.reference.size()) + 'M', "", flags));
        c.expect(project(input, record).sequence == core,
                 "Both orientations preserve native molecule-forward DNA");
        auto changed = center;
        changed[2] = changed[2] == 'A' ? 'C' : 'A';
        record = parse_read(sam("read", low + changed + high,
                                std::to_string(input.reference.size()) + 'M', "", flags));
        c.expect(project(input, record).sequence ==
                     (reverse ? reverse_complement(changed) : changed),
                 "Both orientations project SNP");
        const auto inserted_low = std::string(1, low.back() == 'A' ? 'C' : 'A');
        record = parse_read(sam("read", low + inserted_low + center + high,
                                std::to_string(low.size()) + "M1I" +
                                    std::to_string(center.size() + high.size()) + 'M',
                                "", flags));
        const auto low_projection = project(input, record);
        c.expect(low_projection.status == "resolved" &&
                     low_projection.sequence == (reverse ? reverse_complement(inserted_low + center)
                                                         : inserted_low + center),
                 "Boundary insertion remains in core");
        const auto inserted_high = std::string(1, high.front() == 'T' ? 'G' : 'T');
        record = parse_read(sam("read", low + center + inserted_high + high,
                                std::to_string(low.size() + center.size()) + "M1I" +
                                    std::to_string(high.size()) + 'M',
                                "", flags));
        const auto high_projection = project(input, record);
        c.expect(
            high_projection.status == "resolved" &&
                high_projection.sequence ==
                    (reverse ? reverse_complement(center + inserted_high) : center + inserted_high),
            "Other boundary insertion remains in core");
        record = parse_read(sam("read", low + center.substr(1) + high,
                                std::to_string(low.size()) + "M1D" +
                                    std::to_string(center.size() - 1 + high.size()) + 'M',
                                "", flags));
        const auto deletion = project(input, record);
        c.expect(deletion.status == "resolved" &&
                     deletion.sequence ==
                         (reverse ? reverse_complement(center.substr(1)) : center.substr(1)),
                 "Boundary deletion preserves reference cut");
        record = parse_read(sam("read", low + center.substr(0, center.size() - 1) + high,
                                std::to_string(low.size() + center.size() - 1) + "M1D" +
                                    std::to_string(high.size()) + 'M',
                                "", flags));
        const auto other_deletion = project(input, record);
        c.expect(other_deletion.status == "resolved" &&
                     other_deletion.sequence ==
                         (reverse ? reverse_complement(center.substr(0, center.size() - 1))
                                  : center.substr(0, center.size() - 1)),
                 "Other boundary deletion preserves reference cut");
        const auto erased = complete_deletion(reverse);
        const auto deletion_low = reverse ? reverse_complement(erased.right) : erased.left;
        const auto deletion_high = reverse ? reverse_complement(erased.left) : erased.right;
        const auto complete_cuts = unique_cuts(deletion_low + deletion_high, erased.reference,
                                               deletion_low.size(), deletion_low.size() + 5);
        c.expect(complete_cuts.status == CutStatus::resolved &&
                     complete_cuts.begin == deletion_low.size() &&
                     complete_cuts.end == deletion_low.size(),
                 "Complete-core deletion has unique empty optimal-DAG cuts on both orientations");
        const auto empty =
            project(erased, parse_read(sam("read", deletion_low + deletion_high,
                                           std::to_string(deletion_low.size()) + "M5D" +
                                               std::to_string(deletion_high.size()) + 'M',
                                           "", flags)));
        c.expect(empty.status == "resolved" && empty.sequence.empty(),
                 "Complete-core deletion projects resolved empty DNA on both orientations");
        ++c.complete_deletions;
    }
    auto input = fixture();
    auto record = parse_read(sam("read", input.reference, "35M"));
    record.quality[11] = '!';
    c.expect(project(input, record).status == "base_quality_below_10",
             "Low Q contributes no context");
    record.quality = "*";
    c.expect(project(input, record).status == "base_quality_unavailable",
             "Unavailable Q contributes no context");
    record = parse_read(sam("read", input.reference, "5S30M", "", 0, 106));
    c.expect(project(input, record).status == "guard_not_covered", "Clipped guard unavailable");
    record =
        parse_read(sam("read", left.substr(0, 5) + "T" + left.substr(5) + core + right, "5M1I30M"));
    c.expect(project(input, record).status == "guard_gapped_clipped_or_mismatched",
             "Gapped guard unavailable");
    record = parse_read(sam("read", left + core.substr(1) + right, "10M1N24M"));
    c.expect(project(input, record).status == "structural_skip",
             "N cannot masquerade as DNA deletion");
    record = parse_read(sam("read", input.reference, "35M"));
    input.reference[0] = 'C';
    c.expect(project(input, record).sequence == core,
             "Conserved native guards need not copy the stock reference allele");
    input.reference[0] = 'N';
    c.expect(project(input, record).status == "reference_ambiguous",
             "Unknown reference DNA is an explicit unavailable projection");
    input.left = std::string(10, 'A');
    input.right = std::string(20, 'A');
    input.reference = std::string(32, 'A');
    input.core_begin = 110;
    input.core_end = 112;
    input.ref_end = 132;
    record = parse_read(sam("read", std::string(33, 'A'), "10M1I22M"));
    c.expect(project(input, record).status == "core_cut_ambiguous",
             "Single CIGAR cannot hide repeat-boundary ambiguity");
    c.expect(unique_cuts(std::string(4096, 'A'), std::string(4096, 'A'), 1, 2).status ==
                 CutStatus::cell_bound,
             "Oversized alignment is explicit resource exclusion");
    for (const auto &reference : binary_strings(5))
        if (reference.size() >= 3)
            for (const auto &query : binary_strings(5)) {
                const auto actual = unique_cuts(query, reference, 1, reference.size() - 1),
                           expected = enumerate(query, reference, 1, reference.size() - 1);
                ++c.alignments;
                c.expect(actual.status == expected.status &&
                             (actual.status != CutStatus::resolved ||
                              (actual.begin == expected.begin && actual.end == expected.end)),
                         "Every optimal cut matches independent path enumeration");
            }
}
Packet packet() {
    Packet p;
    p.lineage = LineageMode::strict_qualified;
    p.groups = {"group"};
    p.references = {{"chr1", {10000, std::string(32, 'b')}}};
    for (unsigned i = 0; i < 64; ++i)
        p.targets.insert("target" + std::to_string(i));
    p.cases = {fixture()};
    return p;
}
void lineage_controls(Checks &c) {
    auto p = packet();
    std::map<std::string, Lineage> all{{"root", {std::nullopt, 0, "group", false}},
                                       {"child", {std::string("root"), 0, "group", false}}};
    c.expect(family("child", all, p).root == "root", "Split child collapses to physical root");
    all["child"].parent = "target0";
    c.expect(family("child", all, p).status == "target_family_excluded",
             "Target ancestor excluded");
    all["child"].parent = "child";
    c.expect(family("child", all, p).status == "lineage_cycle_or_depth", "Lineage cycle excluded");
    all["child"].parent = "root";
    all["root"].duplex = 1;
    c.expect(family("child", all, p).status == "duplex_complement_or_unknown",
             "Duplex ancestor excluded");
    all["root"].duplex = -1;
    c.expect(family("child", all, p).status == "duplex_complement_or_unknown",
             "Complement ancestor excluded");
    all["root"].duplex.reset();
    c.expect(family("child", all, p).status == "duplex_complement_or_unknown",
             "Unknown dx excluded");
    all["root"].duplex = 0;
    all["root"].group = "foreign";
    c.expect(family("child", all, p).status == "lineage_conflict_or_foreign_RG",
             "Foreign RG excluded");
    all["root"].group = "group";
    all["root"].conflicting = true;
    c.expect(family("child", all, p).status == "lineage_conflict_or_foreign_RG",
             "Conflicting lineage excluded");
    all["root"].conflicting = false;
    all["root"].group = "";
    c.expect(family("child", all, p).status == "lineage_conflict_or_foreign_RG",
             "Missing RG excluded");
    all["root"].group = "group";
    p.exclusions.insert("root");
    c.expect(family("child", all, p).status == "target_family_excluded",
             "Known target ancestor closure excluded");
    p.lineage = LineageMode::unavailable_strict;
    c.expect(family("child", all, p).status == "producer_lineage_unqualified",
             "Unqualified producer semantics give no eligible context");
    c.rejects(
        [&] { static_cast<void>(parse_read(sam("r", left + core + right, "35M", "\tdx:i:1"))); },
        "Duplicate dx rejected");
    c.rejects([&] { static_cast<void>(parse_read(sam("r", left + core + right, "34M"))); },
              "CIGAR/sequence mismatch rejected");
}
std::string read_file(const std::filesystem::path &path) {
    std::ifstream stream(path);
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}
void full_controls(Checks &c) {
    const auto root = std::filesystem::temp_directory_path() /
                      ("sample-context-" + std::to_string(::getpid()) + '-' +
                       std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    require(std::filesystem::create_directory(root), "Control temporary directory collision");
    struct Cleanup {
        std::filesystem::path path;
        ~Cleanup() {
            std::error_code error;
            std::filesystem::remove_all(path, error);
        }
    } cleanup{root};
    const auto header = "@HD\tVN:1.6\n@SQ\tSN:chr1\tLN:10000\tM5:" + std::string(32, 'b') +
                        "\n@RG\tID:group\tSM:hg002\tPU:PAW71238\tDS:runid=" + run_id + "\n";
    const auto common = sam("root", left + core + right, "35M"),
               child = sam("child", left + core + right, "35M", "\tpi:Z:root"),
               rare = sam("rare", left + "TCTGA" + right, "35M");
    auto p = packet();
    std::ostringstream wire;
    wire << "SCHEMA\tsample-context-cases/2\t" << std::string(64, 'a') << '\t'
         << std::string(64, 'b') << '\t' << std::string(64, 'c') << '\t' << std::string(64, 'd')
         << "\tstrict\tstrict_qualified\n";
    for (const auto &name : p.targets)
        wire << "TARGET\t" << name << '\n';
    wire << "RG\tgroup\nSQ\tchr1\t10000\t" << std::string(32, 'b')
         << "\nCASE\tordinary/fixture/ordinary\ttarget0\tchr1\t+\t100\t135\t110\t115\t" << left
         << '\t' << right << "\t10\t" << std::string(64, 'a') << '\t' << left + core + right
         << "\tcovered\n";
    fresh(root / "cases.tsv", wire.str());
    const auto parsed = read_packet(root / "cases.tsv");
    c.expect(parsed.cases.size() == 1 && parsed.targets.size() == 64 &&
                 parsed.lineage == LineageMode::strict_qualified,
             "Prepared wire preserves geometry and target64 exclusion census");
    for (const auto order : {false, true}) {
        const auto directory = root / (order ? "reordered" : "original");
        std::filesystem::create_directory(directory);
        const auto input = directory / "input.sam";
        fresh(input, header + (order ? rare + '\n' + child + '\n' + common + '\n' + common + '\n'
                                     : common + '\n' + common + '\n' + child + '\n' + rare + '\n'));
        const auto result = build(p, input, directory);
        c.expect(result.find("\"available_cases\":1") != std::string::npos,
                 "Genuine core path produces context");
        const auto rows = split(read_file(directory / "contexts.tsv"), '\n');
        c.expect(rows.size() == 4, "One common and one single-family allele retained");
        for (std::size_t i = 1; i + 1 < rows.size(); ++i)
            c.expect(split(rows[i], '\t').at(5) == "1",
                     "Duplicate and split records remain one family vote");
    }
    c.expect(read_file(root / "original/contexts.tsv") ==
                 read_file(root / "reordered/contexts.tsv"),
             "Context invariant to read permutation");
    const auto duplicate = root / "duplicate-geometry";
    std::filesystem::create_directory(duplicate);
    fresh(duplicate / "input.sam", header + common + '\n');
    auto repeated = p;
    auto other = fixture();
    other.id = "private/fixture/withheld";
    other.parent = "target1";
    other.geometry = std::string(64, 'c');
    repeated.cases.push_back(other);
    c.expect(build(repeated, duplicate / "input.sam", duplicate).find("\"physical_windows\":1") !=
                 std::string::npos,
             "Identical physical windows deduplicate across distinct source geometry identities");
    const auto conflict = root / "conflict";
    std::filesystem::create_directory(conflict);
    fresh(conflict / "input.sam", header + common + '\n' +
                                      sam("child", left + "TCTGA" + right, "35M", "\tpi:Z:root") +
                                      '\n');
    c.expect(build(p, conflict / "input.sam", conflict).find("\"available_cases\":0") !=
                 std::string::npos,
             "Conflicting split calls contribute no family");
    const auto foreign = root / "foreign";
    std::filesystem::create_directory(foreign);
    auto wrong = header;
    wrong.replace(wrong.find("PAW71238"), 8, "PAW70337");
    fresh(foreign / "input.sam", wrong + common + '\n');
    c.rejects([&] { static_cast<void>(build(p, foreign / "input.sam", foreign)); },
              "Wrong supporting flowcell rejected");
    const auto no_group = root / "missing-group";
    std::filesystem::create_directory(no_group);
    auto ungrouped = common;
    ungrouped.erase(ungrouped.find("RG:Z:group\t"), 11);
    fresh(no_group / "input.sam", header + ungrouped + '\n');
    c.expect(build(p, no_group / "input.sam", no_group).find("\"available_cases\":0") !=
                 std::string::npos,
             "Record missing RG supplies no context");
    const auto complement = root / "complement";
    std::filesystem::create_directory(complement);
    auto marked = child;
    marked.replace(marked.find("dx:i:0"), 6, "dx:i:-1");
    fresh(complement / "input.sam", header + common + '\n' + marked + '\n');
    c.expect(build(p, complement / "input.sam", complement).find("\"available_cases\":0") !=
                 std::string::npos,
             "Known complement invalidates the entire connected family");
    const auto target = root / "target";
    std::filesystem::create_directory(target);
    fresh(target / "input.sam", header + common + '\n' +
                                    sam("target0", left + core + right, "35M", "\tpi:Z:root") +
                                    '\n');
    c.expect(build(p, target / "input.sam", target).find("\"available_cases\":0") !=
                 std::string::npos,
             "Known target child invalidates a shared parent and siblings");
    for (const auto mode :
         {LineageMode::strict_qualified, LineageMode::exploratory_published_protocol}) {
        const auto suffix = mode == LineageMode::strict_qualified ? "strict" : "exploratory";
        auto bounded = p;
        bounded.lineage = mode;
        const auto deep = root / (std::string("deep-component-") + suffix);
        std::filesystem::create_directory(deep);
        std::string chain = header;
        for (unsigned i = 0; i <= 65; ++i)
            chain += sam("chain" + std::to_string(i), left + core + right, "35M",
                         i == 0 ? "" : "\tpi:Z:chain" + std::to_string(i - 1)) +
                     '\n';
        fresh(deep / "input.sam", chain);
        const auto deep_result = build(bounded, deep / "input.sam", deep);
        c.expect(deep_result.find("\"available_cases\":0") != std::string::npos &&
                     split(read_file(deep / "contexts.tsv"), '\n').size() == 2 &&
                     split(read_file(deep / "families.tsv"), '\n').size() == 2,
                 "A depth-invalid descendant blocks every ancestor vote in the connected family");
        const auto audit = split(read_file(deep / "lineage.tsv"), '\n');
        c.expect(audit.size() == 68 && std::all_of(audit.begin() + 1, audit.end() - 1,
                                                   [](const auto &line) {
                                                       return split(line, '\t').at(2) ==
                                                              "lineage_cycle_or_depth";
                                                   }),
                 "Every member of the 66-read component records the same depth exclusion");
        ++c.deep_components;
        const std::vector<std::string> parent_records{
            sam("root-a", left + core + right, "35M"),
            sam("root-b", left + core + right, "35M"),
            sam("sibling-a", left + core + right, "35M", "\tpi:Z:root-a"),
            sam("sibling-b", left + core + right, "35M", "\tpi:Z:root-b"),
            sam("disputed", left + core + right, "35M", "\tpi:Z:root-a"),
            sam("disputed", left + core + right, "35M", "\tpi:Z:root-b")};
        std::string first_contexts, first_lineage;
        for (const auto reversed : {false, true}) {
            const auto disputed = root / (std::string("conflicting-parents-") + suffix +
                                          (reversed ? "-reversed" : "-forward"));
            std::filesystem::create_directory(disputed);
            auto ordered = parent_records;
            if (reversed)
                std::reverse(ordered.begin(), ordered.end());
            std::string input = header;
            for (const auto &line : ordered)
                input += line + '\n';
            fresh(disputed / "input.sam", input);
            const auto parent_result = build(bounded, disputed / "input.sam", disputed),
                       contexts = read_file(disputed / "contexts.tsv"),
                       lineage = read_file(disputed / "lineage.tsv");
            c.expect(parent_result.find("\"available_cases\":0") != std::string::npos &&
                         split(contexts, '\n').size() == 2 &&
                         split(read_file(disputed / "families.tsv"), '\n').size() == 2,
                     "Both conflicting pi roots and their siblings contribute zero votes");
            const auto parent_audit = split(lineage, '\n');
            c.expect(parent_audit.size() == 7 &&
                         std::all_of(parent_audit.begin() + 1, parent_audit.end() - 1,
                                     [](const auto &line) {
                                         return split(line, '\t').at(2) ==
                                                "lineage_conflict_or_foreign_RG";
                                     }),
                     "All five connected read names record the conflicting-parent exclusion");
            const auto edge = std::find_if(
                parent_audit.begin() + 1, parent_audit.end() - 1,
                [](const auto &line) { return split(line, '\t').front() == "disputed"; });
            c.expect(edge != parent_audit.end() - 1, "Conflicting read retains an edge audit row");
            const auto evidence = split(*edge, '\t');
            c.expect(evidence.at(3) == "." && evidence.at(6) == "[\"disputed\"]" &&
                         evidence.at(7) == "[\"root-a\",\"root-b\"]" && evidence.at(8) == "0",
                     "All observed pi edges survive without an invented single conflict ancestry");
            if (reversed)
                c.expect(contexts == first_contexts && lineage == first_lineage,
                         "Conflicting-parent path and edge evidence are invariant to source order");
            else {
                first_contexts = contexts;
                first_lineage = lineage;
            }
            ++c.conflicting_parents;
        }
        const auto erased = root / (std::string("complete-deletion-") + suffix);
        std::filesystem::create_directory(erased);
        bounded.cases = {complete_deletion()};
        fresh(erased / "input.sam",
              header + sam("erased", std::string(10, 'A') + std::string(20, 'G'), "10M5D20M") +
                  '\n');
        c.expect(build(bounded, erased / "input.sam", erased).find("\"available_cases\":1") !=
                     std::string::npos,
                 "Complete-core deletion remains an available context in both declared roles");
        const auto deleted_rows = split(read_file(erased / "contexts.tsv"), '\n');
        c.expect(deleted_rows.size() == 3, "Complete-core deletion emits one DNA path row");
        const auto deleted_fields = split(deleted_rows.at(1), '\t');
        c.expect(deleted_fields.at(3) == sha256("") && deleted_fields.at(4).empty() &&
                     deleted_fields.at(5) == "1",
                 "Resolved empty DNA is retained with one family rather than treated as missing");
        ++c.complete_deletions;
    }
    const auto unavailable = root / "unqualified";
    std::filesystem::create_directory(unavailable);
    fresh(unavailable / "input.sam", header + common + '\n');
    p.lineage = LineageMode::unavailable_strict;
    c.expect(build(p, unavailable / "input.sam", unavailable).find("\"available_cases\":0") !=
                 std::string::npos,
             "Unknown lineage cannot create a usable prior");
    const auto exploratory_root = root / "exploratory";
    std::filesystem::create_directory(exploratory_root);
    fresh(exploratory_root / "input.sam", header + common + '\n');
    p.lineage = LineageMode::exploratory_published_protocol;
    const auto assumption_result = build(p, exploratory_root / "input.sam", exploratory_root);
    c.expect(assumption_result.find("\"available_cases\":1") != std::string::npos &&
                 assumption_result.find("\"strict_read_level_qualified\":false") !=
                     std::string::npos &&
                 assumption_result.find("\"consumer_ready\":false") != std::string::npos,
             "Exploratory root rule emits separately tagged paths without strict qualification");
    c.expect(read_file(exploratory_root / "contexts.tsv")
                     .find("exploratory_published_protocol\tpublished_protocol_pi_dx_preservation_"
                           "v1\t0\t0") != std::string::npos,
             "Every exploratory path has explicit assumption and no promotion eligibility");
    const auto missing_dx = root / "exploratory-missing-dx";
    std::filesystem::create_directory(missing_dx);
    auto unknown = common;
    unknown.erase(unknown.find("\tdx:i:0"), 7);
    fresh(missing_dx / "input.sam", header + unknown + '\n');
    c.expect(build(p, missing_dx / "input.sam", missing_dx).find("\"available_cases\":0") !=
                 std::string::npos,
             "Exploratory assumptions never rescue missing dx");
    const auto uncovered = root / "missing-ranges";
    std::filesystem::create_directory(uncovered);
    fresh(uncovered / "input.sam", header + common + '\n');
    p.lineage = LineageMode::strict_qualified;
    p.cases[0].covered = false;
    static_cast<void>(build(p, uncovered / "input.sam", uncovered));
    c.expect(read_file(uncovered / "cases.tsv").find("encoded_ranges_missing") != std::string::npos,
             "Missing encoded ranges remain in the complete case census");
}
}
std::string controls() {
    Checks checks;
    projection_controls(checks);
    lineage_controls(checks);
    full_controls(checks);
    return "{\"schema\":\"sample-context-controls/1\",\"synthetic_only\":true,\"assertions\":" +
           std::to_string(checks.assertions) +
           ",\"independently_enumerated_alignments\":" + std::to_string(checks.alignments) +
           ",\"complete_core_deletion_cases\":" + std::to_string(checks.complete_deletions) +
           ",\"deep_lineage_component_cases\":" + std::to_string(checks.deep_components) +
           ",\"conflicting_parent_order_cases\":" + std::to_string(checks.conflicting_parents) +
           ",\"biological_qualification\":false}";
}
}
