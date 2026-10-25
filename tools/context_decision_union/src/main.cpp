#include "context_decision_union/union.h"
#include <fcntl.h>
#include <iostream>
#include <unistd.h>

int main(int argc, char **argv) {
    using namespace context_study;
    try {
        require(argc >= 2, "union command required");
        const std::string command = argv[1];
        if (command == "controls") {
            require(argc == 2, "union controls accepts no options");
            context_decision_union::verify_sources();
            std::cout << context_decision_union::controls() << " controls passed\n";
            context_decision_union::verify_sources();
            return 0;
        }
        require(command == "qualify" || command == "diagnose", "unknown union command");
        require((argc - 2) % 2 == 0, "union option value required");
        std::map<std::string, std::string> options;
        for (int i = 2; i < argc; i += 2) {
            const std::string key = argv[i];
            require((key == "--output" ||
                     (command == "diagnose" && (key == "--cases" || key == "--cases-sha256"))) &&
                        options.emplace(key, argv[i + 1]).second,
                    "unknown or duplicate union option " + key);
        }
        require(options.contains("--output") &&
                    (command == "qualify" ||
                     (options.contains("--cases") && options.contains("--cases-sha256") &&
                      digest(options.at("--cases-sha256")))),
                "required union options absent or invalid");
        const auto output = std::filesystem::absolute(options.at("--output")).lexically_normal();
        require(!std::filesystem::exists(output), "fresh union output directory required");
        std::filesystem::create_directories(output);
        std::string attempt = "{\"schema\":\"context-decision-union-attempt/1\",\"argv\":[";
        for (int i = 0; i < argc; ++i) {
            if (i != 0)
                attempt += ',';
            attempt += json_string(argv[i]);
        }
        attempt += "],\"binary\":" + pin_json("/proc/self/exe") +
                   ",\"source\":" + context_decision_union::source_json() + "}\n";
        synced_write(output / "attempt.json", attempt);
        context_decision_union::verify_sources();
        std::string result;
        std::vector<std::string> files;
        if (command == "qualify") {
            std::filesystem::current_path(output);
            result = "{\"schema\":\"context-decision-union-controls/1\",\"assertions\":" +
                     std::to_string(context_decision_union::controls()) + "}";
        } else {
            const auto packet =
                read_candidates(options.at("--cases"), options.at("--cases-sha256"));
            result = context_decision_union::diagnose(packet, output);
            files = {"historical.tsv", "decisions.tsv", "union-census.tsv"};
        }
        context_decision_union::verify_sources();
        synced_write(output / "result.json", result + '\n');
        std::string complete =
            "{\"schema\":\"context-decision-union-complete/1\",\"complete\":true,\"command\":" +
            json_string(command) + ",\"attempt\":" + pin_json(output / "attempt.json") +
            ",\"result\":" + pin_json(output / "result.json") + ",\"files\":[";
        for (std::size_t i = 0; i < files.size(); ++i) {
            if (i != 0)
                complete += ',';
            complete += pin_json(output / files[i]);
        }
        complete += "],\"inputs\":[";
        if (command == "diagnose") {
            require(file_sha256(options.at("--cases")) == options.at("--cases-sha256"),
                    "union candidate packet changed before completion");
            complete += pin_json(options.at("--cases"));
        }
        complete += "],\"source\":" + context_decision_union::source_json() + "}\n";
        synced_write(output / "complete.json", complete);
        const int descriptor = ::open(output.c_str(), O_RDONLY | O_DIRECTORY);
        require(descriptor >= 0, "union completion directory sync open failed");
        const auto synced = ::fsync(descriptor);
        const auto closed = ::close(descriptor);
        require(synced == 0 && closed == 0, "union completion directory sync failed");
        std::cout << "{\"completion\":" << pin_json(output / "complete.json") << "}\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
