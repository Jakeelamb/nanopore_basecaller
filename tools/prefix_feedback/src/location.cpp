#include "prefix_feedback/session.h"
#include "prefix_feedback/resource_evidence.h"

#include <algorithm>
#include <cctype>
#include <limits>
#include <set>
#include <sstream>

namespace prefix_feedback {
namespace {
std::size_t natural(const std::string& value) {
    require(!value.empty() && value.find_first_not_of("0123456789") == std::string::npos,
            "PAF unsigned field required");
    return static_cast<std::size_t>(std::stoull(value));
}
std::pair<std::size_t, std::size_t> cigar_extent(const std::string& cigar) {
    std::size_t query{};
    std::size_t reference{};
    std::size_t count{};
    for (const char op : cigar) {
        if (op >= '0' && op <= '9') {
            require(count <= 100000000, "CIGAR operation bound");
            count = count * 10 + static_cast<std::size_t>(op - '0');
            continue;
        }
        require(count > 0 && std::string("MIDN=X").find(op) != std::string::npos,
                "unsupported CIGAR");
        if (op == 'M' || op == 'I' || op == '=' || op == 'X') {
            query += count;
        }
        if (op == 'M' || op == 'D' || op == 'N' || op == '=' || op == 'X') {
            reference += count;
        }
        count = 0;
    }
    require(count == 0 && query > 0 && reference > 0, "truncated/empty CIGAR");
    return {query, reference};
}
}
Json parse_paf(const std::string& paf, const Json& query) {
    Json result = Json::array();
    std::istringstream stream(paf);
    std::string line;
    std::set<std::string> ids;
    while (std::getline(stream, line)) {
        require(!line.empty() && line.find('\r') == std::string::npos && result.size() < 32,
                "PAF row/census bound");
        std::istringstream row(line);
        std::vector<std::string> fields;
        std::string field;
        while (std::getline(row, field, '\t')) {
            fields.push_back(field);
        }
        require(fields.size() >= 13 && fields[0] == "prefix" &&
                        natural(fields[1]) == query.at("length").get<std::size_t>(),
                "foreign mapper prefix");
        const auto qbegin = natural(fields[2]);
        const auto qend = natural(fields[3]);
        const auto rlength = natural(fields[6]);
        const auto rbegin = natural(fields[7]);
        const auto rend = natural(fields[8]);
        const auto mapq = natural(fields[11]);
        require(qbegin < qend && qend <= natural(fields[1]) && rbegin < rend && rend <= rlength &&
                        (fields[4] == "+" || fields[4] == "-") && mapq <= 255 && !fields[5].empty(),
                "mapper coordinates/orientation bounds");
        std::string cigar;
        for (std::size_t index = 12; index < fields.size(); ++index) {
            if (fields[index].starts_with("cg:Z:")) {
                require(cigar.empty(), "duplicate mapper CIGAR");
                cigar = fields[index].substr(5);
            }
        }
        const auto [query_extent, reference_extent] = cigar_extent(cigar);
        require(query_extent == qend - qbegin && reference_extent == rend - rbegin,
                "mapper CIGAR/extent differs");
        Json value{{"contig", fields[5]},
                   {"strand", fields[4]},
                   {"query_begin", qbegin},
                   {"query_end", qend},
                   {"query_length", natural(fields[1])},
                   {"reference_begin", rbegin},
                   {"reference_end", rend},
                   {"reference_length", rlength},
                   {"mapq", mapq},
                   {"cigar", cigar}};
        value["id"] = digest(value.dump());
        require(ids.insert(value.at("id")).second, "duplicate mapper position");
        result.push_back(std::move(value));
    }
    return result;
}
void validate_command_evidence(const Json& receipt, const Json& expected_sources) {
    require(expected_sources.is_array() && !expected_sources.empty() &&
                    receipt.at("source_pins") == expected_sources,
            "producer source census differs");
    for (const auto& source : expected_sources) {
        check_pin(source);
    }
    for (const auto& key : {"stdout", "stderr", "time", "terminal_proof"}) {
        check_pin(receipt.at(key));
    }
    const auto terminal = read_json(receipt.at("terminal_proof").at("path").get<std::string>());
    require(receipt.at("complete") == true && receipt.at("exit_status") == 0 &&
                    receipt.at("terminal") == true && terminal.at("group_empty") == true &&
                    terminal.at("cgroup_empty") == true && terminal.at("reaped") == true,
            "producer terminal proof differs");
    const auto expected_command = Json{{"role", receipt.at("role")},
                                       {"argv", receipt.at("argv")},
                                       {"cwd", receipt.at("cwd")},
                                       {"environment", receipt.at("environment")},
                                       {"inputs", receipt.at("inputs")},
                                       {"binding", receipt.at("binding")},
                                       {"source_pins", receipt.at("source_pins")},
                                       {"stdout", receipt.at("stdout")},
                                       {"produced_files", receipt.at("produced_files")}};
    require(terminal.at("command") == expected_command,
            "producer terminal command binding differs");
}
Json validate_resources(const Json& manifest, const std::string& plan_sha256) {
    require(!manifest.is_null(), "frozen resource manifest required for localization");
    check_pin(manifest);
    const auto declared = read_json(manifest.at("path").get<std::string>());
    require(declared.at("schema") == "prefix-resources/1" &&
                    declared.at("plan_sha256") == plan_sha256,
            "frozen resource plan differs");
    const auto resources = declared.at("resources");
    require(resources.size() == 7, "frozen resource census differs");
    require(resources.at("producer_sources").is_array() &&
                    !resources.at("producer_sources").empty(),
            "frozen producer source census is empty");
    for (const auto& key : {"mapper", "reference_index", "reference", "reference_fai", "samtools",
                            "index_provenance"}) {
        check_pin(resources.at(key));
    }
    const auto lineage = read_json(resources.at("index_provenance").at("path").get<std::string>());
    if (lineage.at("schema") == "prefix-legacy-resource-evidence/1") {
        for (const auto& source : resources.at("producer_sources")) {
            check_pin(source);
        }
        resource_evidence::validate(resources, lineage, resource_evidence::frozen_trust());
        return resources;
    }
    require(lineage.at("schema") == "prefix-reference-lineage/1" && lineage.at("complete") == true,
            "reference/index lineage absent");
    for (const auto& key :
         {"mapper", "reference_index", "reference", "reference_fai", "samtools"}) {
        require(lineage.at(key) == resources.at(key), "reference/index lineage identity differs");
    }
    for (const auto& source : resources.at("producer_sources")) {
        check_pin(source);
    }
    for (const auto& role : {"index_build", "fai_build"}) {
        check_pin(lineage.at(role).at("receipt"));
        const auto receipt =
                read_json(lineage.at(role).at("receipt").at("path").get<std::string>());
        validate_command_evidence(receipt, lineage.at(role).at("producer_sources"));
        require(receipt.at("argv") == lineage.at(role).at("argv") &&
                        receipt.at("cwd") == lineage.at(role).at("cwd") &&
                        receipt.at("environment") == lineage.at(role).at("environment"),
                "reference/index build command custody differs");
        if (std::string(role) == "index_build") {
            const auto& argv = receipt.at("argv");
            require(argv.size() >= 4 && argv.at(0) == resources.at("mapper").at("path") &&
                            argv.at(argv.size() - 3) == "-d" &&
                            argv.at(argv.size() - 2) ==
                                    resources.at("reference_index").at("path") &&
                            argv.back() == resources.at("reference").at("path"),
                    "reference/index build relationship differs");
            require(receipt.at("role") == "reference-index-build" &&
                            receipt.at("inputs") == Json::array({resources.at("mapper"),
                                                                 resources.at("reference")}) &&
                            receipt.at("produced_files") ==
                                    Json::array({resources.at("reference_index")}),
                    "reference/index build input/output census differs");
        } else {
            require(receipt.at("role") == "reference-fai-build" &&
                            receipt.at("argv") ==
                                    Json::array({resources.at("samtools").at("path"), "faidx",
                                                 resources.at("reference").at("path")}) &&
                            receipt.at("inputs") == Json::array({resources.at("samtools"),
                                                                 resources.at("reference")}) &&
                            receipt.at("produced_files") ==
                                    Json::array({resources.at("reference_fai")}),
                    "reference/FAI build input/output relationship differs");
        }
    }
    return resources;
}
std::vector<Location> parse_locations(const Json& update, const Json& resources) {
    std::vector<Location> result;
    std::set<std::string> ids;
    require(update.at("locations").empty() || !resources.empty(),
            "frozen resources required for retained positions");
    for (const auto& value : update.at("locations")) {
        require(value.size() == 13, "location fields differ");
        Location item{value.at("id"),
                      value.at("contig"),
                      value.at("strand"),
                      value.at("query_begin"),
                      value.at("query_end"),
                      value.at("query_length"),
                      value.at("reference_begin"),
                      value.at("reference_end"),
                      value.at("reference_length"),
                      value.at("mapq"),
                      value.at("cigar"),
                      value.at("continuation"),
                      value.at("evidence")};
        dna(item.continuation);
        require(item.continuation.size() <= 8192 && item.query_begin < item.query_end &&
                        item.query_end <= item.query_length &&
                        item.reference_begin < item.reference_end &&
                        item.reference_end <= item.reference_length && item.mapq <= 255 &&
                        (item.strand == "+" || item.strand == "-") && ids.insert(item.id).second,
                "location geometry/duplicate bound");
        const auto [query, reference] = cigar_extent(item.cigar);
        require(query == item.query_end - item.query_begin &&
                        reference == item.reference_end - item.reference_begin,
                "location CIGAR extent differs");
        require(item.evidence.at("confidence_feature") == "minimap2-MAPQ-not-posterior" &&
                        item.evidence.at("continuation_orientation") == "signal-forward",
                "location confidence/orientation meaning differs");
        if (!item.continuation.empty()) {
            for (const auto& key : {"reference", "reference_fai", "samtools"}) {
                check_pin(item.evidence.at(key));
            }
            for (const auto& key : {"reference", "reference_fai", "samtools"}) {
                require(item.evidence.at(key) == resources.at(key),
                        "continuation frozen resource identity differs");
            }
            require(item.evidence.at("index_provenance") == resources.at("index_provenance"),
                    "continuation index/reference lineage differs");
            check_pin(item.evidence.at("reference_receipt"));
            check_pin(item.evidence.at("fasta"));
            const auto receipt =
                    read_json(item.evidence.at("reference_receipt").at("path").get<std::string>());
            require(receipt.at("role") == "reference-continuation" &&
                            receipt.at("complete") == true && receipt.at("exit_status") == 0 &&
                            receipt.at("terminal") == true &&
                            receipt.at("stdout") == item.evidence.at("fasta"),
                    "reference continuation receipt differs");
            require(receipt.at("inputs") ==
                            Json::array({resources.at("reference"), resources.at("reference_fai"),
                                         resources.at("samtools")}),
                    "reference continuation exact input census differs");
            auto fasta = read_text(item.evidence.at("fasta").at("path").get<std::string>());
            const auto newline = fasta.find('\n');
            require(newline != std::string::npos && fasta[0] == '>',
                    "reference FASTA header absent");
            auto sequence = fasta.substr(newline + 1);
            sequence.erase(std::remove(sequence.begin(), sequence.end(), '\n'), sequence.end());
            for (auto& base : sequence) {
                base = static_cast<char>(std::toupper(static_cast<unsigned char>(base)));
            }
            dna(sequence);
            const auto begin = item.evidence.at("reference_begin").get<std::size_t>();
            const auto end = item.evidence.at("reference_end").get<std::size_t>();
            require(begin < end && end - begin == sequence.size() &&
                            (item.strand == "+" ? begin == item.reference_end
                                                : end == item.reference_begin),
                    "reference continuation interval differs");
            require(receipt.at("binding") == Json{{"location_id", item.id},
                                                  {"contig", item.contig},
                                                  {"reference_begin", begin},
                                                  {"reference_end", end},
                                                  {"strand", item.strand}},
                    "reference continuation receipt location differs");
            const auto region =
                    item.contig + ":" + std::to_string(begin + 1) + "-" + std::to_string(end);
            require(receipt.at("argv") ==
                            Json::array({item.evidence.at("samtools").at("path"), "faidx",
                                         item.evidence.at("reference").at("path"), region}),
                    "reference continuation exact argv differs");
            require(receipt.at("cwd") == source_witness().at("root") &&
                            receipt.at("environment").at("LC_ALL") == "C",
                    "reference continuation cwd/environment differs");
            validate_command_evidence(receipt, resources.at("producer_sources"));
            require(item.continuation ==
                            (item.strand == "+" ? sequence : reverse_complement(sequence)),
                    "reference continuation strand differs");
        }
        result.push_back(std::move(item));
    }
    return result;
}
}
