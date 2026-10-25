#include "context_sample_feedback/runtime.h"
#include "sample_sources.h"
#include <fcntl.h>
#include <iostream>
#include <unistd.h>

namespace context_sample_feedback {
std::string source_json() {
    std::string result = "{\"compiled_sources\":[";
    bool first = true;
    for (const auto &source : sample_compiled_sources) {
        if (!first)
            result += ',';
        first = false;
        result += "{\"path\":" + context_study::json_string(source.path) +
                  ",\"size\":" + std::to_string(source.size) +
                  ",\"sha256\":" + context_study::json_string(source.sha256) + "}";
    }
    return result + "],\"compiler_path\":" + context_study::json_string(sample_compiler_path) +
           ",\"compiler_sha256\":" + context_study::json_string(sample_compiler_sha256) +
           ",\"formatter_path\":" + context_study::json_string(sample_formatter_path) +
           ",\"formatter_sha256\":" + context_study::json_string(sample_formatter_sha256) +
           ",\"compile_flags\":" + context_study::json_string(sample_compile_flags) + "}";
}
void verify_sources() {
    for (const auto &source : sample_compiled_sources)
        context_study::require(std::filesystem::file_size(source.path) == source.size &&
                                   context_study::file_sha256(source.path) == source.sha256,
                               "compiled sample source changed " + std::string(source.path));
    context_study::require(
        context_study::file_sha256(sample_compiler_path) == sample_compiler_sha256 &&
            context_study::file_sha256(sample_formatter_path) == sample_formatter_sha256,
        "sample toolchain changed");
    context_study::verify_compiled_sources();
}
context_study::Invocation begin(int argc, char **argv) {
    using context_study::require;
    require(argc >= 2, "sample command required");
    context_study::Invocation result;
    result.command = argv[1];
    require(result.command == "qualify" || result.command == "price" || result.command == "infer" ||
                result.command == "consume-frame" || result.command == "evaluate",
            "unknown sample command");
    require((argc - 2) % 2 == 0, "sample option requires value");
    const std::set<std::string> allowed{"--output",
                                        "--cases",
                                        "--cases-sha256",
                                        "--frames",
                                        "--frames-sha256",
                                        "--source-cases",
                                        "--source-cases-sha256",
                                        "--contexts",
                                        "--contexts-sha256",
                                        "--handshake",
                                        "--handshake-sha256",
                                        "--case-id",
                                        "--allow-exploratory",
                                        "--frame",
                                        "--frame-sha256",
                                        "--truth",
                                        "--truth-sha256",
                                        "--choices",
                                        "--choices-sha256"};
    for (int i = 2; i < argc; i += 2) {
        const std::string key(argv[i]);
        require(allowed.contains(key) && result.options.emplace(key, argv[i + 1]).second,
                "unknown/duplicate sample option " + key);
    }
    require(result.options.contains("--output"), "fresh --output required");
    result.output = result.options.at("--output");
    require(result.output.is_absolute() && !std::filesystem::exists(result.output),
            "fresh absolute sample output required");
    std::filesystem::create_directories(result.output);
    std::string attempt = "{\"schema\":\"context-sample-feedback-native-attempt/1\",\"argv\":[";
    for (int i = 0; i < argc; ++i) {
        if (i != 0)
            attempt += ',';
        attempt += context_study::json_string(argv[i]);
    }
    context_study::synced_write(result.output / "attempt.json",
                                attempt +
                                    "],\"binary\":" + context_study::pin_json("/proc/self/exe") +
                                    ",\"source\":" + source_json() + "}\n");
    verify_sources();
    return result;
}
void finish(const context_study::Invocation &invocation, const std::string &result,
            const std::vector<std::string> &files) {
    verify_sources();
    context_study::synced_write(invocation.output / "result.json", result + '\n');
    std::string complete =
        "{\"schema\":\"context-sample-feedback-native-complete/1\",\"complete\":true,\"attempt\":" +
        context_study::pin_json(invocation.output / "attempt.json") +
        ",\"result\":" + context_study::pin_json(invocation.output / "result.json") +
        ",\"source\":" + source_json() + ",\"files\":[";
    for (std::size_t i = 0; i < files.size(); ++i) {
        if (i != 0)
            complete += ',';
        complete += context_study::pin_json(invocation.output / files[i]);
    }
    complete += "],\"inputs\":[";
    bool first = true;
    for (const auto &[name, value] : invocation.options) {
        if (!name.ends_with("-sha256"))
            continue;
        const auto input = invocation.options.at(name.substr(0, name.size() - 7));
        context_study::require(context_study::file_sha256(input) == value,
                               "input changed before sample completion");
        if (!first)
            complete += ',';
        first = false;
        complete += context_study::pin_json(input);
    }
    context_study::synced_write(invocation.output / "complete.json", complete + "]}\n");
    const int descriptor = ::open(invocation.output.c_str(), O_RDONLY | O_DIRECTORY);
    context_study::require(descriptor >= 0, "completion directory open failed");
    const auto synced = ::fsync(descriptor);
    const auto closed = ::close(descriptor);
    context_study::require(synced == 0 && closed == 0, "completion directory sync failed");
    std::cout << "{\"completion\":" << context_study::pin_json(invocation.output / "complete.json")
              << "}\n";
}
}
