#include "prefix_feedback/session.h"
#include <iostream>

namespace prefix_feedback {
namespace {
Spec spec(const Json& value) {
    require(value.size() == 5 && value.at("policy").size() == 5, "session specification fields differ");
    const auto& policy = value.at("policy");
    return {value.at("read_id"), value.at("plan_sha256"), value.at("state_length"), value.at("stay_score"), {policy.at("beam_width"), policy.at("maximum_symbols"), policy.at("minimum_symbols"), policy.at("maximum_locations"), policy.at("context_weight")}};
}
}
}
int main(int argc, char** argv) {
    using namespace prefix_feedback;
    try {
        verify_sources();
        if (argc == 2 && std::string(argv[1]) == "controls") { return controls(); }
        if (argc == 2 && std::string(argv[1]) == "witness") { std::cout << Json{{"source_sha256", source_id()}, {"source", source_witness()}}.dump(2) << '\n'; return 0; }
        require(argc == 8 && std::string(argv[2]) == "--request" && std::string(argv[4]) == "--request-sha256" && std::string(argv[6]) == "--output", "advance|locations --request ABS --request-sha256 SHA --output NEW_ABS_DIR");
        const fs::path request_path(argv[3]);
        const auto expected = std::string(argv[5]);
        require(request_path.is_absolute() && file_digest(request_path) == expected, "request root differs");
        const auto request = read_json(request_path);
        const fs::path output(argv[7]);
        require(output.is_absolute() && !fs::exists(output) && fs::create_directory(output), "fresh output directory required");
        if (std::string(argv[1]) == "locations") {
            check_pin(request.at("paf"));
            auto result = parse_paf(read_text(request.at("paf").at("path").get<std::string>()), request.at("query"));
            fresh(output / "locations.json", result);
        } else {
            require(std::string(argv[1]) == "advance" && request.at("schema") == "prefix-advance/1" && request.at("source_sha256") == source_id() && request.size() == 7, "advance request fields/source differ");
            Session session;
            std::string previous;
            if (request.at("state").is_null()) { session = start(spec(request.at("spec"))); previous = state_id(session); }
            else {
                check_pin(request.at("state"));
                session = restore(read_json(request.at("state").at("path").get<std::string>()));
                previous = state_id(session);
                require(request.at("spec") == state_json(session).at("spec"), "state/spec differs");
            }
            require(request.at("expected_previous_state_sha256") == (request.at("state").is_null() ? Json(nullptr) : Json(previous)), "independently expected previous state differs");
            const auto block = load_block(request.at("block"), session.spec);
            const auto update = request.at("update").is_null() ? std::optional<Json>{} : std::optional<Json>{request.at("update")};
            advance(session, block, update);
            fresh(output / "state.json", state_json(session));
            fresh(output / "batch.json", batch(session, previous));
        }
        verify_sources();
        require(file_digest(request_path) == expected, "request changed during consumption");
        fresh(output / "complete.json", {{"schema", "prefix-complete/1"}, {"complete", true}, {"request", pin(request_path)}, {"source", source_witness()}, {"source_sha256", source_id()}});
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 2; }
}
