#include "archive_consumer/core.h"
#include "compiled_sources.h"

#include <algorithm>
#include <set>

namespace archive_consumer {
Json own_dependencies() { return read(fs::path(own_unit_path) / "dependencies.json"); }
Json legacy_witness() {
    return own_dependencies().at("legacy_source_binding").at("source_witness");
}
TraceMap parse_traces(const Json& descriptors, const std::set<std::size_t>& queries) {
    require(descriptors.is_array() && descriptors.size() == queries.size(),
            "Trace descriptor/decoded population count differs");
    TraceMap traces;
    std::set<fs::path> original_paths, archive_paths;
    for (const auto& descriptor : descriptors) {
        auto trace = parse_trace(descriptor);
        require(queries.contains(trace.query_index), "Unused/foreign archive query");
        const auto original_path =
                std::visit([](const auto& value) { return value.original.path; }, trace.storage);
        require(original_paths.insert(original_path).second, "Replayed native trace path");
        if (const auto* gzip = std::get_if<Gzip>(&trace.storage)) {
            require(archive_paths.insert(gzip->archive.path).second,
                    "Duplicate compressed storage path");
        }
        const auto query = trace.query_index;
        require(traces.emplace(query, std::move(trace)).second, "Duplicate archive query");
    }
    for (const auto& path : archive_paths) {
        require(!original_paths.contains(path), "Compressed storage aliases an original trace");
    }
    return traces;
}
void validate_geometry(const Json& planned,
                       const Json& target,
                       const Json& row,
                       const Json& result,
                       const Json& construction,
                       const Fields& base,
                       const Fields& frame) {
    const auto id = integer(row.at("query_index"));
    require(result.at("schema") == "context-decoder-guarded-frame/2" &&
                    result.at("frame") == row.at("frame") && result.at("binding") == Json(frame) &&
                    base.at("query_index") == std::to_string(id) &&
                    base.at("parent") == target.at("window").at("read_id").get<std::string>() &&
                    base.at("plan_sha256") == planned.at("plan_sha256").get<std::string>() &&
                    natural(frame.at("owned_start")) == integer(target.at("owned_start")) &&
                    natural(frame.at("owned_end")) == integer(target.at("owned_end")) &&
                    integer(result.at("retained_rust_scalar_bit_comparisons")) > 0,
            "Decoder new geometry/scalar linkage differs");
    Fields base_binding;
    add_pin(base_binding, "base_frame", row.at("base_frame"));
    for (const auto& [key, value] : base_binding) {
        require(frame.at(key) == value, "Guarded/base frame Pin differs");
    }
    require(construction.at("schema") == "uncertainty-feedback-frame-construction/1" &&
                    construction.at("new_plan_sha256") == planned.at("plan_sha256") &&
                    construction.at("target") == target &&
                    construction.at("original_window") == target.at("window") &&
                    construction.at("frame") == row.at("frame") &&
                    construction.at("base_frame") == row.at("base_frame") &&
                    construction.at("truth_input") == false,
            "Original frame construction/PLAN join differs");
}
void verify_legacy_binding(const Json& value) {
    const auto expected = own_dependencies().at("legacy_source_binding");
    require(value == expected, "Frozen qualified legacy producer binding differs");
    for (const auto& key :
         {"source_manifest", "qualification", "native_result", "controls", "binary", "runtime"}) {
        check(value.at(key));
    }
    const auto sources = read(value.at("source_manifest").at("path").get<std::string>());
    require(sources.is_array() && sources.size() == 22, "Legacy source43 census differs");
    std::set<std::string> paths;
    for (const auto& source : sources) {
        require(paths.insert(file_pin(source).path.string()).second,
                "Duplicate legacy source manifest path");
        check(source);
    }
    const auto controls = read(value.at("controls").at("path").get<std::string>());
    require(controls.at("schema") == "uncertainty-feedback-controls/1" &&
                    controls.at("source_witness") == value.at("source_witness") &&
                    controls.at("assertions") == 26,
            "Accepted legacy controls/witness differs");
    const auto outer = read(value.at("qualification").at("path").get<std::string>());
    require(outer.at("schema") == "targeting-runtime-execution/1" && outer.at("complete") == true &&
                    outer.at("phase") == "native" &&
                    outer.at("result") == value.at("native_result") &&
                    outer.at("source_manifest") == value.at("source_manifest"),
            "Accepted legacy native qualification differs");
    const auto qualified = read(value.at("native_result").at("path").get<std::string>());
    require(qualified.at("complete") == true && qualified.at("phase") == "native" &&
                    qualified.at("binary") == value.at("binary") &&
                    qualified.at("runtime") == value.at("runtime") &&
                    qualified.at("controls_stdout") == value.at("controls") &&
                    qualified.at("source_manifest") == value.at("source_manifest") &&
                    qualified.at("source_witness") == value.at("source_witness"),
            "Accepted legacy binary/runtime/source closure differs");
    for (const auto& source : value.at("source_witness").at("compiled_sources")) {
        check(source);
    }
    check(value.at("source_witness").at("compiler"));
    validate_runtime(value.at("runtime"), value.at("binary"));
}
void apply_request(const Json& request_pin, const fs::path& output) {
    check(request_pin);
    const auto request = read(request_pin.at("path").get<std::string>());
    exact_keys(request, {"schema", "legacy_plan", "legacy_decoded_parts", "legacy_source_binding",
                         "old_decoder_manifest", "traces"});
    require(request.at("schema") == "uncertainty-feedback-archive-apply-request/1",
            "Archive apply request schema differs");
    verify_sources();
    verify_legacy_binding(request.at("legacy_source_binding"));
    const auto deps = dependencies();
    require(request.at("old_decoder_manifest") == deps.at("unchanged_decoder_manifest_pin"),
            "Qualified unchanged decoder manifest differs");
    check(request.at("old_decoder_manifest"));
    const auto decoder = read(request.at("old_decoder_manifest").at("path").get<std::string>());
    require(decoder.at("binary") == deps.at("unchanged_decoder"),
            "Qualified unchanged decoder binary differs");
    same_catalogue(decoder.at("compiled_sources"), decoder.at("compiled_sources"), 32);
    check(decoder.at("binary"));
    for (const auto& source : decoder.at("compiled_sources")) {
        check(source);
    }
    check(request.at("legacy_plan"));
    const auto planned = read(request.at("legacy_plan").at("path").get<std::string>());
    validate_plan(planned);
    const auto& parts = request.at("legacy_decoded_parts");
    require(parts.is_array() && !parts.empty() && parts.size() <= 512,
            "Nonempty bounded genuine decoded parts required");
    std::set<std::string> part_paths;
    std::map<std::size_t, Json> rows;
    for (const auto& part_pin : parts) {
        require(part_paths.insert(file_pin(part_pin).path.string()).second,
                "Replayed decoded part");
        check(part_pin);
        const auto part = read(part_pin.at("path").get<std::string>());
        validate_completion(part, "uncertainty-feedback-decoded/1");
        require(part.at("plan") == planned && part.at("unchanged_decoder") == decoder.at("binary"),
                "Original decoded part PLAN/decoder differs");
        require(part.at("rows").is_array() && !part.at("rows").empty(),
                "Empty genuine decoded part");
        for (const auto& row : part.at("rows")) {
            const auto query = integer(row.at("query_index"));
            require(query < 512 && rows.emplace(query, row).second,
                    "Foreign/replayed decoded query");
        }
    }
    Json decoded = {{"rows", Json::array()}, {"query_indices", Json::array()}};
    std::set<std::size_t> queries;
    for (const auto& [query, row] : rows) {
        decoded["rows"].push_back(row);
        decoded["query_indices"].push_back(query);
        queries.insert(query);
    }
    const auto traces = parse_traces(request.at("traces"), queries);
    output_directory(output);
    emit(planned, decoded, traces, request_pin, output);
}
}
