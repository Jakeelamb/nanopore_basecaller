#include "uncertainty_feedback/core.h"

#include <algorithm>
#include <fstream>
#include <iomanip>
#include <optional>
#include <sstream>

namespace uncertainty_feedback {
namespace {
void exact(const Json& value, const std::set<std::string>& expected) {
    require(value.is_object(), "Graph object required");
    std::set<std::string> actual;
    for (const auto& [key, item] : value.items()) {
        static_cast<void>(item);
        actual.insert(key);
    }
    require(actual == expected, "Graph record has unknown/missing fields");
}
std::string slice_reference(const Json& reference, std::size_t start, std::size_t end) {
    const auto a = integer(reference.at("start")), b = integer(reference.at("end"));
    const auto seq = reference.at("sequence").get<std::string>();
    require(a <= start && start <= end && end <= b && b - a == seq.size(),
            "Extracted reference does not cover requested span");
    return seq.substr(start - a, end - start);
}
std::map<std::string, std::string> fasta_spans(const fs::path& path, const Json& rows) {
    std::map<std::string, std::vector<std::pair<std::size_t, std::size_t>>> wanted;
    for (const auto& row : rows) {
        const auto& ref = row.at("reference");
        wanted[row.at("query").at("contig").get<std::string>()].emplace_back(
                integer(ref.at("start")), integer(ref.at("end")));
    }
    for (auto& [contig, spans] : wanted) {
        static_cast<void>(contig);
        std::sort(spans.begin(), spans.end());
        spans.erase(std::unique(spans.begin(), spans.end()), spans.end());
    }
    std::map<std::string, std::string> result;
    std::ifstream input(path);
    require(input.good(), "Cannot open pinned FASTA");
    std::string line, contig;
    std::size_t offset{};
    while (std::getline(input, line)) {
        require(line.find('\r') == std::string::npos, "FASTA CR rejected");
        if (line.starts_with('>')) {
            contig = line.substr(1, line.find_first_of(" \t", 1) - 1);
            offset = 0;
            continue;
        }
        if (wanted.contains(contig)) {
            for (const auto& [a, b] : wanted.at(contig)) {
                if (offset < b && offset + line.size() > a) {
                    const auto begin = std::max(a, offset) - offset,
                               end = std::min(b, offset + line.size()) - offset;
                    const auto key = contig + ':' + std::to_string(a) + ':' + std::to_string(b);
                    result[key] += line.substr(begin, end - begin);
                }
            }
        }
        offset += line.size();
    }
    require(input.eof(), "Pinned FASTA read failed");
    return result;
}
}
Json project(const Json& window, const Json& graph) {
    exact(graph, {"schema", "query_index", "query", "reference", "boundary_nodes", "walks"});
    exact(graph.at("query"), {"sample", "contig", "start", "end"});
    exact(graph.at("reference"), {"start", "end", "sequence"});
    require(window.at("reverse").is_boolean() &&
                    integer(window.at("ref_start")) + 20 <= integer(window.at("ref_end")) &&
                    integer(graph.at("query_index")) == integer(window.at("query_index")),
            "Guarded query type/span differs");
    require(graph.at("boundary_nodes").is_array() && graph.at("boundary_nodes").size() == 2,
            "Graph boundary node census differs");
    require(graph.at("schema") == "hprc-local-paths/1" &&
                    graph.at("query_index") == window.at("query_index") &&
                    graph.at("query") == Json{{"sample", "GRCh38"},
                                              {"contig", window.at("contig")},
                                              {"start", window.at("ref_start")},
                                              {"end", window.at("ref_end")}},
            "Guarded graph query linkage differs");
    const auto& reference = graph.at("reference");
    const auto ref_start = integer(reference.at("start")), ref_end = integer(reference.at("end"));
    const auto ref_seq = reference.at("sequence").get<std::string>();
    require(ref_start <= ref_end && ref_end - ref_start == ref_seq.size() &&
                    ref_seq.size() <= 65536,
            "Graph reference span differs");
    bool complete_reference = false;
    require(graph.at("walks").is_array() && graph.at("walks").size() <= 10000,
            "Graph walk census bound");
    for (const auto& walk : graph.at("walks")) {
        exact(walk, {"is_reference", "both_anchors", "sequence", "cigar", "copy_count"});
        require(walk.at("is_reference").is_boolean() && walk.at("both_anchors").is_boolean(),
                "Graph anchor/reference flags must be boolean");
        complete_reference = complete_reference ||
                             (walk.at("is_reference") == true && walk.at("both_anchors") == true &&
                              walk.at("sequence") == ref_seq &&
                              walk.at("cigar") == std::to_string(ref_seq.size()) + 'M');
    }
    require(complete_reference, "Guarded graph lacks complete reference path");
    const auto start = integer(window.at("ref_start")) + 10,
               end = integer(window.at("ref_end")) - 10;
    require(start <= end, "Guarded genomic center reversed");
    std::set<std::string> paths;
    Json exclusions = Json::array();
    std::size_t index{};
    for (const auto& walk : graph.at("walks")) {
        if (walk.at("both_anchors") != true) {
            exclusions.push_back(
                    {{"walk", index++}, {"reason", "unanchored_or_predeclared_withheld"}});
            continue;
        }
        const auto sequence = walk.at("sequence").get<std::string>();
        require(sequence.size() <= 65536, "Graph walk sequence byte bound");
        std::size_t r = ref_start, q{};
        std::optional<std::size_t> a, b;
        for (const auto& [length, op] : cigar(walk.at("cigar").get<std::string>())) {
            if (op == 'M' || op == '=' || op == 'X') {
                if (start > 0 && start - 1 >= r && start - 1 - r < length) {
                    a = q + start - 1 - r;
                }
                if (end >= r && end - r < length) {
                    b = q + end - r;
                }
                r += length;
                q += length;
            } else if (op == 'I') {
                q += length;
            } else if (op == 'D') {
                r += length;
            } else {
                throw std::invalid_argument("Unsupported guarded graph CIGAR");
            }
            require(r <= ref_end && q <= sequence.size(), "Guarded graph CIGAR span differs");
        }
        require(r == ref_end && q == sequence.size(), "Guarded graph CIGAR span differs");
        if (!a || !b) {
            exclusions.push_back(
                    {{"walk", index}, {"reason", "editable_center_guard_anchor_absent"}});
        } else {
            require(*a + 1 <= *b, "Guarded graph center reversed");
            auto center = sequence.substr(*a + 1, *b - *a - 1);
            if (window.at("reverse") == true) {
                center = reverse_complement(center);
            }
            dna(center);
            require(center.size() <= 108, "Guarded center context bound");
            paths.insert(center);
        }
        ++index;
    }
    require(paths.size() <= 32, "Guarded unique context cap exceeded");
    return {{"centers", paths}, {"exclusions", exclusions}};
}
void qualify_graph(const Json& config,
                   const Json& planned,
                   const Json& batch_manifest,
                   const Json& raw_receipt,
                   const fs::path& raw,
                   const fs::path& output) {
    validate_plan(planned);
    validate_completion(batch_manifest, "uncertainty-feedback-batch/1");
    require(batch_manifest.at("plan_sha256") == planned.at("plan_sha256"),
            "Batch/new plan linkage differs");
    for (const auto& key : {"joins", "windows"}) {
        check(planned.at(key));
    }
    for (const auto& key : {"queries", "mapping"}) {
        check(batch_manifest.at(key));
    }
    const auto& graph_config = config.at("graph");
    check(graph_config.at("resource"));
    check(graph_config.at("binary"));
    require(raw_receipt.at("argv") ==
                    Json::array({graph_config.at("binary").at("path"),
                                 graph_config.at("resource").at("path"),
                                 batch_manifest.at("queries").at("path"), raw.string()}),
            "Graph producer argv/query mapping differs");
    const auto graph_manifest = read(graph_config.at("source_manifest").get<std::string>());
    require(graph_manifest.at("tool").at("binary").at("sha256") ==
                            graph_config.at("binary").at("sha256") &&
                    graph_manifest.at("graph").at("sha256") ==
                            graph_config.at("resource").at("sha256"),
            "Graph manifest source/binary/resource identity differs");
    const fs::path source_root = "/home/jake/Projects/nanopore_basecaller-reference";
    Json graph_sources = Json::array();
    for (auto item : graph_manifest.at("tool").at("source")) {
        item["path"] = (source_root / item.at("path").get<std::string>()).string();
        check(item);
        graph_sources.push_back(item);
    }
    const auto source_manifest = dependencies().at("graph_source_manifest");
    check(source_manifest);
    require(source_manifest.at("path") == graph_config.at("source_manifest"),
            "Frozen graph source manifest path differs");
    Json producer_inputs = Json::array(
            {graph_config.at("resource"), batch_manifest.at("queries"), source_manifest});
    for (const auto& item : graph_sources) {
        producer_inputs.push_back(item);
    }
    const auto graph_argv = Json::array({graph_config.at("binary").at("path"),
                                         graph_config.at("resource").at("path"),
                                         batch_manifest.at("queries").at("path"), raw.string()});
    validate_receipt(raw_receipt, graph_config.at("binary"), graph_argv, producer_inputs);
    require(raw_receipt.at("environment") == command_environment() &&
                    raw_receipt.at("extra_runtimes").empty(),
            "Graph actual environment/runtime census differs");
    validate_runtime(raw_receipt.at("runtime"), graph_config.at("binary"));
    const auto mapping = read(batch_manifest.at("mapping").at("path").get<std::string>());
    const auto joins = read(planned.at("joins").at("path").get<std::string>());
    Json rows = Json::array();
    std::istringstream input(text(raw / "walks.jsonl", 104857600));
    std::string line;
    while (std::getline(input, line)) {
        require(line.size() <= 2097152, "Graph JSONL line bound");
        rows.push_back(parse(line));
    }
    require(rows.size() == mapping.size() &&
                    rows.size() == integer(batch_manifest.at("query_count")),
            "Complete raw graph query census differs");
    Json raw_pins = Json::array();
    std::set<std::string> expected = {"graph-metadata.json", "walks.jsonl"};
    for (std::size_t local = 0; local < rows.size(); ++local) {
        std::ostringstream name;
        name << std::setw(4) << std::setfill('0') << local;
        expected.insert(name.str() + ".gfa");
        expected.insert(name.str() + ".walks.tsv");
    }
    std::set<std::string> actual;
    for (const auto& entry : fs::directory_iterator(raw)) {
        require(entry.is_regular_file() && !entry.is_symlink(), "Foreign raw graph entry");
        actual.insert(entry.path().filename().string());
        const auto item = pin(entry.path());
        require(std::find(raw_receipt.at("produced_files").begin(),
                          raw_receipt.at("produced_files").end(),
                          item) != raw_receipt.at("produced_files").end(),
                "Raw graph bytes not bound by actual producer");
        raw_pins.push_back(item);
    }
    require(actual == expected, "Raw graph file census differs");
    const auto donor_metadata = read(raw / "graph-metadata.json");
    for (const auto& label : donor_metadata.at("samples")) {
        const auto name = label.get<std::string>();
        require(name != "HG002" && name != "HG003" && name != "HG004" && name != "HG005" &&
                        name != "NA19240",
                "Excluded target/relative graph donor label present");
    }
    const fs::path fasta = graph_config.at("reference").at("path").get<std::string>();
    require(sha256(fasta) == graph_config.at("reference").at("sha256").get<std::string>(),
            "Pinned full reference changed");
    const auto reference_spans = fasta_spans(fasta, rows);
    Json qualified = Json::array();
    std::string normalized;
    for (std::size_t local = 0; local < rows.size(); ++local) {
        auto graph = rows.at(local);
        const auto& join = mapping.at(local);
        const auto global = integer(join.at("global_query_index"));
        require(integer(join.at("local_query_index")) == local &&
                        join.at("plan_sha256") == planned.at("plan_sha256") &&
                        integer(graph.at("query_index")) == local && global < joins.size(),
                "Wrong new plan/global-local graph join");
        const auto& target = joins.at(global);
        const auto& window = target.at("window");
        graph["query_index"] = global;
        const auto& reference = graph.at("reference");
        const auto a = integer(reference.at("start")), b = integer(reference.at("end"));
        const auto key = window.at("contig").get<std::string>() + ':' + std::to_string(a) + ':' +
                         std::to_string(b);
        require(reference_spans.contains(key) &&
                        reference_spans.at(key) == reference.at("sequence").get<std::string>(),
                "Full extracted reference differs from pinned FASTA");
        Json projection;
        std::string availability = "usable", reason;
        try {
            projection = project(window, graph);
        } catch (const std::invalid_argument& error) {
            const std::string message = error.what();
            if (message != "Guarded unique context cap exceeded" &&
                message != "Guarded center context bound") {
                throw;
            }
            projection = {{"centers", Json::array()}, {"exclusions", Json::array()}};
            availability = "missing";
            reason = message;
        }
        auto oriented = slice_reference(reference, integer(target.at("expanded_ref_start")),
                                        integer(target.at("expanded_ref_end")));
        if (window.at("reverse") == true) {
            oriented = reverse_complement(oriented);
        }
        check(target.at("evidence").at("metadata_pin"));
        const auto meta =
                metadata(target.at("evidence").at("metadata_pin").at("path").get<std::string>());
        const auto c = integer(window.at("chunk_start")), d = integer(window.at("chunk_end"));
        const auto left = meta.at("SEQ").substr(c, 10), right = meta.at("SEQ").substr(d - 10, 20);
        if (oriented.size() < 30 || !oriented.starts_with(left) || !oriented.ends_with(right)) {
            availability = "missing";
            reason = "native_reference_guard_mismatch";
        }
        if (projection.at("centers").empty() && reason.empty()) {
            availability = "missing";
            reason = "no_anchored_context_center";
        }
        normalized += graph.dump() + "\n";
        qualified.push_back(
                {{"query_index", global},
                 {"local_query_index", local},
                 {"availability", availability},
                 {"reason", reason},
                 {"projection", projection},
                 {"graph", graph},
                 {"raw_graph_sha256", sha256(raw / "walks.jsonl")},
                 {"base_guards_equal_reference", reason != "native_reference_guard_mismatch"}});
    }
    fresh(output / "walks.jsonl", normalized);
    write(output / "qualified.json", qualified);
    complete(output, "uncertainty-feedback-graph/1",
             {{"plan", planned},
              {"plan_sha256", planned.at("plan_sha256")},
              {"batch", batch_manifest},
              {"producer", raw_receipt},
              {"graph_resource", graph_config.at("resource")},
              {"graph_sources", graph_sources},
              {"graph_source_manifest", pin(graph_config.at("source_manifest").get<std::string>())},
              {"reference", pin(fasta)},
              {"raw_files", raw_pins},
              {"walks", pin(output / "walks.jsonl")},
              {"qualified", pin(output / "qualified.json")},
              {"donor_metadata", pin(raw / "graph-metadata.json")},
              {"exclusion_policy", "fixed population; no refill or path truncation"}});
}
}
