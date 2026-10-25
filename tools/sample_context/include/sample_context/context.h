#pragma once
#include <cstdint>
#include <filesystem>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace sample_context {
struct Pin {
    std::string path, sha256;
    std::uintmax_t size{};
    bool operator==(const Pin &) const = default;
};
struct Reference {
    std::uint64_t length{};
    std::string md5;
};
struct Case {
    std::string id, parent, contig, geometry, left, right, reference;
    bool reverse{}, covered{};
    std::uint64_t ref_begin{}, ref_end{}, core_begin{}, core_end{};
    bool same_geometry(const Case &) const;
    std::string physical_window() const;
};
enum class LineageMode {
    unavailable_strict,
    unavailable_exploratory,
    strict_qualified,
    exploratory_published_protocol
};
struct Packet {
    std::string source_cases, lineage_contract, reference_proof, assembly_proof;
    LineageMode lineage{LineageMode::unavailable_strict};
    std::set<std::string> targets, exclusions, groups;
    std::map<std::string, Reference> references;
    std::vector<Case> cases;
};
struct Segment {
    char operation{};
    std::uint64_t reference_begin{}, reference_end{};
    std::size_t read_begin{}, read_end{};
};
struct Read {
    std::string name, contig, sequence, quality, group;
    std::optional<std::string> parent;
    std::optional<int> duplex;
    unsigned flags{}, mapq{};
    std::uint64_t reference_begin{}, reference_end{};
    std::vector<Segment> segments;
};
struct Projection {
    std::string status, sequence;
};
enum class CutStatus { resolved, ambiguous, cell_bound };
struct Cuts {
    CutStatus status{};
    std::size_t begin{}, end{};
};
struct Family {
    std::string status, root;
    std::vector<std::string> ancestry;
};
struct Lineage {
    std::optional<std::string> parent;
    std::optional<int> duplex;
    std::string group;
    bool conflicting{};
    std::set<std::string> observed_parents{};
    bool absent_parent_seen{};
};
void require(bool, const std::string &);
std::vector<std::string> split(std::string_view, char);
std::uint64_t integer(std::string_view);
std::string reverse_complement(std::string_view);
Read parse_read(const std::string &);
Projection project(const Case &, const Read &);
Cuts unique_cuts(std::string_view, std::string_view, std::size_t, std::size_t);
Family family(const std::string &, const std::map<std::string, Lineage> &, const Packet &);
Packet read_packet(const std::filesystem::path &);
std::string build(const Packet &, const std::filesystem::path &, const std::filesystem::path &);
std::string controls();
Pin pin(const std::filesystem::path &);
void check(const Pin &);
std::string quote(std::string_view);
std::string pin_json(const Pin &);
std::string sha256(std::string_view);
void fresh(const std::filesystem::path &, std::string_view);
std::string utc();
std::string source_json();
void verify_sources();
}
