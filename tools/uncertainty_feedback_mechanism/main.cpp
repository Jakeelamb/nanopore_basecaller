#include "mechanism.h"

#include <fcntl.h>
#include <unistd.h>
#include <zlib.h>

#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <map>

namespace {
using namespace targeting_mechanism;
namespace fs = std::filesystem;
constexpr std::size_t maximum_metadata = 8 * 1024 * 1024;
constexpr std::size_t maximum_trace = 100 * 1024 * 1024;
constexpr std::size_t maximum_report = 1024 * 1024;
std::string bytes(const fs::path& path, std::size_t maximum) {
    require(path.is_absolute() && path.lexically_normal() == path && fs::is_regular_file(path) &&
                    !fs::is_symlink(path) && fs::file_size(path) <= maximum,
            "Absolute bounded nonsymlink input required");
    std::ifstream input(path, std::ios::binary);
    require(input.good(), "Cannot open input");
    std::string result{std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
    require(!input.bad() && result.size() <= maximum, "Input read failed or grew beyond bound");
    return result;
}
Json parse(const std::string& input) {
    std::vector<Strings> keys;
    const auto callback = [&keys](int depth, Json::parse_event_t event, Json& value) {
        require(depth <= 32, "JSON depth exceeds bound");
        if (event == Json::parse_event_t::object_start) {
            keys.emplace_back();
        } else if (event == Json::parse_event_t::key) {
            require(!keys.empty() && keys.back().insert(value.get<std::string>()).second,
                    "Duplicate JSON key");
        } else if (event == Json::parse_event_t::object_end) {
            keys.pop_back();
        }
        return true;
    };
    return Json::parse(input, callback, true, false);
}
std::string checked(const Json& pin, std::size_t maximum) {
    require(pin.is_object() && pin.size() == 3, "Exact FilePin required");
    const auto result = bytes(pin.at("path").get<std::string>(), maximum);
    require(natural(pin.at("size")) == result.size() && pin.at("sha256") == hash_text(result),
            "Input FilePin differs");
    return result;
}
// Qualified checkpoint_storage_v2.validate_storage runs before this observer.
// This reader binds the actual decompressed bytes to that same immutable Pin;
// it does not replace the qualified single-member/CRC/trailing-data validator.
std::string raw_trace(const Json& descriptor) {
    const auto& storage = descriptor.at("storage");
    require(storage.at("codec") == "gzip", "Only qualified lossless gzip storage accepted");
    const auto compressed = checked(storage.at("archive"), maximum_trace);
    require(compressed.size() >= 2 && static_cast<unsigned char>(compressed[0]) == 31 &&
                    static_cast<unsigned char>(compressed[1]) == 139,
            "Gzip magic differs; no transparent raw fallback");
    const auto expected = natural(storage.at("original").at("size"));
    require(expected <= maximum_trace, "Original trace exceeds sealed byte bound");
    const auto path = storage.at("archive").at("path").get<std::string>();
    gzFile input = gzopen(path.c_str(), "rb");
    require(input != nullptr, "Cannot open qualified archive");
    std::string result;
    std::array<char, 65536> block{};
    int count{};
    while ((count = gzread(input, block.data(), static_cast<unsigned>(block.size()))) > 0) {
        const auto size = static_cast<std::size_t>(count);
        if (size > expected - result.size()) {
            static_cast<void>(gzclose(input));
            throw std::invalid_argument("Decoded trace exceeds original size");
        }
        result.append(block.data(), size);
    }
    const bool eof = gzeof(input) != 0;
    const int closed = gzclose(input);
    require(count == 0 && eof && closed == Z_OK && result.size() == expected &&
                    hash_text(result) == storage.at("original").at("sha256").get<std::string>(),
            "Decoded bytes differ from original trace identity");
    return result;
}
void fresh(const fs::path& path, const std::string& text) {
    require(path.is_absolute() && path.lexically_normal() == path && text.size() <= maximum_report,
            "Absolute bounded fresh output required");
    const int fd = ::open(path.c_str(), O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW, 0600);
    require(fd >= 0, "Output exists or exclusive create failed");
    std::size_t offset{};
    while (offset < text.size()) {
        const auto count = ::write(fd, text.data() + offset, text.size() - offset);
        if (count <= 0) {
            static_cast<void>(::close(fd));
            throw std::runtime_error("Output write failed");
        }
        offset += static_cast<std::size_t>(count);
    }
    const int synced = ::fsync(fd), closed = ::close(fd);
    require(synced == 0 && closed == 0, "Output sync/close failed");
    const int directory = ::open(path.parent_path().c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    require(directory >= 0, "Output directory open failed");
    const int synced_directory = ::fsync(directory), closed_directory = ::close(directory);
    require(synced_directory == 0 && closed_directory == 0, "Output directory sync/close failed");
}
int run(int argc, char** argv) {
    require(argc == 7,
            "Usage: targeting-mechanism --request JSON --request-sha256 HASH --output JSON");
    std::map<std::string, std::string> options;
    for (int i = 1; i < argc; i += 2) {
        require(options.emplace(argv[i], argv[i + 1]).second, "Duplicate option");
    }
    require(options.contains("--request") && options.contains("--request-sha256") &&
                    options.contains("--output"),
            "Unknown or missing option");
    const auto payload = bytes(options.at("--request"), maximum_metadata);
    require(hash_text(payload) == options.at("--request-sha256"), "Request SHA256 differs");
    const auto request = parse(payload);
    require(request.at("schema") == "targeting-mechanism-request/1" &&
                    natural(request.at("query_index")) < 512 &&
                    request.at("storage_validated_by_exact_shared_helper") == true,
            "Request schema/query/qualified upstream storage differs");
    const auto native = parse(checked(request.at("native_result"), maximum_metadata));
    const auto proof = parse(checked(request.at("validated_case"), maximum_metadata));
    const auto& descriptor = request.at("trace_descriptor");
    require(proof.at("query_index") == request.at("query_index") &&
                    proof.at("current_storage").at("native_result") ==
                            request.at("native_result") &&
                    proof.at("trace_descriptor") == descriptor &&
                    proof.at("current_storage").at("lossless_current_gzip_verified") == true &&
                    descriptor.at("query_index") == request.at("query_index"),
            "Canonical validated case/request/result/trace join differs");
    const auto output = observe(native, request, raw_trace(descriptor));
    fresh(options.at("--output"), output.dump(2) + '\n');
    std::cout << Json{{"complete", true},
                      {"query_index", request.at("query_index")},
                      {"output", options.at("--output")}}
                         .dump()
              << '\n';
    return 0;
}
}
int main(int argc, char** argv) {
    try {
        return run(argc, argv);
    } catch (const std::exception& error) {
        std::cerr << "targeting mechanism rejected: " << error.what() << '\n';
        return 2;
    }
}
