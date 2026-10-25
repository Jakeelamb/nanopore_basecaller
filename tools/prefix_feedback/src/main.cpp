#include "context_decoder/io.h"
#include "prefix_feedback/feedback.h"

#include <fcntl.h>
#include <unistd.h>

#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

namespace {
void sync_directory(const std::filesystem::path& path) {
    const int descriptor = ::open(path.c_str(), O_RDONLY | O_DIRECTORY);
    prefix_feedback::require(descriptor >= 0, "cannot open owned output directory");
    const auto status = ::fsync(descriptor);
    const auto closed = ::close(descriptor);
    prefix_feedback::require(status == 0 && closed == 0, "directory sync/close failed");
}
}

int main(int argc, char** argv) {
    std::filesystem::path output;
    bool owns_output{};
    try {
        const std::vector<std::string> args(argv, argv + argc);
        prefix_feedback::require(args.size() == 12 && args[1] == "decode" &&
                                         args[2] == "--packet" && args[4] == "--packet-sha256" &&
                                         args[6] == "--session" && args[8] == "--session-sha256" &&
                                         args[10] == "--output",
                                 "usage: prefix-feedback decode --packet FILE --packet-sha256 SHA "
                                 "--session FILE --session-sha256 SHA --output NEWDIR");
        output = args[11];
        const std::filesystem::path root(
                "/home/jake/Projects/nanopore_basecaller-context-feedback-causal/results/"
                "context-feedback");
        const auto relative = output.lexically_normal().lexically_relative(root);
        prefix_feedback::require(output.is_absolute() && !relative.empty() &&
                                         !relative.string().starts_with("..") &&
                                         std::filesystem::create_directory(output),
                                 "fresh absolute output directory required");
        owns_output = true;
        const auto source = prefix_feedback::source_json();
        const auto binary = std::filesystem::canonical("/proc/self/exe");
        std::string command = "[";
        for (std::size_t index = 0; index < args.size(); ++index) {
            command += (index == 0 ? "" : ",") + context_decoder::quote(args[index]);
        }
        command += "]";
        context_decoder::fresh(
                output / "attempt.json",
                "{\"argv\":" + command + ",\"sources\":" + source +
                        ",\"binary\":{\"path\":" + context_decoder::quote(binary.string()) +
                        ",\"sha256\":" + context_decoder::quote(context_decoder::sha256(binary)) +
                        "},\"packet_sha256\":" + context_decoder::quote(args[5]) +
                        ",\"session_sha256\":" + context_decoder::quote(args[9]) + "}");
        sync_directory(output);
        const auto window = prefix_feedback::load_window(args[3], args[5]);
        auto session = prefix_feedback::load_session(args[7], args[9], window);
        const auto result = prefix_feedback::decode(window, session);
        context_decoder::fresh(output / "result.json", result);
        context_decoder::fresh(
                output / "complete.json",
                "{\"schema\":\"prefix-feedback-complete/1\",\"complete\":true,\"sources\":" +
                        source + ",\"result_sha256\":" +
                        context_decoder::quote(context_decoder::sha256(output / "result.json")) +
                        ",\"attempt_sha256\":" +
                        context_decoder::quote(context_decoder::sha256(output / "attempt.json")) +
                        "}");
        sync_directory(output);
        std::cout << "{\"completion\":{\"path\":"
                  << context_decoder::quote((output / "complete.json").string())
                  << ",\"size\":" << std::filesystem::file_size(output / "complete.json")
                  << ",\"sha256\":"
                  << context_decoder::quote(context_decoder::sha256(output / "complete.json"))
                  << "}}\n";
        return 0;
    } catch (const std::exception& error) {
        if (owns_output && std::filesystem::is_directory(output) &&
            std::filesystem::exists(output / "attempt.json") &&
            !std::filesystem::exists(output / "complete.json")) {
            try {
                context_decoder::fresh(output / "failure.json",
                                       "{\"complete\":false,\"error\":" +
                                               context_decoder::quote(error.what()) + "}");
                sync_directory(output);
            } catch (const std::exception&) {
                // The raw stderr and outer recorder remain the failure authority.
            }
        }
        std::cerr << "prefix-feedback: " << error.what() << '\n';
        return 2;
    }
}
