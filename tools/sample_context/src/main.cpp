#include "sample_context/context.h"
#include "sample_sources.h"
#include <iostream>
#include <map>
#include <optional>
#include <set>

int main(int argc, char **argv) {
    namespace sc = sample_context;
    std::optional<std::filesystem::path> output;
    bool owned_output{};
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            std::cout << "sample-context qualify --output NEWDIR\nsample-context build --cases "
                         "FILE --cases-sha256 SHA --sam FILE --sam-sha256 SHA --output NEWDIR "
                         "[--context-role strict|exploratory_published_protocol]\n";
            return 0;
        }
        for (int i = 2; i + 1 < argc; ++i)
            if (std::string(argv[i]) == "--output") {
                sc::require(!output, "Duplicate output option");
                output = std::filesystem::weakly_canonical(argv[i + 1]);
            }
        sc::require(output.has_value(), "Fresh owned output required");
        const auto root = std::filesystem::path(sample_compiled::root) / "results/sample-context";
        const auto relative = output->lexically_relative(root);
        sc::require(!relative.empty() && relative != "." && !relative.is_absolute() &&
                        *relative.begin() != ".." && !std::filesystem::exists(*output),
                    "Output outside owned results or already exists");
        sc::require(std::filesystem::create_directories(*output),
                    "Fresh output directory collision");
        owned_output = true;
        const auto source = sc::source_json();
        std::string arguments = "[";
        for (int i = 0; i < argc; ++i) {
            if (i)
                arguments += ',';
            arguments += sc::quote(argv[i]);
        }
        arguments += ']';
        sc::fresh(*output / "attempt.json",
                  "{\"schema\":\"sample-context-attempt/1\",\"argv\":" + arguments +
                      ",\"binary\":" + sc::pin_json(sc::pin("/proc/self/exe")) +
                      ",\"started_utc\":" + sc::quote(sc::utc()) + ",\"source\":" + source + "}\n");
        sc::verify_sources();
        sc::require(argc >= 2, "Command required");
        const std::string command = argv[1];
        std::map<std::string, std::string> options;
        for (int i = 2; i < argc; i += 2) {
            sc::require(i + 1 < argc && options.emplace(argv[i], argv[i + 1]).second,
                        "Malformed/duplicate CLI option");
        }
        std::set<std::string> expected =
            command == "qualify" ? std::set<std::string>{"--output"}
                                 : std::set<std::string>{"--cases", "--cases-sha256", "--sam",
                                                         "--sam-sha256", "--output"};
        if (command == "build" && options.contains("--context-role"))
            expected.insert("--context-role");
        std::set<std::string> actual;
        for (const auto &[name, value] : options) {
            static_cast<void>(value);
            actual.insert(name);
        }
        sc::require((command == "qualify" || command == "build") && actual == expected,
                    "Unknown command/options");
        std::vector<sc::Pin> inputs;
        std::vector<std::string> files;
        std::string result;
        if (command == "qualify")
            result = sc::controls();
        else {
            const auto cases = sc::pin(options.at("--cases")), sam = sc::pin(options.at("--sam"));
            sc::require(cases.sha256 == options.at("--cases-sha256") &&
                            sam.sha256 == options.at("--sam-sha256") &&
                            cases.size <= 16 * 1024 * 1024,
                        "Cases/SAM input pin differs or packet exceeds 16 MiB");
            const auto packet = sc::read_packet(cases.path);
            const auto role =
                options.contains("--context-role") ? options.at("--context-role") : "strict";
            const auto exploratory =
                packet.lineage == sc::LineageMode::exploratory_published_protocol ||
                packet.lineage == sc::LineageMode::unavailable_exploratory;
            sc::require(role == (exploratory ? "exploratory_published_protocol" : "strict"),
                        "Packet role differs; exploratory paths require explicit --context-role "
                        "exploratory_published_protocol");
            inputs = {cases, sam};
            result = sc::build(packet, sam.path, *output);
            files = {"contexts.tsv",     "cases.tsv",   "families.tsv",
                     "observations.tsv", "lineage.tsv", "excluded.tsv"};
        }
        for (const auto &value : inputs)
            sc::check(value);
        sc::verify_sources();
        sc::fresh(*output / "result.json", result + '\n');
        std::string complete =
            "{\"schema\":\"sample-context-complete/1\",\"complete\":true,\"phase\":" +
            sc::quote(command) + ",\"attempt\":" + sc::pin_json(sc::pin(*output / "attempt.json")) +
            ",\"result\":" + sc::pin_json(sc::pin(*output / "result.json")) + ",\"files\":[";
        for (std::size_t i = 0; i < files.size(); ++i) {
            if (i)
                complete += ',';
            complete += sc::pin_json(sc::pin(*output / files[i]));
        }
        complete += "],\"inputs\":[";
        for (std::size_t i = 0; i < inputs.size(); ++i) {
            if (i)
                complete += ',';
            complete += sc::pin_json(inputs[i]);
        }
        complete += "],\"source\":" + source + ",\"finished_utc\":" + sc::quote(sc::utc()) +
                    ",\"biological_qualification\":false}\n";
        sc::fresh(*output / "complete.json", complete);
        std::cout << "{\"completion\":" << sc::pin_json(sc::pin(*output / "complete.json"))
                  << "}\n";
        return 0;
    } catch (const std::exception &error) {
        if (owned_output && output && std::filesystem::is_directory(*output))
            try {
                sc::fresh(*output / "failure.json",
                          "{\"complete\":false,\"error\":" + sc::quote(error.what()) +
                              ",\"finished_utc\":" + sc::quote(sc::utc()) + "}\n");
            } catch (const std::exception &projection) {
                std::cerr << "Failure projection: " << projection.what() << '\n';
            }
        std::cerr << "sample-context: " << error.what() << '\n';
        return 2;
    }
}
