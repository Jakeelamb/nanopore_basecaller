#include "archive_consumer/core.h"

#include <exception>
#include <iostream>
#include <set>

namespace {
using namespace archive_consumer;
int run(int argc, char** argv) {
    require(argc >= 2, "Command required");
    const std::string command = argv[1];
    require(command == "apply" || command == "controls", "Unknown command");
    require(argc >= 4 && argc % 2 == 0, "Option/value pairs required");
    std::map<std::string, std::string> options;
    for (int i = 2; i < argc; i += 2) {
        require(options.emplace(argv[i], argv[i + 1]).second, "Duplicate option");
    }
    const std::set<std::string> allowed =
            command == "apply" ? std::set<std::string>{"--request", "--request-sha256", "--output"}
                               : std::set<std::string>{"--scratch"};
    std::set<std::string> supplied;
    for (const auto& [key, value] : options) {
        static_cast<void>(value);
        supplied.insert(key);
    }
    require(supplied == allowed, "Unknown/missing command option");
    verify_sources();
    if (command == "controls") {
        return controls(options.at("--scratch"));
    }
    const auto request_pin = pin(options.at("--request"));
    require(request_pin.at("sha256") == options.at("--request-sha256"),
            "Root archive request pin differs");
    apply_request(request_pin, options.at("--output"));
    std::cout
            << Json{{"completion", pin(fs::path(options.at("--output")) / "complete.json")}}.dump()
            << '\n';
    return 0;
}
}
int main(int argc, char** argv) {
    try {
        return run(argc, argv);
    } catch (const std::exception& error) {
        std::cerr << "archive consumer rejected: " << error.what() << '\n';
        return 2;
    }
}
