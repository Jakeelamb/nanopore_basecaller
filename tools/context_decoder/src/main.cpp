#include "compiled_sources.h"
#include "context_decoder/controls.h"
#include "context_decoder/decoder.h"
#include "context_decoder/io.h"

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cmath>
#include <exception>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef __FAST_MATH__
#error "Context decoder qualification prohibits fast math"
#endif

namespace {
using namespace context_decoder;
void require(bool condition, const char* message) {
    if (!condition) {
        throw std::invalid_argument(message);
    }
}
std::string pin_json(const std::filesystem::path& file) {
    const auto path = std::filesystem::canonical(file);
    return "{\"path\":" + quote(path.string()) +
           ",\"size\":" + std::to_string(std::filesystem::file_size(path)) +
           ",\"sha256\":" + quote(sha256(path)) + '}';
}
std::string sources_json() {
    std::string out = "[";
    bool first = true;
    for (const auto& source : compiled_sources) {
        require(std::filesystem::file_size(source.path) == source.size &&
                        sha256(source.path) == source.sha256,
                "compiled source changed");
        if (!first) {
            out += ',';
        }
        first = false;
        out += pin_json(source.path);
    }
    require(sha256(pinned_clang_format) == pinned_clang_format_sha256, "pinned formatter changed");
    return out + ']';
}
std::size_t integer(const std::string& value) {
    std::size_t used = 0;
    const auto number = std::stoull(value, &used);
    require(used == value.size() && value.find('-') == std::string::npos && number <= 1000000,
            "invalid integer option");
    return static_cast<std::size_t>(number);
}
double numeric(const std::string& value) {
    std::size_t used = 0;
    const auto number = std::stod(value, &used);
    require(used == value.size() && std::isfinite(number) && number >= 0.0,
            "invalid numeric option");
    return number;
}
int run(int argc, char** argv) {
    require(argc >= 2, "qualify or decode command required");
    const std::string command(argv[1]);
    if (command == "--help") {
        std::cout << "context-decoder qualify --output NEWDIR\n"
                     "context-decoder decode --frame TSV --frame-sha256 HASH --output NEWDIR "
                     "--beam N --min-symbols N --max-symbols N --weight W --deficit D --margin M\n";
        return 0;
    }
    require(command == "qualify" || command == "decode", "unknown command");
    require(argc % 2 == 0, "option value missing");
    std::map<std::string, std::string> options;
    for (int index = 2; index < argc; index += 2) {
        require(options.emplace(argv[index], argv[index + 1]).second, "duplicate option");
    }
    const std::set<std::string> allowed =
            command == "qualify"
                    ? std::set<std::string>{"--output"}
                    : std::set<std::string>{"--frame",  "--frame-sha256", "--output",
                                            "--beam",   "--min-symbols",  "--max-symbols",
                                            "--weight", "--deficit",      "--margin"};
    std::set<std::string> actual;
    for (const auto& [key, value] : options) {
        static_cast<void>(value);
        actual.insert(key);
    }
    require(actual == allowed, "unknown or missing option");
    const auto sources = sources_json();
    const std::filesystem::path directory(options.at("--output"));
    require(std::filesystem::create_directory(directory),
            "exclusive new output directory required");
    const auto output = std::filesystem::canonical(directory);
    const auto binary = std::filesystem::canonical("/proc/self/exe");
    std::ostringstream invocation;
    invocation << '[';
    for (int index = 0; index < argc; ++index) {
        if (index != 0) {
            invocation << ',';
        }
        invocation << quote(argv[index]);
    }
    invocation << ']';
    fresh(output / "attempt.json",
          "{\"schema\":\"context-decoder-attempt/1\",\"binary\":" + pin_json(binary) +
                  ",\"compiled_sources\":" + sources + ",\"argv\":" + invocation.str() +
                  ",\"compiler\":" + quote(compiler_path) +
                  ",\"compiler_version\":" + quote(__VERSION__) +
                  ",\"cpp_standard\":23,\"fast_math\":false,\"fp_contract\":\"off\"}");
    if (command == "qualify") {
        fresh(output / "result.json", run_controls());
    } else {
        const auto frame_path = std::filesystem::canonical(options.at("--frame"));
        const auto bound = load_frame(frame_path, options.at("--frame-sha256"));
        Policy policy;
        policy.beam_width = integer(options.at("--beam"));
        policy.min_symbols = integer(options.at("--min-symbols"));
        policy.max_symbols = integer(options.at("--max-symbols"));
        policy.context_weight = numeric(options.at("--weight"));
        policy.maximum_signal_deficit = numeric(options.at("--deficit"));
        policy.minimum_objective_margin = numeric(options.at("--margin"));
        const auto comparisons = check_retained_scalar(bound);
        const auto result = decode(bound.scores, bound.context, policy, bound.native);
        require(sha256(frame_path) == options.at("--frame-sha256"),
                "frame changed during decoding");
        std::string binding = "{";
        bool first = true;
        for (const auto& [key, value] : bound.binding) {
            if (!first) {
                binding += ',';
            }
            first = false;
            binding += quote(key) + ':' + quote(value);
        }
        binding += '}';
        fresh(output / "result.json",
              "{\"schema\":\"context-decoder-frame/1\",\"frame\":" + pin_json(frame_path) +
                      ",\"binding\":" + binding + ",\"retained_rust_scalar_bit_comparisons\":" +
                      std::to_string(comparisons) + ",\"outcome\":" + outcome_json(result) + '}');
    }
    fresh(output / "complete.json",
          "{\"schema\":\"context-decoder-complete/1\",\"complete\":true,\"files\":[" +
                  pin_json(output / "attempt.json") + ',' + pin_json(output / "result.json") +
                  "]}");
    const int directory_descriptor = ::open(output.c_str(), O_RDONLY | O_DIRECTORY);
    require(directory_descriptor >= 0, "output directory cannot be synced");
    const auto synced = ::fsync(directory_descriptor);
    const auto closed = ::close(directory_descriptor);
    require(synced == 0 && closed == 0, "output directory sync failed");
    std::cout << "{\"completion\":" << pin_json(output / "complete.json") << "}\n";
    return 0;
}
}
int main(int argc, char** argv) {
    try {
        return run(argc, argv);
    } catch (const std::exception& error) {
        std::cerr << "context-decoder: " << error.what() << '\n';
        return 1;
    }
}
