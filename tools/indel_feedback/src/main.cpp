#include "indel_feedback/core.h"

#include <iostream>

int main(int argc, char **argv) {
  using namespace indel_feedback;
  try {
    verify_sources();
    if (argc == 2 && std::string(argv[1]) == "controls") {
      controls();
      return 0;
    }
    require(argc == 5, "usage: indel-feedback classify|propose REQUEST "
                       "EXPECTED_REQUEST_SHA256 NEW_OUTPUT");
    const fs::path request_path(argv[2]), output_path(argv[4]);
    require(request_path.is_absolute() && output_path.is_absolute() &&
                !fs::exists(output_path),
            "absolute request/new output required");
    require(file_digest(request_path) == argv[3],
            "independent request hash differs");
    const auto request = read_json(request_path);
    const std::string command(argv[1]);
    require(command == "classify" || command == "propose", "unknown command");
    auto result = command == "classify" ? classify_request(request)
                                        : propose_request(request);
    require(file_digest(request_path) == argv[3],
            "request changed during consumption");
    verify_sources();
    result["request_sha256"] = argv[3];
    result["source_files"] = source_witness();
    result["complete"] = true;
    fresh(output_path, result.dump(2) + '\n');
    std::cout << "completed " << command << '\n';
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "indel-feedback: " << error.what() << '\n';
    return 1;
  }
}
