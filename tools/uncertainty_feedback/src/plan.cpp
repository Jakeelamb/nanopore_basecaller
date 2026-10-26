#include "uncertainty_feedback/core.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <optional>
#include <sstream>

namespace uncertainty_feedback {
namespace {
Json row_pin(const std::vector<std::string>& row, std::size_t offset) {
    require(row.size() > offset + 2, "Truncated manifest pin");
    return {{"path", row[offset]}, {"size", natural(row[offset + 1])}, {"sha256", row[offset + 2]}};
}
Json checked(const Json& parent, const std::string& key) {
    const auto value = parent.at(key);
    check(value);
    return read(value.at("path").get<std::string>());
}
std::vector<Json> reconstruct(const Fields& whole, const std::vector<Json>& chunks) {
    const auto count = natural(whole.at("chunk_count"));
    const auto signal = natural(whole.at("signal_samples"));
    require(count > 0 && count == chunks.size() && whole.at("stride") == "6",
            "Parent chunk count/stride differs");
    std::vector<Fields> values;
    for (std::size_t i = 0; i < count; ++i) {
        check(chunks[i].at("metadata"));
        values.push_back(metadata(chunks[i].at("metadata").at("path").get<std::string>()));
        const auto& meta = values.back();
        require(meta.at("format") == "DGM1" && meta.at("read_id") == whole.at("read_id") &&
                        natural(meta.at("chunk_index")) == i &&
                        natural(meta.at("chunk_count")) == count &&
                        meta.at("signal_samples") == whole.at("signal_samples") &&
                        meta.at("num_trimmed_samples") == whole.at("num_trimmed_samples") &&
                        meta.at("C") == "1024" &&
                        meta.at("model_path") ==
                                "/home/jake/Projects/nanopore_basecaller/models/"
                                "dna_r10.4.1_e8.2_400bps_hac@v6.0.0" &&
                        meta.at("score_file") ==
                                fs::path(chunks[i].at("score").at("path").get<std::string>())
                                        .filename()
                                        .string(),
                "Native reconstruction producer/parent/chunk binding differs");
        static_cast<void>(emissions(meta));
        require(meta.at("MOVES").size() == natural(meta.at("T")) && natural(meta.at("T")) <= 4096,
                "Chunk timestep geometry differs");
    }
    std::string sequence, quality, moves;
    std::size_t front{};
    std::vector<Json> result;
    for (std::size_t i = 0; i < count; ++i) {
        const auto& meta = values[i];
        std::size_t end{}, next_front{};
        if (i + 1 < count) {
            const auto finish =
                    natural(meta.at("input_offset")) + natural(meta.at("raw_chunk_size"));
            const auto next = natural(values[i + 1].at("input_offset"));
            require(finish >= next && (finish - next) % 6 == 0,
                    "Native stride-six overlap differs");
            const auto overlap = (finish - next) / 6;
            require(meta.at("MOVES").size() >= overlap / 2, "Native rear overlap exceeds chunk");
            end = meta.at("MOVES").size() - overlap / 2;
            next_front = overlap - overlap / 2;
        } else if (count == 1 || meta.at("variable_chunk_sizes") == "1") {
            end = (std::min(signal, natural(meta.at("raw_chunk_size"))) + 5) / 6;
        } else {
            end = meta.at("MOVES").size();
        }
        require(front <= end && end <= meta.at("MOVES").size(), "Retained chunk timestep bounds");
        const auto a = static_cast<std::size_t>(
                std::count(meta.at("MOVES").begin(),
                           meta.at("MOVES").begin() + static_cast<std::ptrdiff_t>(front), '1'));
        const auto b =
                a + static_cast<std::size_t>(std::count(
                            meta.at("MOVES").begin() + static_cast<std::ptrdiff_t>(front),
                            meta.at("MOVES").begin() + static_cast<std::ptrdiff_t>(end), '1'));
        const auto start = sequence.size();
        sequence += meta.at("SEQ").substr(a, b - a);
        quality += meta.at("Q").substr(a, b - a);
        moves += meta.at("MOVES").substr(front, end - front);
        result.push_back({{"t_start", front},
                          {"t_end", end},
                          {"chunk_base_start", a},
                          {"chunk_base_end", b},
                          {"parent_base_start", start},
                          {"parent_base_end", sequence.size()}});
        front = next_front;
    }
    if (moves.size() > signal / 6) {
        require(moves.size() == signal / 6 + 1, "Native final partial overhang differs");
        if (moves.back() == '1') {
            sequence.pop_back();
            quality.pop_back();
            result.back()["chunk_base_end"] = integer(result.back().at("chunk_base_end")) - 1;
        }
        moves.pop_back();
        result.back()["t_end"] = integer(result.back().at("t_end")) - 1;
        result.back()["parent_base_end"] = sequence.size();
    }
    require(sequence == whole.at("SEQ") && quality == whole.at("Q") && moves == whole.at("MOVES"),
            "Complete parent SEQ/Q/MOVES reconstruction differs");
    return result;
}
std::vector<std::optional<std::size_t>> coordinates(const std::vector<std::string>& sam) {
    std::vector<std::optional<std::size_t>> result;
    auto reference = natural(sam[3]) - 1;
    for (const auto& [length, op] : cigar(sam[5])) {
        if (op == 'M' || op == '=' || op == 'X') {
            for (std::size_t i = 0; i < length; ++i) {
                result.push_back(reference + i);
            }
            reference += length;
        } else if (op == 'I' || op == 'S') {
            result.insert(result.end(), length, std::nullopt);
        } else if (op == 'D' || op == 'N') {
            reference += length;
        } else {
            require(op == 'P', "Hardclipped native SAM cannot bind full parent");
        }
        require(result.size() <= 10000000, "Native mapping query bound");
    }
    require(result.size() == sam[9].size(), "Native CIGAR/SEQ length differs");
    if ((natural(sam[1]) & 16U) != 0) {
        std::reverse(result.begin(), result.end());
    }
    return result;
}
bool contiguous(const std::vector<std::optional<std::size_t>>& values,
                std::size_t a,
                std::size_t b,
                bool reverse) {
    if (a >= b || b > values.size()) {
        return false;
    }
    for (auto i = a; i < b; ++i) {
        if (!values[i]) {
            return false;
        }
        if (i > a &&
            (reverse ? *values[i] + 1 != *values[i - 1] : *values[i] != *values[i - 1] + 1)) {
            return false;
        }
    }
    return true;
}
Json location_receipt(const Json& proof) {
    Json selected;
    for (const auto& item : proof.at("receipts")) {
        check(item);
        const auto value = read(item.at("path").get<std::string>());
        if (value.value("stdout", std::string{}) !=
            proof.at("aligned_sam").at("path").get<std::string>()) {
            continue;
        }
        require(selected.is_null() && value.at("status") == "finished" && value.at("exit") == 0,
                "Duplicate/failed native location receipt");
        const fs::path recorder = value.at("recorder").get<std::string>();
        for (const auto* name : {"command.sh", "cwd.txt", "start.txt", "end.txt", "exit-status.txt",
                                 "stdout", "stderr", "time.txt"}) {
            const auto raw = pin(recorder / name);
            require(std::find(value.at("pins").begin(), value.at("pins").end(), raw) !=
                            value.at("pins").end(),
                    "Native receipt lacks raw evidence");
        }
        require(text(recorder / "exit-status.txt", 32) == "0\n" &&
                        value.at("stdout") == proof.at("aligned_sam").at("path"),
                "Native location producer exit/stdout differs");
        selected = item;
    }
    require(!selected.is_null(), "Exact native SAM producer receipt missing");
    return selected;
}
}
void validate_nomination_worker(const Json& worker,
                                const std::string& phase,
                                const Json& source_id,
                                const Json& prepared) {
    require((phase == "collect" || phase == "merge") &&
                    worker.at("schema") == "uncertainty-worker/1" &&
                    worker.at("complete") == true && worker.at("phase") == phase &&
                    worker.at("source_id") == source_id,
            "Nomination worker phase/schema/completion differs");
    std::set<std::string> expected = {"schema",  "complete",  "phase",  "admission_id",
                                      "sources", "source_id", "driver", "kernel_limits",
                                      "native",  "prepared",  "stages"};
    if (phase == "collect") {
        expected.insert("scans");
    } else {
        expected.insert({"engineering", "binary", "parts"});
    }
    std::set<std::string> supplied;
    for (const auto& [key, value] : worker.items()) {
        static_cast<void>(value);
        supplied.insert(key);
    }
    require(supplied == expected, "Nomination worker phase field census differs");
    require(worker.at("prepared") == prepared && worker.at("sources").is_array() &&
                    !worker.at("sources").empty() && worker.at("stages").is_array() &&
                    !worker.at("stages").empty(),
            "Worker/preparation/source/stage join differs");
    check(worker.at("driver"));
    check(worker.at("kernel_limits"));
    check(worker.at("native"));
    for (const auto& item : worker.at("sources")) {
        check(item);
    }
    for (const auto& item : worker.at("stages")) {
        check(item);
    }
    if (phase == "collect") {
        check(worker.at("scans"));
    } else {
        check(worker.at("binary"));
        check(worker.at("parts"));
        const auto engineering = checked(worker, "engineering");
        require(engineering.at("schema") == "uncertainty-worker/1" &&
                        engineering.at("complete") == true &&
                        engineering.at("phase") == "engineering" &&
                        engineering.at("source_id") == source_id &&
                        engineering.at("binary") == worker.at("binary") &&
                        engineering.at("sources") == worker.at("sources") &&
                        engineering.at("driver") == worker.at("driver"),
                "Merge worker/engineering binary/source join differs");
    }
}
void plan(const Json& config, const fs::path& output) {
    require(config.at("schema") == "uncertainty-feedback-config/1" &&
                    config.at("role") == "development",
            "Targeting config role/schema differs");
    const auto frozen =
            read("/home/jake/Projects/nanopore_basecaller-context-feedback-v2/config/"
                 "context-feedback-dev-v2.json");
    for (const auto& key :
         {"anchor_bases", "future_bases", "beam_width", "min_center", "max_center",
          "context_weight", "maximum_signal_deficit", "minimum_objective_margin", "minimum_mapq"}) {
        require(config.at("policy").at(key) == frozen.at("policy").at(key),
                "Frozen guarded policy differs");
    }
    fresh(output / "predeclared-protocol.md", text(config.at("protocol_path").get<std::string>()));
    const auto& inputs = config.at("inputs");
    const fs::path audit_path = inputs.at("audit").get<std::string>();
    require(sha256(audit_path) == inputs.at("audit_sha256").get<std::string>(),
            "Frozen full uncertainty audit changed");
    const auto audit = read(audit_path);
    require(audit.at("schema") == "uncertainty-v2-full-artifact-audit/1" &&
                    audit.at("complete") == true &&
                    audit.at("source_id") == config.at("nomination_source_id") &&
                    audit.at("unique_qualified_chunks") == 1557 &&
                    audit.at("parent_metadata_accounted") == 64 &&
                    audit.at("nominations_count") == 512,
            "Full uncertainty audit qualification differs");
    for (const auto& key : {"full_run", "prepared", "manifest", "native_merge", "nominations"}) {
        require(audit.at(key).at("sha256") == inputs.at(std::string(key) + "_sha256"),
                "Frozen nomination root changed");
        check(audit.at(key));
    }
    Json collected;
    for (const auto& key : {"collect", "merge"}) {
        const auto worker = checked(audit, key);
        validate_nomination_worker(worker, key, config.at("nomination_source_id"),
                                   audit.at("prepared"));
        if (std::string(key) == "collect") {
            collected = worker.at("native");
            const auto parts = read(collected.at("path").get<std::string>());
            require(parts.at("schema") == "uncertainty-collected-parts/1" &&
                            parts.at("complete") == true && parts.at("qualified_chunks") == 1557 &&
                            parts.at("prepared") == audit.at("prepared") &&
                            parts.at("scans") == worker.at("scans"),
                    "Collected complete chunk proof differs");
            check(parts.at("parts"));
        } else {
            require(worker.at("native") == audit.at("native_merge") &&
                            worker.at("parts") == collected,
                    "Merge worker/native/collected-parts join differs");
        }
    }
    const auto prepared = checked(audit, "prepared");
    require(prepared.at("schema") == "uncertainty-preparation/1" &&
                    prepared.at("complete") == true &&
                    prepared.at("source_id") == config.at("nomination_source_id") &&
                    prepared.at("manifest") == audit.at("manifest"),
            "Original preparation differs");
    for (const auto& item : prepared.at("sources")) {
        check(item);
    }
    const auto proof = checked(prepared, "original");
    require(proof.at("role") == "development", "Nondevelopment original input rejected");
    check(proof.at("aligned_sam"));
    const auto location = location_receipt(proof);
    const auto merge = checked(audit, "native_merge");
    const auto merge_result = checked(merge, "result");
    require(merge.at("complete") == true && merge.at("command") == "merge" &&
                    merge.at("source_id") == config.at("nomination_source_id") &&
                    merge.at("files").size() == 1 &&
                    merge.at("files").at(0) == audit.at("nominations") &&
                    merge_result.at("nominations") == 512 &&
                    merge_result.at("qualified_chunks") == 1557,
            "Native nomination merge/result differs");
    std::map<std::string, Json> parent_pins;
    std::map<std::string, std::vector<Json>> groups;
    std::map<std::string, Json> chunk_index;
    std::istringstream manifest(text(audit.at("manifest").at("path").get<std::string>()));
    std::string line;
    std::getline(manifest, line);
    require(split(line).at(0) == "uncertainty-inputs/1", "Original input schema differs");
    while (std::getline(manifest, line)) {
        const auto row = split(line);
        if (row[0] == "PARENT") {
            require(row.size() == 5 && parent_pins.emplace(row[1], row_pin(row, 2)).second,
                    "Duplicate parent declaration");
        } else if (row[0] == "CHUNK") {
            require(row.size() == 10, "Malformed chunk declaration");
            Json item = {{"id", row[1]},
                         {"parent", row[2]},
                         {"index", natural(row[3])},
                         {"score", row_pin(row, 4)},
                         {"metadata", row_pin(row, 7)}};
            require(chunk_index.emplace(row[1], item).second, "Duplicate chunk declaration");
            groups[row[2]].push_back(item);
        } else {
            require(row[0] == "SOURCE" || row[0] == "ALIGN", "Unknown manifest record");
        }
    }
    require(parent_pins.size() == 64 && chunk_index.size() == 1557,
            "Complete native population census differs");
    std::map<std::string, std::vector<std::string>> sams;
    std::istringstream alignment(
            text(proof.at("aligned_sam").at("path").get<std::string>(), 33554432));
    while (std::getline(alignment, line)) {
        if (line.empty() || line[0] == '@') {
            continue;
        }
        const auto row = split(line);
        require(row.size() >= 11, "Malformed native SAM row");
        if ((natural(row[1]) & 0x900U) != 0) {
            continue;
        }
        require(parent_pins.contains(row[0]) && sams.emplace(row[0], row).second,
                "Foreign/duplicate primary parent");
    }
    require(sams.size() == 64, "Primary native SAM population differs");
    Json parents = Json::object(), status_counts = Json::object();
    std::map<std::string, std::vector<Json>> spans;
    std::map<std::string, std::vector<std::optional<std::size_t>>> mappings;
    for (const auto& [id, item] : parent_pins) {
        check(item);
        const auto whole = metadata(item.at("path").get<std::string>());
        require(whole.at("format") == "DGP1" && whole.at("read_id") == id,
                "DGP parent association differs");
        auto& chunks = groups.at(id);
        std::sort(chunks.begin(), chunks.end(), [](const auto& a, const auto& b) {
            return integer(a.at("index")) < integer(b.at("index"));
        });
        spans[id] = reconstruct(whole, chunks);
        const auto& sam = sams.at(id);
        const auto flags = natural(sam[1]);
        const bool reverse = (flags & 16U) != 0;
        auto seq = sam[9], quality = sam[10];
        if (reverse) {
            seq = reverse_complement(seq);
            std::reverse(quality.begin(), quality.end());
        }
        const bool mapped = (flags & 4U) == 0 && sam[2] != "*" && sam[5] != "*";
        bool autosomal = false;
        for (std::size_t chromosome = 1; chromosome <= 22; ++chromosome) {
            autosomal = autosomal || sam[2] == "chr" + std::to_string(chromosome);
        }
        const auto status = !mapped                                          ? "native_unmapped"
                            : !autosomal                                     ? "native_non_autosome"
                            : natural(sam[4]) < 30 || natural(sam[4]) >= 255 ? "native_mapq"
                            : seq != whole.at("SEQ") || quality != whole.at("Q")
                                    ? "native_parent_seq_q_mismatch"
                                    : "eligible";
        status_counts[status] = status_counts.value(status, std::size_t{}) + 1;
        Json reconstruction = Json::array();
        for (const auto& chunk : chunks) {
            reconstruction.push_back(chunk.at("metadata"));
        }
        parents[id] = {
                {"parent_pin", item},
                {"reconstruction_metadata_pins", reconstruction},
                {"location_status", status},
                {"reverse", reverse},
                {"contig", sam[2]},
                {"chunk_count", chunks.size()},
                {"native_sequence", seq},
                {"native_quality", quality},
                {"native_location_sam", proof.at("aligned_sam")},
                {"export_matches_native_sam", seq == whole.at("SEQ") && quality == whole.at("Q")}};
        if (std::string(status) == "eligible") {
            mappings[id] = coordinates(sam);
        }
    }
    require(status_counts == audit.at("parent_status_counts"),
            "Native parent exception census changed");
    std::istringstream nominations(text(audit.at("nominations").at("path").get<std::string>()));
    std::getline(nominations, line);
    require(line == "uncertainty-proposals/1\t" +
                            audit.at("manifest").at("sha256").get<std::string>() + '\t' +
                            config.at("nomination_source_id").get<std::string>(),
            "Nomination source/manifest header differs");
    Json joins = Json::array();
    std::string windows, queries;
    std::map<std::string, std::vector<std::pair<std::size_t, std::size_t>>> owned;
    while (std::getline(nominations, line)) {
        const auto row = split(line);
        require(row.size() == 20 && (row[4] == "0" || row[4] == "1"), "Malformed nomination row");
        const auto index = joins.size(), c = natural(row[5]), d = natural(row[6]),
                   p = natural(row[7]), q = natural(row[8]);
        require(index < 512 && c >= 14 && d >= c && d - c == 21 && p >= 10 && q >= p && q - p == 21,
                "Owned nomination core geometry differs");
        const auto& chunk = chunk_index.at(row[0]);
        require(chunk.at("parent") == row[1] && integer(chunk.at("index")) == natural(row[2]) &&
                        parents.at(row[1]).at("location_status") == "eligible",
                "Foreign/ineligible nomination parent/chunk");
        const auto meta = metadata(chunk.at("metadata").at("path").get<std::string>());
        const auto emitted = emissions(meta);
        const auto& seq = meta.at("SEQ");
        require(d + 20 < emitted.size() && seq.substr(c, d - c) == row[15],
                "Nomination native core differs");
        const auto& retained = spans.at(row[1]).at(natural(row[2]));
        const auto chunk_a = integer(retained.at("chunk_base_start")),
                   chunk_b = integer(retained.at("chunk_base_end"));
        require(c >= chunk_a + 14 && d + 20 < chunk_b &&
                        integer(retained.at("parent_base_start")) + c - chunk_a == p,
                "Nomination retained parent/chunk join differs");
        const auto& mapping = mappings.at(row[1]);
        const bool reverse = row[4] == "1";
        require(reverse == parents.at(row[1]).at("reverse") &&
                        row[3] == parents.at(row[1]).at("contig").get<std::string>() &&
                        contiguous(mapping, p - 10, p, reverse) &&
                        contiguous(mapping, q, q + 20, reverse),
                "Nomination orientation/native guards differ");
        const auto ref_a = std::min(*mapping.at(p - 10), *mapping.at(q + 9));
        const auto ref_b = std::max(*mapping.at(p - 10), *mapping.at(q + 9)) + 1;
        const auto expanded_a = std::min(*mapping.at(p - 10), *mapping.at(q + 19));
        const auto expanded_b = std::max(*mapping.at(p - 10), *mapping.at(q + 19)) + 1;
        require(ref_b > ref_a + 20 && natural(row[13]) == ref_a + 10 &&
                        natural(row[14]) == ref_b - 10 && natural(row[11]) == expanded_a &&
                        natural(row[12]) == expanded_b && natural(row[9]) == emitted.at(c - 10) &&
                        natural(row[10]) == emitted.at(d + 20) &&
                        emitted.at(d + 20) - emitted.at(c - 10) <= 256,
                "Nomination base/future/reference boundaries differ");
        for (const auto& span : owned[row[1]]) {
            require(q <= span.first || p >= span.second, "Owned cores overlap");
        }
        owned[row[1]].emplace_back(p, q);
        std::size_t state{};
        const auto context = seq.substr(c - 14, 4);
        dna(context);
        for (const auto base : context) {
            state = state * 4 + std::string("ACGT").find(base);
        }
        Json window = {{"schema", "graph-prior-window/1"},
                       {"query_index", index},
                       {"read_id", row[1]},
                       {"contig", row[3]},
                       {"ref_start", ref_a},
                       {"ref_end", ref_b},
                       {"core_start", ref_a + 10},
                       {"core_end", ref_b - 10},
                       {"read_start", p - 10},
                       {"read_end", q + 10},
                       {"chunk_index", natural(row[2])},
                       {"chunk_start", c - 10},
                       {"chunk_end", d + 10},
                       {"t_start", emitted.at(c - 10)},
                       {"t_end", emitted.at(d + 10)},
                       {"reverse", reverse},
                       {"stock", seq.substr(c - 10, 41)},
                       {"context", context},
                       {"score_file", meta.at("score_file")}};
        const auto tie =
                hash_text("uncertainty-v1\n" + row[1] + '\n' + row[7] + '\n' + row[0] + '\n');
        require(tie == row[19], "Nomination deterministic identity differs");
        windows += window.dump() + "\n";
        queries += "GRCh38\t" + row[3] + '\t' + std::to_string(ref_a) + '\t' +
                   std::to_string(ref_b) + '\n';
        auto evidence = parents.at(row[1]);
        for (const auto& key : {"native_sequence", "native_quality", "native_location_sam"}) {
            evidence.erase(key);
        }
        evidence["score_pin"] = chunk.at("score");
        evidence["metadata_pin"] = chunk.at("metadata");
        joins.push_back({{"query_index", index},
                         {"nomination", row},
                         {"window", window},
                         {"evidence", evidence},
                         {"retained", retained},
                         {"initial_state", state},
                         {"owned_start", p},
                         {"owned_end", q},
                         {"expanded_t_start", emitted.at(c - 10)},
                         {"expanded_t_end", emitted.at(d + 20)},
                         {"expanded_ref_start", expanded_a},
                         {"expanded_ref_end", expanded_b},
                         {"location_sam", proof.at("aligned_sam")},
                         {"location_receipt", location}});
    }
    require(joins.size() == 512, "Fixed nomination population differs");
    fresh(output / "windows.jsonl", windows);
    fresh(output / "queries.tsv", queries);
    write(output / "joins.json", joins);
    write(output / "parents.json", parents);
    complete(output, "uncertainty-feedback-plan/1",
             {{"audit", pin(audit_path)},
              {"nomination_roots", audit},
              {"protocol", pin(output / "predeclared-protocol.md")},
              {"windows", pin(output / "windows.jsonl")},
              {"plan_sha256", sha256(output / "windows.jsonl")},
              {"queries", pin(output / "queries.tsv")},
              {"joins", pin(output / "joins.json")},
              {"parents", pin(output / "parents.json")},
              {"nomination_count", joins.size()},
              {"parent_status_counts", status_counts},
              {"owned_cores_nonoverlapping", true},
              {"guard_overlap_allowed", true},
              {"candidate_selection_uses_truth", false}});
}
void batch(const Json& planned, const std::vector<std::size_t>& ids, const fs::path& output) {
    validate_plan(planned);
    check(planned.at("joins"));
    check(planned.at("windows"));
    const auto joins = read(planned.at("joins").at("path").get<std::string>());
    Json mapping = Json::array();
    std::string queries;
    std::set<std::size_t> seen;
    for (const auto id : ids) {
        require(id < joins.size() && seen.insert(id).second, "Foreign/duplicate batch query");
        const auto& window = joins.at(id).at("window");
        const auto a = integer(window.at("ref_start")), b = integer(window.at("ref_end"));
        require(a < b && b - a <= 10000, "Graph genomic query bound");
        queries += "GRCh38\t" + window.at("contig").get<std::string>() + '\t' + std::to_string(a) +
                   '\t' + std::to_string(b) + '\n';
        mapping.push_back({{"local_query_index", mapping.size()},
                           {"global_query_index", id},
                           {"plan_sha256", planned.at("plan_sha256")}});
    }
    require(!mapping.empty(), "Empty graph batch");
    fresh(output / "queries.tsv", queries);
    write(output / "mapping.json", mapping);
    complete(output, "uncertainty-feedback-batch/1",
             {{"plan", planned},
              {"plan_sha256", planned.at("plan_sha256")},
              {"queries", pin(output / "queries.tsv")},
              {"mapping", pin(output / "mapping.json")},
              {"query_count", mapping.size()}});
}
}
