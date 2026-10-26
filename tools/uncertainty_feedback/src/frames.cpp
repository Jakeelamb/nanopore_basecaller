#include "uncertainty_feedback/core.h"

#include <algorithm>
#include <bit>
#include <charconv>
#include <cmath>
#include <limits>
#include <sstream>

namespace uncertainty_feedback {
namespace {
Json rows_for(const Json& planned, const Json& qualified) {
    validate_plan(planned);
    validate_completion(qualified, "uncertainty-feedback-graph/1");
    require(planned.at("plan_sha256") == qualified.at("plan_sha256"),
            "Graph/new plan identity differs");
    check(planned.at("joins"));
    check(qualified.at("qualified"));
    check(qualified.at("walks"));
    return read(qualified.at("qualified").at("path").get<std::string>());
}
Fields request_fields(const Json& planned, const Json& target) {
    const auto& w = target.at("window");
    const auto& evidence = target.at("evidence");
    for (const auto& key : {"score_pin", "metadata_pin", "parent_pin"}) {
        check(evidence.at(key));
    }
    for (const auto& item : evidence.at("reconstruction_metadata_pins")) {
        check(item);
    }
    const auto meta = metadata(evidence.at("metadata_pin").at("path").get<std::string>());
    Fields result = {{"plan_sha256", planned.at("plan_sha256").get<std::string>()},
                     {"query_index", std::to_string(integer(w.at("query_index")))},
                     {"parent", w.at("read_id").get<std::string>()},
                     {"chunk_index", std::to_string(integer(w.at("chunk_index")))},
                     {"t_start", std::to_string(integer(w.at("t_start")))},
                     {"t_end", std::to_string(integer(w.at("t_end")))},
                     {"initial_context", w.at("context").get<std::string>()},
                     {"initial_state", std::to_string(integer(target.at("initial_state")))},
                     {"sequence", w.at("stock").get<std::string>()},
                     {"token", meta.at("token")},
                     {"time_offset", meta.at("time_offset")},
                     {"T", meta.at("T")},
                     {"C", meta.at("C")}};
    add_pin(result, "tensor", evidence.at("score_pin"));
    add_pin(result, "metadata", evidence.at("metadata_pin"));
    return result;
}
}
void frame_requests(const Json& planned, const Json& qualified, const fs::path& output) {
    const auto rows = rows_for(planned, qualified),
               joins = read(planned.at("joins").at("path").get<std::string>());
    Json requests = Json::array();
    for (const auto& row : rows) {
        const auto index = integer(row.at("query_index"));
        const auto path = output / (std::to_string(index) + ".request.tsv");
        tabular(path, "context-scalar-request/1", request_fields(planned, joins.at(index)));
        requests.push_back({{"query_index", index}, {"request", pin(path)}});
    }
    complete(output, "uncertainty-feedback-scalar-requests/1",
             {{"plan", planned},
              {"plan_sha256", planned.at("plan_sha256")},
              {"qualified_graph", qualified},
              {"requests", requests}});
}
void frames(const Json& planned,
            const Json& qualified,
            const Json& scalar,
            const fs::path& output) {
    const auto rows = rows_for(planned, qualified),
               joins = read(planned.at("joins").at("path").get<std::string>());
    require(scalar.at("schema") == "uncertainty-feedback-scalars/1" &&
                    scalar.at("complete") == true &&
                    scalar.at("plan_sha256") == planned.at("plan_sha256"),
            "Independent scalar completion differs");
    validate_scalar_build(scalar);
    const auto scalar_inputs = scalar.at("sources");
    check(scalar.at("build_receipt"));
    const auto scalar_build = read(scalar.at("build_receipt").at("path").get<std::string>());
    require(scalar_build.at("complete") == true && scalar_build.at("exit_status") == 0 &&
                    std::find(scalar_build.at("produced_files").begin(),
                              scalar_build.at("produced_files").end(),
                              scalar.at("binary")) != scalar_build.at("produced_files").end(),
            "Independent scalar binary/build output linkage differs");
    std::map<std::size_t, Json> scalars;
    for (const auto& row : scalar.at("rows")) {
        require(scalars.emplace(integer(row.at("query_index")), row).second,
                "Duplicate scalar query");
    }
    require(scalars.size() == rows.size(), "Scalar/graph query population differs");
    Json built = Json::array();
    for (const auto& row : rows) {
        const auto index = integer(row.at("query_index"));
        const auto& target = joins.at(index);
        const auto& w = target.at("window");
        const auto& evidence = target.at("evidence");
        const auto& control = scalars.at(index);
        for (const auto& key : {"request", "scalar", "audit", "producer"}) {
            check(control.at(key));
        }
        const auto request_path = control.at("request").at("path").get<std::string>();
        std::istringstream request_input(text(request_path));
        std::string header;
        std::getline(request_input, header);
        require(header == "context-scalar-request/1", "Scalar request schema differs");
        Fields request;
        std::string line;
        while (std::getline(request_input, line)) {
            const auto pair = split(line);
            require(pair.size() == 2 && request.emplace(pair[0], pair[1]).second,
                    "Malformed scalar request");
        }
        require(request == request_fields(planned, target),
                "Scalar request does not match actual new base interval");
        const auto scalar_rows =
                split(text(control.at("scalar").at("path").get<std::string>(), 65536), '\n');
        require(scalar_rows.size() == 2 && scalar_rows.back().empty(),
                "Exactly one independent native base scalar required");
        const auto scalar_row = split(scalar_rows.front());
        require(scalar_row.size() == 2 && scalar_row[0] == request.at("sequence"),
                "Independent scalar does not score the explicit native base window");
        const auto audit =
                fields(control.at("audit").at("path").get<std::string>(), "context-scalar-audit/1");
        for (const auto& key : {"plan_sha256", "query_index", "parent", "chunk_index",
                                "tensor_sha256", "metadata_sha256", "t_start", "t_end",
                                "initial_context", "initial_state", "sequence"}) {
            require(audit.at(key) == request.at(key),
                    "Independent scalar bit audit targets another interval");
        }
        require(audit.at("request_sha256") ==
                                control.at("request").at("sha256").get<std::string>() &&
                        audit.at("value") == scalar_row[1] && audit.at("bits").size() == 16,
                "Independent scalar decimal/bit/request audit differs");
        std::uint64_t expected_bits{};
        const auto& bit_text = audit.at("bits");
        const auto parsed = std::from_chars(bit_text.data(), bit_text.data() + bit_text.size(),
                                            expected_bits, 16);
        require(parsed.ec == std::errc{} && parsed.ptr == bit_text.data() + bit_text.size(),
                "Independent scalar hex audit malformed");
        std::size_t used{};
        const auto decimal = scalar_row[1] == "impossible"
                                     ? -std::numeric_limits<double>::infinity()
                                     : std::stod(scalar_row[1], &used);
        require((scalar_row[1] == "impossible" ||
                 (used == scalar_row[1].size() && std::isfinite(decimal))) &&
                        std::bit_cast<std::uint64_t>(decimal) == expected_bits,
                "Independent scalar decimal does not preserve emitted bits");
        const auto producer = read(control.at("producer").at("path").get<std::string>());
        require(producer.at("schema") == "uncertainty-feedback-command/1" &&
                        producer.at("complete") == true && producer.at("exit_status") == 0 &&
                        producer.at("binary") == scalar.at("binary"),
                "Independent scalar producer receipt differs");
        for (const auto& item : producer.at("raw_files")) {
            check(item);
        }
        const auto scalar_directory =
                fs::path(control.at("scalar").at("path").get<std::string>()).parent_path();
        require(producer.at("argv") ==
                        Json::array({scalar.at("binary").at("path"), "score", "--request",
                                     control.at("request").at("path"), "--request-sha256",
                                     control.at("request").at("sha256"), "--output",
                                     scalar_directory.string()}),
                "Independent scalar exact request/argv differs");
        for (const auto& key : {"scalar", "audit"}) {
            require(std::find(producer.at("produced_files").begin(),
                              producer.at("produced_files").end(),
                              control.at(key)) != producer.at("produced_files").end(),
                    "Independent scalar output not bound by producer");
        }
        Json actual_inputs = Json::array({control.at("request"), scalar.at("build_receipt")});
        for (const auto& item : scalar_inputs) {
            actual_inputs.push_back(item);
        }
        validate_receipt(producer, scalar.at("binary"), producer.at("argv"), actual_inputs);
        require(producer.at("environment") == command_environment() &&
                        producer.at("runtime") == scalar.at("runtime") &&
                        producer.at("extra_runtimes") == Json::array({scalar.at("sha256_runtime")}),
                "Scalar actual environment/runtime closure differs");
        validate_runtime(producer.at("runtime"), scalar.at("binary"));
        validate_runtime(producer.at("extra_runtimes").at(0),
                         dependencies().at("scalar_toolchain").at("sha256"));
        const auto meta = metadata(evidence.at("metadata_pin").at("path").get<std::string>());
        const auto c = integer(w.at("chunk_start")), d = integer(w.at("chunk_end"));
        const auto& seq = meta.at("SEQ");
        const auto emitted = emissions(meta);
        require(integer(w.at("t_start")) == emitted.at(c) &&
                        integer(w.at("t_end")) == emitted.at(d) &&
                        integer(target.at("expanded_t_start")) == emitted.at(c) &&
                        integer(target.at("expanded_t_end")) == emitted.at(d + 10),
                "Base/future scalar interval mismatch");
        const auto directory = output / std::to_string(index);
        fs::create_directory(directory);
        const auto availability = row.at("availability").get<std::string>();
        const auto centers =
                availability == "usable" ? row.at("projection").at("centers") : Json::array();
        Fields identity = {
                {"plan_sha256", planned.at("plan_sha256").get<std::string>()},
                {"query_index", std::to_string(index)},
                {"parent", w.at("read_id").get<std::string>()},
                {"chunk_index", std::to_string(integer(w.at("chunk_index")))},
                {"tensor_sha256", evidence.at("score_pin").at("sha256").get<std::string>()},
                {"t_start", std::to_string(integer(w.at("t_start")))},
                {"t_end", std::to_string(integer(w.at("t_end")))},
                {"initial_context", w.at("context").get<std::string>()},
                {"initial_state", std::to_string(integer(target.at("initial_state")))},
                {"reverse", w.at("reverse") == true ? "1" : "0"},
                {"contig", w.at("contig").get<std::string>()},
                {"ref_start", std::to_string(integer(w.at("ref_start")))},
                {"ref_end", std::to_string(integer(w.at("ref_end")))},
                {"graph_sha256", qualified.at("walks").at("sha256").get<std::string>()},
                {"location_receipt_sha256",
                 target.at("location_receipt").at("sha256").get<std::string>()},
                {"location_sam_sha256", target.at("location_sam").at("sha256").get<std::string>()}};
        auto base_context = identity;
        std::size_t path_index{};
        for (const auto& center : centers) {
            base_context["sequence_" + std::to_string(path_index++)] =
                    seq.substr(c, 10) + center.get<std::string>() + seq.substr(d - 10, 10);
        }
        tabular(directory / "base-context.tsv", "context-paths/1", base_context);
        auto base = identity;
        base["location_status"] = availability;
        base["stock"] = w.at("stock").get<std::string>();
        add_pin(base, "tensor", evidence.at("score_pin"));
        add_pin(base, "metadata", evidence.at("metadata_pin"));
        add_pin(base, "location_receipt", target.at("location_receipt"));
        add_pin(base, "location_sam", target.at("location_sam"));
        add_pin(base, "context", pin(directory / "base-context.tsv"));
        add_pin(base, "scalar_controls", control.at("scalar"));
        tabular(directory / "base-frame.tsv", "context-frame/1", base);
        const auto base_pin = pin(directory / "base-frame.tsv");
        Fields context = {
                {"base_frame_sha256", base_pin.at("sha256").get<std::string>()},
                {"plan_sha256", identity.at("plan_sha256")},
                {"query_index", identity.at("query_index")},
                {"parent", identity.at("parent")},
                {"chunk_index", identity.at("chunk_index")},
                {"tensor_sha256", identity.at("tensor_sha256")},
                {"expanded_t_start", std::to_string(integer(target.at("expanded_t_start")))},
                {"expanded_t_end", std::to_string(integer(target.at("expanded_t_end")))},
                {"owned_start", std::to_string(integer(target.at("owned_start")))},
                {"owned_end", std::to_string(integer(target.at("owned_end")))},
                {"availability", availability},
                {"graph_sha256", identity.at("graph_sha256")}};
        path_index = 0;
        for (const auto& center : centers) {
            context["sequence_" + std::to_string(path_index++)] = center.get<std::string>();
        }
        tabular(directory / "context.tsv", "context-centers/2", context);
        Fields frame = {{"read_start", std::to_string(integer(w.at("read_start")))},
                        {"read_end", std::to_string(integer(w.at("read_end")))},
                        {"owned_start", context.at("owned_start")},
                        {"owned_end", context.at("owned_end")},
                        {"anchor_bases", "10"},
                        {"future_bases", "10"},
                        {"expanded_t_start", context.at("expanded_t_start")},
                        {"expanded_t_end", context.at("expanded_t_end")},
                        {"left_guard", seq.substr(c, 10)},
                        {"right_guard", seq.substr(d - 10, 20)},
                        {"native_center", seq.substr(c + 10, d - c - 20)},
                        {"retained_chunk_start",
                         std::to_string(integer(target.at("retained").at("chunk_base_start")))},
                        {"retained_chunk_end",
                         std::to_string(integer(target.at("retained").at("chunk_base_end")))}};
        add_pin(frame, "base_frame", base_pin);
        add_pin(frame, "parent", evidence.at("parent_pin"));
        add_pin(frame, "context", pin(directory / "context.tsv"));
        tabular(directory / "frame.tsv", "guarded-frame/2", frame);
        write(directory / "construction.json",
              {{"schema", "uncertainty-feedback-frame-construction/1"},
               {"new_plan_sha256", planned.at("plan_sha256")},
               {"original_window", w},
               {"target", target},
               {"frame", pin(directory / "frame.tsv")},
               {"base_frame", base_pin},
               {"graph", row},
               {"independent_scalar", control},
               {"reconstruction_metadata", evidence.at("reconstruction_metadata_pins")},
               {"parent", evidence.at("parent_pin")},
               {"owned_native", frame.at("native_center")},
               {"truth_input", false}});
        const auto t =
                integer(target.at("expanded_t_end")) - integer(target.at("expanded_t_start"));
        built.push_back({{"query_index", index},
                         {"read_id", w.at("read_id")},
                         {"frame", pin(directory / "frame.tsv")},
                         {"base_frame", base_pin},
                         {"construction", pin(directory / "construction.json")},
                         {"availability", availability},
                         {"context_exclusion", row.at("reason")},
                         {"work_bound",
                          {{"guide_cells", (t + 1) * 256 * 22},
                           {"phase_updates", t * 128 * 25},
                           {"context_cells",
                            t * 128 * std::max(std::size_t{1}, centers.size()) * 109 * 109},
                           {"scalar_cells", t * 139 * 257}}}});
    }
    write(output / "frames.json", built);
    complete(output, "uncertainty-feedback-frames/1",
             {{"plan", planned},
              {"plan_sha256", planned.at("plan_sha256")},
              {"frames", pin(output / "frames.json")},
              {"qualified_graph", qualified},
              {"scalar_completion", scalar},
              {"mandatory_old_cpp_scalar_check_unchanged", true}});
}
}
