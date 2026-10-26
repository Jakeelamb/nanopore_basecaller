#include "context_policy/protocol.h"

#include <fstream>
#include <iostream>
#include <stdexcept>

int main(int argc, char **argv) {
    try {
        if (argc != 4 || std::string(argv[1]) != "decide") {
            throw std::invalid_argument(
                "usage: context-policy decide REQUEST EXPECTED_REQUEST_SHA256");
        }
        context_policy::verify_compiled_sources();
        std::ifstream input(argv[2], std::ios::binary | std::ios::ate);
        if (!input.good() || input.tellg() < 0 || input.tellg() > 8388608) {
            throw std::invalid_argument("request unavailable or exceeds 8 MiB");
        }
        input.seekg(0);
        const std::string bytes{std::istreambuf_iterator<char>(input),
                                std::istreambuf_iterator<char>()};
        if (context_policy::digest(bytes) != argv[3]) {
            throw std::invalid_argument("request input hash changed");
        }
        const auto request = context_policy::parse(bytes);
        const auto batch_path = request.at("batch_pin").at("path").get<std::string>();
        std::ifstream batch_input(batch_path, std::ios::binary | std::ios::ate);
        if (!batch_input.good() || batch_input.tellg() < 0 || batch_input.tellg() > 8388608) {
            throw std::invalid_argument("candidate batch unavailable or exceeds 8 MiB");
        }
        batch_input.seekg(0);
        const std::string batch_bytes{std::istreambuf_iterator<char>(batch_input),
                                      std::istreambuf_iterator<char>()};
        std::cout << context_policy::decide_request(request, batch_bytes).dump() << '\n';
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "context-policy: " << error.what() << '\n';
        return 2;
    }
}
