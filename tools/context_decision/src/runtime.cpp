#include "context_decision/runtime.h"
#include "context_decision/decision.h"
#include "decision_sources.h"
#include <fcntl.h>
#include <iostream>
#include <unistd.h>

namespace context_decision {
std::map<std::string, std::string> parse_options(const std::string &command,
                                                 const std::vector<std::string> &arguments) {
    context_study::require(command == "qualify" || command == "price" || command == "replay",
                           "unknown decision command");
    context_study::require(arguments.size() % 2 == 0, "decision option value required");
    std::map<std::string, std::string> result;
    for (std::size_t i = 0; i < arguments.size(); i += 2) {
        const auto &key = arguments[i];
        const bool allowed = key == "--output" || (command != "qualify" &&
                                                   (key == "--cases" || key == "--cases-sha256" ||
                                                    key == "--scope" || key == "--max-cells"));
        context_study::require(allowed && result.emplace(key, arguments[i + 1]).second,
                               "unknown or duplicate decision option " + key);
    }
    context_study::require(result.contains("--output") &&
                               (command == "qualify" ||
                                (result.contains("--cases") && result.contains("--cases-sha256"))),
                           "required decision options absent");
    if (result.contains("--cases-sha256"))
        context_study::require(context_study::digest(result.at("--cases-sha256")),
                               "invalid decision input hash");
    for (const auto *name : {"--max-cells"})
        if (result.contains(name))
            static_cast<void>(context_study::natural(result.at(name)));
    if (result.contains("--max-cells"))
        context_study::require(context_study::natural(result.at("--max-cells")) > 0 &&
                                   context_study::natural(result.at("--max-cells")) <=
                                       maximum_work_cells,
                               "decision cell cap cannot exceed frozen maximum");
    if (result.contains("--scope"))
        context_study::require(
            result.at("--scope") == "query0" || result.at("--scope") == "first32" ||
                result.at("--scope") == "remaining" || result.at("--scope") == "all",
            "unknown decision scope");
    return result;
}
std::string source_json() {
    std::string result = "{\"compiled_sources\":[";
    bool first = true;
    for (const auto &source : decision_compiled_sources) {
        if (!first)
            result += ',';
        first = false;
        result += "{\"path\":" + context_study::json_string(source.path) +
                  ",\"size\":" + std::to_string(source.size) +
                  ",\"sha256\":" + context_study::json_string(source.sha256) + "}";
    }
    return result + "],\"compiler_path\":" + context_study::json_string(decision_compiler_path) +
           ",\"compiler_sha256\":" + context_study::json_string(decision_compiler_sha256) +
           ",\"compile_flags\":" + context_study::json_string(decision_compile_flags) +
           ",\"formatter_path\":" + context_study::json_string(decision_formatter_path) +
           ",\"formatter_sha256\":" + context_study::json_string(decision_formatter_sha256) + "}";
}
void verify_sources() {
    for (const auto &source : decision_compiled_sources)
        context_study::require(std::filesystem::is_regular_file(source.path) &&
                                   std::filesystem::file_size(source.path) == source.size &&
                                   context_study::file_sha256(source.path) == source.sha256,
                               "compiled decision source changed " + std::string(source.path));
    context_study::require(
        context_study::file_sha256(decision_compiler_path) == decision_compiler_sha256 &&
            context_study::file_sha256(decision_formatter_path) == decision_formatter_sha256,
        "decision compiler or formatter changed");
    context_study::verify_compiled_sources();
}
context_study::Invocation begin(int argc, char **argv) {
    context_study::Invocation result;
    for (int i = 2; i + 1 < argc; ++i)
        if (std::string(argv[i]) == "--output")
            result.output = argv[i + 1];
    context_study::require(!result.output.empty() && !std::filesystem::exists(result.output),
                           "fresh decision --output directory required");
    std::filesystem::create_directories(result.output);
    std::string attempt = "{\"schema\":\"context-decision-native-attempt/1\",\"argv\":[";
    for (int i = 0; i < argc; ++i) {
        if (i != 0)
            attempt += ',';
        attempt += context_study::json_string(argv[i]);
    }
    attempt += "],\"binary\":" + context_study::pin_json("/proc/self/exe") +
               ",\"source\":" + source_json() + "}\n";
    context_study::synced_write(result.output / "attempt.json", attempt);
    verify_sources();
    context_study::require(argc >= 2, "decision command required");
    result.command = argv[1];
    std::vector<std::string> arguments;
    for (int i = 2; i < argc; ++i)
        arguments.emplace_back(argv[i]);
    result.options = parse_options(result.command, arguments);
    return result;
}
void finish(const context_study::Invocation &invocation, const std::string &result,
            const std::vector<std::string> &files) {
    verify_sources();
    context_study::synced_write(invocation.output / "result.json", result + '\n');
    std::string complete =
        "{\"schema\":\"context-decision-native-complete/1\",\"complete\":true,\"command\":" +
        context_study::json_string(invocation.command) +
        ",\"attempt\":" + context_study::pin_json(invocation.output / "attempt.json") +
        ",\"result\":" + context_study::pin_json(invocation.output / "result.json") +
        ",\"files\":[";
    for (std::size_t i = 0; i < files.size(); ++i) {
        if (i != 0)
            complete += ',';
        complete += context_study::pin_json(invocation.output / files[i]);
    }
    complete += "],\"inputs\":[";
    if (invocation.options.contains("--cases")) {
        const auto &input = invocation.options.at("--cases");
        context_study::require(context_study::file_sha256(input) ==
                                   invocation.options.at("--cases-sha256"),
                               "decision input changed before completion");
        complete += context_study::pin_json(input);
    }
    complete += "],\"source\":" + source_json() + "}\n";
    context_study::synced_write(invocation.output / "complete.json", complete);
    const int descriptor = ::open(invocation.output.c_str(), O_RDONLY | O_DIRECTORY);
    context_study::require(descriptor >= 0, "decision completion directory sync open failed");
    const auto synced = ::fsync(descriptor);
    const auto closed = ::close(descriptor);
    context_study::require(synced == 0 && closed == 0, "decision completion directory sync failed");
    std::cout << "{\"completion\":" << context_study::pin_json(invocation.output / "complete.json")
              << "}\n";
}
}
