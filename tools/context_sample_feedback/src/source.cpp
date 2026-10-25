#include "context_sample_feedback/sample.h"
#include <algorithm>
#include <bit>
#include <fstream>
#include <sstream>

namespace context_sample_feedback {
namespace {
using context_study::require;
std::vector<std::string> split(const std::string &line, char delimiter) {
    std::vector<std::string> result;
    std::size_t begin{};
    while (true) {
        const auto end = line.find(delimiter, begin);
        result.push_back(line.substr(begin, end == std::string::npos ? end : end - begin));
        if (end == std::string::npos)
            return result;
        begin = end + 1;
    }
}
std::string canonical_pin(const context_decoder::Fields &fields, const std::string &prefix) {
    return "{\"path\":" + context_study::json_string(fields.at(prefix + "_path")) +
           ",\"sha256\":" + context_study::json_string(fields.at(prefix + "_sha256")) +
           ",\"size\":" + std::to_string(context_study::natural(fields.at(prefix + "_size"))) + "}";
}
}
Table read_table(const std::filesystem::path &path, const std::string &hash,
                 const std::set<std::string> &expected) {
    require(path.is_absolute() && std::filesystem::file_size(path) <= 8 * 1024 * 1024 &&
                context_study::digest(hash) && context_study::file_sha256(path) == hash,
            "source table pin/size differs");
    std::ifstream input(path);
    std::string line;
    require(static_cast<bool>(std::getline(input, line)), "source table header absent");
    const auto names = split(line, '\t');
    require(std::set<std::string>(names.begin(), names.end()) == expected &&
                names.size() == expected.size(),
            "source table exact header differs");
    Table result;
    while (std::getline(input, line)) {
        require(line.size() <= 1024 * 1024 && line.find('\r') == std::string::npos,
                "source table line invalid");
        const auto values = split(line, '\t');
        require(values.size() == names.size(), "source table field count differs");
        std::map<std::string, std::string> row;
        for (std::size_t i = 0; i < names.size(); ++i)
            row.emplace(names[i], values[i]);
        require(result.size() < 65536, "source table row cap exceeded");
        result.push_back(std::move(row));
    }
    require(input.eof() && context_study::file_sha256(path) == hash,
            "source table changed during read");
    return result;
}
std::string physical_window(const context_study::CandidateCase &input) {
    return context_study::sha256(
        "sample-physical-window/1\t" + input.contig + '\t' + (input.reverse ? "-" : "+") + '\t' +
        std::to_string(input.reference.begin) + '\t' + std::to_string(input.reference.end) + '\t' +
        std::to_string(input.core.begin) + '\t' + std::to_string(input.core.end) + '\t' +
        input.left + '\t' + input.right + '\n');
}
std::map<std::string, Source>
read_sources(const std::filesystem::path &cases, const std::string &cases_hash,
             const std::filesystem::path &contexts, const std::string &contexts_hash,
             const context_study::Packet &packet, bool allow_exploratory) {
    require(allow_exploratory, "explicit --allow-exploratory 1 required");
    const auto census = read_table(cases, cases_hash,
                                   {"case_id", "geometry_sha256", "physical_window_sha256",
                                    "coverage", "status", "paths", "families", "context_role",
                                    "assumption_tag", "strict_read_level_qualified"});
    const auto paths =
        read_table(contexts, contexts_hash,
                   {"case_id", "geometry_sha256", "physical_window_sha256", "sequence_sha256",
                    "sequence", "family_count", "family_sha256s", "context_role", "assumption_tag",
                    "strict_read_level_qualified", "promotion_eligible"});
    std::map<std::string, const context_study::CandidateCase *> originals;
    for (const auto &input : packet.cases)
        originals.emplace(input.id, &input);
    std::map<std::string, Source> result;
    std::map<std::string, std::pair<std::size_t, std::size_t>> expected_counts, observed_counts;
    auto role = [](const auto &row) {
        require(row.at("context_role") == "exploratory_published_protocol" &&
                    row.at("assumption_tag") == "published_protocol_pi_dx_preservation_v1" &&
                    row.at("strict_read_level_qualified") == "0",
                "source role/assumption/strict flag differs");
    };
    for (const auto &row : census) {
        role(row);
        const auto &id = row.at("case_id");
        require(originals.contains(id) && !result.contains(id), "source case duplicate/foreign");
        const auto &input = *originals.at(id);
        require(row.at("geometry_sha256") == input.geometry &&
                    row.at("physical_window_sha256") == physical_window(input),
                "source geometry/physical-window mismatch");
        require(row.at("coverage") == "covered" && (row.at("status") == "exploratory_available" ||
                                                    row.at("status") == "no_resolved_support"),
                "unsupported source coverage/status");
        const auto count = context_study::natural(row.at("paths"));
        require((row.at("status") == "exploratory_available") == (count != 0),
                "source availability/path count differs");
        result.emplace(id, Source{id,
                                  input.geometry,
                                  physical_window(input),
                                  row.at("assumption_tag"),
                                  SourceRole::exploratory,
                                  count == 0 ? SourceState::missing : SourceState::available,
                                  {}});
        expected_counts[id] = {count, context_study::natural(row.at("families"))};
    }
    require(result.size() == originals.size(), "source availability case census incomplete");
    std::set<std::pair<std::string, std::string>> unique;
    for (const auto &row : paths) {
        role(row);
        const auto &id = row.at("case_id");
        require(result.contains(id) && row.at("promotion_eligible") == "0",
                "source path case/promotion differs");
        auto &source = result.at(id);
        require(row.at("geometry_sha256") == source.geometry &&
                    row.at("physical_window_sha256") == source.physical_window &&
                    source.state == SourceState::available,
                "source path availability/geometry differs");
        const auto &sequence = row.at("sequence");
        require(context_study::dna(sequence) &&
                    context_study::sha256(sequence) == row.at("sequence_sha256"),
                "source DNA digest differs");
        const auto families = split(row.at("family_sha256s"), ',');
        const auto count = context_study::natural(row.at("family_count"));
        require(count > 0 && count == families.size() &&
                    std::set<std::string>(families.begin(), families.end()).size() == count &&
                    std::all_of(families.begin(), families.end(), context_study::digest),
                "source family census differs");
        ++observed_counts[id].first;
        observed_counts[id].second += count;
        unique.emplace(id, sequence);
        source.paths.push_back(sequence);
    }
    for (auto &[id, source] : result) {
        require(expected_counts.at(id) == observed_counts[id], "source CASE/CTX counts differ");
        source = canonical_source(std::move(source));
    }
    return result;
}
void bind_frame(const context_study::CandidateCase &input,
                const context_decoder::GuardedBoundFrame &bound) {
    const auto &f = bound.binding;
    const auto &b = bound.base.binding;
    require(bound.scalar_comparisons > 0, "mandatory genuine Rust scalar comparisons absent");
    const auto parts = split(input.id, '/');
    require(parts.size() == 3 && b.at("query_index") == parts[1] &&
                ((input.domain == "ordinary" && parts[0] == "ordinary" && parts[2] == "ordinary") ||
                 (input.domain == "private-ordinary" && parts[0] == "private" &&
                  parts[2] == "ordinary") ||
                 (input.domain == "private-withheld" && parts[0] == "private" &&
                  parts[2] == "withheld")),
            "frame case/domain/query identity differs");
    require(b.at("parent") == input.parent && b.at("contig") == input.contig &&
                (b.at("reverse") == "1") == input.reverse &&
                f.at("native_center") == input.native && f.at("left_guard") == input.left &&
                f.at("right_guard") == input.right &&
                context_study::natural(f.at("read_start")) == input.read.begin &&
                context_study::natural(f.at("read_end")) == input.read.end &&
                context_study::natural(f.at("owned_start")) == input.owned.begin &&
                context_study::natural(f.at("owned_end")) == input.owned.end &&
                context_study::natural(f.at("future_bases")) == input.future,
            "frame native geometry differs");
    const auto ancestry =
        "{\"chunk_index\":" + std::to_string(context_study::natural(b.at("chunk_index"))) +
        ",\"expanded_t_end\":" + std::to_string(context_study::natural(f.at("expanded_t_end"))) +
        ",\"expanded_t_start\":" +
        std::to_string(context_study::natural(f.at("expanded_t_start"))) +
        ",\"initial_context\":" + context_study::json_string(b.at("initial_context")) +
        ",\"initial_state\":" + std::to_string(context_study::natural(b.at("initial_state"))) +
        ",\"parent_pin\":" + canonical_pin(f, "parent") +
        ",\"tensor_pin\":" + canonical_pin(b, "tensor") + "}";
    require(context_study::sha256(ancestry) == input.ancestry, "frame native ancestry differs");
    require(bound.window.scores.initial_state == context_study::natural(b.at("initial_state")) &&
                context_study::digest(b.at("plan_sha256")) &&
                context_study::digest(b.at("location_receipt_sha256")) &&
                context_study::digest(b.at("location_sam_sha256")),
            "frame initial state/location receipt differs");
    require(bound.window.center_context.sequences == input.paths,
            "original population paths differ");
}
void write_trace(const std::filesystem::path &path, const context_decoder::GuardedSearch &search) {
    std::string bytes = "sample-guarded-exact-trace/1\n";
    auto integer = [&](std::uint64_t value) {
        for (unsigned shift = 0; shift < 64; shift += 8)
            bytes.push_back(static_cast<char>((value >> shift) & 255U));
    };
    auto real = [&](double value) { integer(std::bit_cast<std::uint64_t>(value)); };
    auto vector = [&](const std::vector<double> &values) {
        integer(values.size());
        for (const auto value : values)
            real(value);
    };
    integer(search.pruned);
    integer(search.center_bound_reached);
    integer(search.trace.size());
    for (const auto &step : search.trace) {
        integer(step.timestep);
        integer(step.generated);
        integer(step.merged);
        integer(step.pruned);
        vector(step.left_mass);
        integer(step.retained.size());
        for (const auto &item : step.retained) {
            integer(item.center.size());
            bytes += item.center;
            real(item.open_mass);
            vector(item.suffix_mass);
            real(item.partial_potential);
            real(item.terminal_potential);
            real(item.rank);
        }
    }
    integer(search.finalists.size());
    for (const auto &item : search.finalists) {
        integer(item.sequence.size());
        bytes += item.sequence;
        integer(item.state);
        real(item.signal_mass);
        real(item.context_potential);
        real(item.rank);
    }
    context_study::synced_write(path, bytes);
}
}
