#include "uncertainty_feedback/core.h"

#include <exception>
#include <iostream>

namespace {
using namespace uncertainty_feedback;
int run(int argc, char** argv) {
    require(argc >= 2, "Command required");
    const std::string command = argv[1];
    if (command == "controls") {
        require(argc == 2, "Controls accepts no arguments");
        verify_sources();
        return controls();
    }
    require(argc >= 4 && argc % 2 == 0, "Option/value pairs required");
    std::map<std::string, std::string> options;
    for (int i = 2; i < argc; i += 2) {
        require(options.emplace(argv[i], argv[i + 1]).second, "Duplicate option");
    }
    const std::map<std::string, std::set<std::string>> allowed = {
            {"plan", {"--config", "--config-sha256", "--output"}},
            {"batch", {"--plan", "--plan-sha256", "--queries", "--output"}},
            {"qualify-graph",
             {"--config", "--config-sha256", "--plan", "--plan-sha256", "--batch", "--batch-sha256",
              "--receipt", "--receipt-sha256", "--raw", "--output"}},
            {"requests", {"--plan", "--plan-sha256", "--graph", "--graph-sha256", "--output"}},
            {"frames",
             {"--plan", "--plan-sha256", "--graph", "--graph-sha256", "--scalars",
              "--scalars-sha256", "--output"}},
            {"apply", {"--plan", "--plan-sha256", "--decoded", "--decoded-sha256", "--output"}},
            {"project", {"--request", "--request-sha256", "--output"}},
            {"seal-runtime", {"--request", "--request-sha256", "--output"}},
            {"exposure", {"--request", "--request-sha256", "--output"}}};
    require(allowed.contains(command), "Unknown command");
    std::set<std::string> supplied;
    for (const auto& [key, value] : options) {
        static_cast<void>(value);
        supplied.insert(key);
    }
    require(supplied == allowed.at(command), "Unknown/missing command option");
    verify_sources();
    const auto input = [&options](const std::string& name) {
        const fs::path path = options.at("--" + name);
        require(path.is_absolute() && sha256(path) == options.at("--" + name + "-sha256"),
                "Root input pin mismatch: " + name);
        const auto value = read(path);
        const std::map<std::string, std::string> schemas = {
                {"plan", "uncertainty-feedback-plan/1"},
                {"batch", "uncertainty-feedback-batch/1"},
                {"graph", "uncertainty-feedback-graph/1"},
                {"scalars", "uncertainty-feedback-scalars/1"},
                {"decoded", "uncertainty-feedback-decoded/1"},
                {"receipt", "uncertainty-feedback-command/1"}};
        if (schemas.contains(name)) {
            validate_completion(value, schemas.at(name));
        }
        if (name == "plan") {
            validate_plan(value);
        }
        if (name == "config") {
            require(value == read(connector_root() / "config/uncertainty-feedback-v1.json"),
                    "Frozen connector config differs");
        }
        return value;
    };
    const fs::path output = options.at("--output");
    output_directory(output);
    if (command == "plan") {
        plan(input("config"), output);
    } else if (command == "batch") {
        std::vector<std::size_t> ids;
        for (const auto& value : split(options.at("--queries"), ',')) {
            ids.push_back(natural(value));
        }
        batch(input("plan"), ids, output);
    } else if (command == "qualify-graph") {
        qualify_graph(input("config"), input("plan"), input("batch"), input("receipt"),
                      options.at("--raw"), output);
    } else if (command == "requests") {
        frame_requests(input("plan"), input("graph"), output);
    } else if (command == "frames") {
        frames(input("plan"), input("graph"), input("scalars"), output);
    } else if (command == "apply") {
        apply(input("plan"), input("decoded"), output);
    } else if (command == "exposure") {
        exposure(input("request"), output);
    } else if (command == "seal-runtime") {
        seal_runtime(input("request"), output);
    } else {
        const auto request = input("request");
        const auto result = project(request.at("window"), request.at("graph"));
        complete(output, "uncertainty-feedback-projection/1", result);
    }
    std::cout << Json{{"completion", pin(output / "complete.json")}}.dump() << '\n';
    return 0;
}
}
int main(int argc, char** argv) {
    try {
        return run(argc, argv);
    } catch (const std::exception& error) {
        std::cerr << "uncertainty-feedback: " << error.what() << '\n';
        return 1;
    }
}
