#include "archive_consumer/core.h"

#include <zlib.h>

#include <algorithm>
#include <array>
#include <functional>
#include <iostream>
#include <stdexcept>

namespace archive_consumer {
namespace {
std::string gzip(const std::string& raw) {
    require(raw.size() <= 65536, "Synthetic gzip input bound");
    z_stream stream{};
    require(deflateInit2(&stream, 6, Z_DEFLATED, 15 + 16, 8, Z_DEFAULT_STRATEGY) == Z_OK,
            "Synthetic gzip initialization failed");
    gz_header header{};
    header.os = 255;
    const auto header_status = deflateSetHeader(&stream, &header);
    std::array<unsigned char, 131072> bytes{};
    stream.next_in = reinterpret_cast<Bytef*>(const_cast<char*>(raw.data()));
    stream.avail_in = static_cast<uInt>(raw.size());
    stream.next_out = bytes.data();
    stream.avail_out = static_cast<uInt>(bytes.size());
    const auto status = deflate(&stream, Z_FINISH);
    const auto size = bytes.size() - static_cast<std::size_t>(stream.avail_out);
    const auto ended = deflateEnd(&stream);
    require(header_status == Z_OK && status == Z_STREAM_END && ended == Z_OK,
            "Synthetic gzip construction failed");
    return {reinterpret_cast<const char*>(bytes.data()), size};
}
struct Controls {
    Json cases = Json::array();
    void pass(const std::string& name, const std::function<void()>& action) {
        action();
        cases.push_back({{"name", name}, {"expected", "accept"}, {"status", "passed"}});
    }
    void reject(const std::string& name,
                const std::string& message,
                const std::function<void()>& action) {
        bool rejected = false;
        try {
            action();
        } catch (const std::invalid_argument& error) {
            require(std::string(error.what()).find(message) != std::string::npos,
                    name + " failed at the wrong guard: " + error.what());
            rejected = true;
        }
        require(rejected, name + " was accepted");
        cases.push_back({{"name", name}, {"expected", "reject"}, {"status", "passed"}});
    }
};
}
int controls(const fs::path& scratch) {
    output_directory(scratch);
    Controls tests;
    const std::string raw = "synthetic trace\nACGT\n";
    fresh(scratch / "phase-trace.bin", raw);
    fresh(scratch / "trace.gz", gzip(raw));
    const auto original = file_pin(pin(scratch / "phase-trace.bin"));
    const auto archive = file_pin(pin(scratch / "trace.gz"));
    tests.reject("repinned dot path alias", "Non-normalized FilePin path", [&] {
        const auto alias = scratch / "." / "phase-trace.bin";
        auto repinned = as_json(original);
        repinned["path"] = alias.string();
        require(fs::file_size(alias) == original.size && sha256(alias) == original.sha256,
                "Repinned dot alias bytes differ");
        check(repinned);
    });
    fs::create_directory(scratch / "existing-directory");
    tests.reject("repinned dotdot path alias", "Non-normalized FilePin path", [&] {
        const auto alias = scratch / "existing-directory" / ".." / "phase-trace.bin";
        auto repinned = as_json(original);
        repinned["path"] = alias.string();
        require(fs::file_size(alias) == original.size && sha256(alias) == original.sha256,
                "Repinned dotdot alias bytes differ");
        check(repinned);
    });
    tests.pass("raw and gzip verify the same original SHA/size", [&] {
        verify_storage(Raw{original});
        verify_storage(Gzip{original, archive});
    });
    tests.reject("missing original raw trace", "Archive storage open failed", [&] {
        auto missing = original;
        missing.path = scratch / "absent-phase-trace.bin";
        verify_storage(Raw{missing});
    });
    fs::create_symlink(original.path, scratch / "symlink-trace");
    tests.reject("trace symlink", "Archive storage open failed", [&] {
        auto symlink = original;
        symlink.path = scratch / "symlink-trace";
        verify_storage(Raw{symlink});
    });
    const auto bad_bytes = [&](const std::string& name, std::string bytes) {
        const auto path = scratch / name;
        fresh(path, bytes);
        return file_pin(pin(path));
    };
    auto corrupt = gzip(raw);
    corrupt.at(corrupt.size() - 8) =
            static_cast<char>(static_cast<unsigned char>(corrupt.at(corrupt.size() - 8)) ^ 1U);
    const auto corrupt_pin = bad_bytes("bad-crc.gz", corrupt);
    tests.reject("stale compressed pin precedes deep CRC", "Stored FilePin SHA256/size differs",
                 [&] {
                     auto stale = archive;
                     stale.path = corrupt_pin.path;
                     verify_storage(Gzip{original, stale});
                 });
    tests.reject("repinned compressed CRC corruption", "Gzip data/CRC integrity failed",
                 [&] { verify_storage(Gzip{original, corrupt_pin}); });
    auto truncated = gzip(raw);
    truncated.resize(truncated.size() - 4);
    const auto truncated_pin = bad_bytes("truncated.gz", truncated);
    tests.reject("truncated gzip", "Gzip truncated",
                 [&] { verify_storage(Gzip{original, truncated_pin}); });
    auto changed_header = gzip(raw);
    changed_header.at(4) = 1;
    const auto header_pin = bad_bytes("nonzero-mtime.gz", changed_header);
    tests.reject("noncanonical deterministic gzip header", "Deterministic gzip6",
                 [&] { verify_storage(Gzip{original, header_pin}); });
    const auto extra = bad_bytes("trailing.gz", gzip(raw) + "x");
    tests.reject("trailing byte", "Gzip trailing bytes",
                 [&] { verify_storage(Gzip{original, extra}); });
    const auto concatenated = bad_bytes("concatenated.gz", gzip(raw) + gzip(raw));
    tests.reject("concatenated gzip member", "Gzip trailing bytes",
                 [&] { verify_storage(Gzip{original, concatenated}); });
    tests.reject("declared raw size underrun stops expansion", "Gzip raw byte bound exceeded", [&] {
        auto wrong = original;
        --wrong.size;
        verify_storage(Gzip{wrong, archive});
    });
    tests.reject("declared raw size overrun", "Gzip original SHA256/size differs", [&] {
        auto wrong = original;
        ++wrong.size;
        verify_storage(Gzip{wrong, archive});
    });
    tests.reject("wrong original raw SHA", "Gzip original SHA256/size differs", [&] {
        auto wrong = original;
        wrong.sha256 = std::string(64, '0');
        verify_storage(Gzip{wrong, archive});
    });
    tests.reject("hard original byte bound", "Original trace exceeds byte bound", [&] {
        auto wrong = original;
        wrong.size = maximum_trace_bytes + 1;
        verify_storage(Raw{wrong});
    });
    tests.reject("hard compressed byte bound", "Compressed trace exceeds byte bound", [&] {
        auto wrong = archive;
        wrong.size = maximum_trace_bytes + 1;
        verify_storage(Gzip{original, wrong});
    });
    const auto descriptor = Json{
            {"query_index", 0},
            {"native_completion", as_json(original)},
            {"producer", as_json(archive)},
            {"storage",
             {{"codec", "gzip"}, {"original", as_json(original)}, {"archive", as_json(archive)}}}};
    tests.reject("unsupported codec", "Unsupported trace codec", [&] {
        auto changed = descriptor;
        changed["storage"]["codec"] = "zstd";
        static_cast<void>(parse_trace(changed));
    });
    tests.reject("boolean archive proof", "Object field census differs", [&] {
        auto changed = descriptor;
        changed["storage"] = true;
        static_cast<void>(parse_trace(changed));
    });
    tests.reject("extra descriptor field", "Object field census differs", [&] {
        auto changed = descriptor;
        changed["archive_proof"] = true;
        static_cast<void>(parse_trace(changed));
    });
    tests.reject("missing archive entry", "Trace descriptor/decoded population count differs",
                 [&] { static_cast<void>(parse_traces(Json::array(), {0})); });
    tests.reject("extra archive entry", "Trace descriptor/decoded population count differs", [&] {
        static_cast<void>(parse_traces(Json::array({descriptor, descriptor}), {0}));
    });
    tests.reject("foreign archive query", "Unused/foreign archive query", [&] {
        auto changed = descriptor;
        changed["query_index"] = 1;
        static_cast<void>(parse_traces(Json::array({changed}), {0}));
    });
    tests.reject("duplicate archive query", "Duplicate archive query", [&] {
        auto changed = descriptor;
        changed["storage"]["original"]["path"] = (scratch / "second" / "phase-trace.bin").string();
        changed["storage"]["archive"]["path"] = (scratch / "second.gz").string();
        static_cast<void>(parse_traces(Json::array({descriptor, changed}), {0, 1}));
    });
    tests.reject("two queries alias one original trace", "Replayed native trace path", [&] {
        auto changed = descriptor;
        changed["query_index"] = 1;
        static_cast<void>(parse_traces(Json::array({descriptor, changed}), {0, 1}));
    });
    tests.reject("duplicate JSON key", "Duplicate JSON key",
                 [&] { static_cast<void>(parse("{\"a\":1,\"a\":2}")); });
    tests.pass("substitution insertion deletion and off-edit Q", [&] {
        require(apply_edits("ACGT", "abcd", {{1, 2, "T", 0}}) ==
                        std::pair<std::string, std::string>{"ATGT", "a!cd"},
                "Substitution/off-edit Q differs");
        require(apply_edits("ACGT", "abcd", {{1, 1, "TT", 0}}) ==
                        std::pair<std::string, std::string>{"ATTCGT", "a!!bcd"},
                "Insertion/off-edit Q differs");
        require(apply_edits("ACGT", "abcd", {{1, 3, "", 0}}) ==
                        std::pair<std::string, std::string>{"AT", "ad"},
                "Deletion/off-edit Q differs");
    });
    tests.pass("two edits and reverse input order reconstruct identically", [&] {
        const std::vector<Edit> forward{{0, 1, "TT", 0}, {3, 4, "", 1}};
        auto reverse = forward;
        std::reverse(reverse.begin(), reverse.end());
        require(apply_edits("ACGT", "abcd", forward) ==
                                std::pair<std::string, std::string>{"TTCG", "!!bc"} &&
                        apply_edits("ACGT", "abcd", forward) ==
                                apply_edits("ACGT", "abcd", reverse),
                "Two-edit reconstruction differs");
    });
    tests.pass("disabled identity", [&] {
        require(apply_edits("ACGT", "abcd", {}) ==
                        std::pair<std::string, std::string>{"ACGT", "abcd"},
                "Identity differs");
    });
    tests.reject("overlapping owned edits", "Owned edits overlap", [&] {
        static_cast<void>(apply_edits("ACGT", "abcd", {{0, 3, "A", 0}, {2, 4, "T", 1}}));
    });
    const auto directory = scratch / "native";
    fs::create_directory(directory);
    fresh(directory / "phase-trace.bin", raw);
    Json sources = Json::array();
    for (std::size_t index = 0; index < 32; ++index) {
        sources.push_back(
                {{"path", (scratch / ("synthetic-source-" + std::to_string(index))).string()},
                 {"size", 0},
                 {"sha256", hash_text("")}});
    }
    const Json binary = as_json(original), argv = Json::array({"synthetic", "decode-guarded"});
    const Json attempt = {{"schema", "context-decoder-attempt/1"},
                          {"binary", binary},
                          {"argv", argv},
                          {"compiled_sources", sources},
                          {"cpp_standard", 23},
                          {"fast_math", false},
                          {"fp_contract", "off"}};
    write(directory / "attempt.json", attempt);
    const auto native_trace = pin(directory / "phase-trace.bin");
    const Json result = {{"phase_trace", native_trace}};
    write(directory / "result.json", result);
    const auto catalogue = Json::array(
            {pin(directory / "attempt.json"), pin(directory / "result.json"), native_trace});
    const Json seal = {
            {"schema", "context-decoder-complete/1"}, {"complete", true}, {"files", catalogue}};
    write(directory / "complete.json", seal);
    const auto native_completion = pin(directory / "complete.json");
    write(scratch / "stdout", {{"completion", native_completion}});
    Json produced = catalogue;
    produced.push_back(native_completion);
    Json producer = {{"produced_files", produced},
                     {"raw_files", Json::array({nullptr, nullptr, nullptr, nullptr, nullptr,
                                                pin(scratch / "stdout")})}};
    const Json row = {{"query_index", 0},
                      {"result", pin(directory / "result.json")},
                      {"completion", native_completion},
                      {"producer", as_json(archive)}};
    const Json decoder = {{"binary", binary}, {"compiled_sources", sources}};
    const Trace trace{0, native_completion, row.at("producer"), Raw{file_pin(native_trace)}};
    const auto native = [&](const Json& supplied_row, const Json& supplied_result,
                            const Json& supplied_seal, const Json& supplied_producer,
                            const Json& supplied_decoder, const Trace& supplied_trace) {
        validate_native_catalogue(supplied_row, supplied_result, supplied_seal, supplied_producer,
                                  argv, supplied_decoder, supplied_trace);
    };
    tests.pass("synthetic full native catalogue raw",
               [&] { native(row, result, seal, producer, decoder, trace); });
    tests.pass("same native catalogue gzip", [&] {
        auto compressed_trace = trace;
        compressed_trace.storage = Gzip{file_pin(native_trace), archive};
        native(row, result, seal, producer, decoder, compressed_trace);
    });
    tests.reject("shortened legacy completion", "File catalogue count differs", [&] {
        auto changed = seal;
        changed["files"].erase(2);
        native(row, result, changed, producer, decoder, trace);
    });
    tests.reject("extra native completion member", "File catalogue count differs", [&] {
        auto changed = seal;
        changed["files"].push_back(as_json(archive));
        native(row, result, changed, producer, decoder, trace);
    });
    tests.reject("duplicate native completion member", "Duplicate catalogue path", [&] {
        auto changed = seal;
        changed["files"][2] = changed["files"][0];
        native(row, result, changed, producer, decoder, trace);
    });
    tests.reject("native complete missing from producer", "File catalogue count differs", [&] {
        auto changed = producer;
        changed["produced_files"].erase(3);
        native(row, result, seal, changed, decoder, trace);
    });
    tests.reject("extra producer output", "File catalogue count differs", [&] {
        auto changed = producer;
        changed["produced_files"].push_back(as_json(archive));
        native(row, result, seal, changed, decoder, trace);
    });
    tests.reject("duplicate producer output", "Duplicate catalogue path", [&] {
        auto changed = producer;
        changed["produced_files"][3] = changed["produced_files"][0];
        native(row, result, seal, changed, decoder, trace);
    });
    tests.reject("wrong producer identity", "Original native row/storage origin differs", [&] {
        auto changed = trace;
        changed.producer = as_json(original);
        native(row, result, seal, producer, decoder, changed);
    });
    tests.reject("changed result trace", "Original result/trace identity differs", [&] {
        auto changed = result;
        changed["phase_trace"]["sha256"] = std::string(64, '0');
        native(row, changed, seal, producer, decoder, trace);
    });
    tests.reject("foreign decoder source catalogue", "File catalogue membership differs", [&] {
        auto changed = decoder;
        changed["compiled_sources"][0]["sha256"] = std::string(64, '0');
        native(row, result, seal, producer, changed, trace);
    });
    write(scratch / "wrong-stdout", {{"completion", as_json(original)}});
    tests.reject("native stdout names another completion", "Raw native stdout names", [&] {
        auto changed = producer;
        changed["raw_files"][5] = pin(scratch / "wrong-stdout");
        native(row, result, seal, changed, decoder, trace);
    });
    const Json planned = {{"plan_sha256", "synthetic-plan"}};
    const Json target = {
            {"window", {{"read_id", "synthetic-parent"}}}, {"owned_start", 1}, {"owned_end", 2}};
    auto geometry_row = row;
    geometry_row["frame"] = as_json(original);
    geometry_row["base_frame"] = as_json(archive);
    Fields base = {{"query_index", "0"},
                   {"parent", "synthetic-parent"},
                   {"plan_sha256", "synthetic-plan"}};
    Fields frame = {{"owned_start", "1"}, {"owned_end", "2"}};
    add_pin(frame, "base_frame", geometry_row.at("base_frame"));
    const Json geometry_result = {{"schema", "context-decoder-guarded-frame/2"},
                                  {"frame", geometry_row.at("frame")},
                                  {"binding", frame},
                                  {"retained_rust_scalar_bit_comparisons", 1}};
    const Json construction = {{"schema", "uncertainty-feedback-frame-construction/1"},
                               {"new_plan_sha256", "synthetic-plan"},
                               {"target", target},
                               {"original_window", target.at("window")},
                               {"frame", geometry_row.at("frame")},
                               {"base_frame", geometry_row.at("base_frame")},
                               {"truth_input", false}};
    tests.pass("synthetic native geometry join", [&] {
        validate_geometry(planned, target, geometry_row, geometry_result, construction, base,
                          frame);
    });
    tests.reject("foreign frame", "Decoder new geometry/scalar linkage differs", [&] {
        auto changed = geometry_result;
        changed["frame"] = as_json(archive);
        validate_geometry(planned, target, geometry_row, changed, construction, base, frame);
    });
    tests.reject("foreign PLAN", "Decoder new geometry/scalar linkage differs", [&] {
        auto changed = planned;
        changed["plan_sha256"] = "foreign";
        validate_geometry(changed, target, geometry_row, geometry_result, construction, base,
                          frame);
    });
    tests.reject("foreign construction", "Original frame construction/PLAN join differs", [&] {
        auto changed = construction;
        changed["target"]["owned_end"] = 3;
        validate_geometry(planned, target, geometry_row, geometry_result, changed, base, frame);
    });
    tests.reject("zero independent scalar comparisons",
                 "Decoder new geometry/scalar linkage differs", [&] {
                     auto changed = geometry_result;
                     changed["retained_rust_scalar_bit_comparisons"] = 0;
                     validate_geometry(planned, target, geometry_row, changed, construction, base,
                                       frame);
                 });
    tests.reject("new witness cannot impersonate old source43", "Connector source witness changed",
                 [&] {
                     validate_completion({{"schema", "uncertainty-feedback-decoded/1"},
                                          {"complete", true},
                                          {"source_witness", source_witness()}},
                                         "uncertainty-feedback-decoded/1");
                 });
    const Json report = {{"schema", "uncertainty-feedback-archive-controls/1"},
                         {"complete", true},
                         {"synthetic_only", true},
                         {"biological_qualification", false},
                         {"native_acceptance", false},
                         {"source_witness", source_witness()},
                         {"cases", tests.cases},
                         {"assertions", tests.cases.size()},
                         {"skipped", 0}};
    write(scratch / "report.json", report);
    std::cout << report.dump() << '\n';
    return 0;
}
}
