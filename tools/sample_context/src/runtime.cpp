#include "sample_context/context.h"
#include "sample_sources.h"
#include <array>
#include <cerrno>
#include <chrono>
#include <ctime>
#include <fcntl.h>
#include <fstream>
#include <iomanip>
#include <memory>
#include <openssl/evp.h>
#include <sstream>
#include <stdexcept>
#include <unistd.h>

namespace sample_context {
namespace {
using Digest = std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)>;
Digest begin_digest() {
    Digest context(EVP_MD_CTX_new(), EVP_MD_CTX_free);
    require(context && EVP_DigestInit_ex(context.get(), EVP_sha256(), nullptr) == 1,
            "SHA256 initialization failed");
    return context;
}
std::string finish(Digest &context) {
    std::array<unsigned char, EVP_MAX_MD_SIZE> bytes{};
    unsigned length{};
    require(EVP_DigestFinal_ex(context.get(), bytes.data(), &length) == 1 && length == 32,
            "SHA256 finalization failed");
    std::ostringstream out;
    for (unsigned i = 0; i < length; ++i)
        out << std::hex << std::setfill('0') << std::setw(2) << static_cast<unsigned>(bytes[i]);
    return out.str();
}
}
std::string sha256(std::string_view value) {
    auto context = begin_digest();
    require(EVP_DigestUpdate(context.get(), value.data(), value.size()) == 1,
            "SHA256 update failed");
    return finish(context);
}
Pin pin(const std::filesystem::path &path) {
    const auto actual = std::filesystem::canonical(path);
    const auto size = std::filesystem::file_size(actual);
    std::ifstream stream(actual, std::ios::binary);
    require(stream.good(), "Cannot read pinned file: " + actual.string());
    auto context = begin_digest();
    std::array<char, 1024 * 1024> block{};
    while (stream) {
        stream.read(block.data(), static_cast<std::streamsize>(block.size()));
        const auto n = stream.gcount();
        if (n > 0)
            require(EVP_DigestUpdate(context.get(), block.data(), static_cast<std::size_t>(n)) == 1,
                    "SHA256 file update failed");
    }
    require(!stream.bad() && std::filesystem::file_size(actual) == size,
            "Pinned file changed/read failed");
    return {actual.string(), finish(context), size};
}
void check(const Pin &expected) {
    require(pin(expected.path) == expected, "Missing or changed input: " + expected.path);
}
std::string quote(std::string_view value) {
    std::ostringstream out;
    out << '"';
    for (const auto ch : value) {
        if (ch == '"' || ch == '\\')
            out << '\\' << ch;
        else if (ch == '\n')
            out << "\\n";
        else if (ch == '\t')
            out << "\\t";
        else if (ch == '\r')
            out << "\\r";
        else {
            require(static_cast<unsigned char>(ch) >= 32U, "Control byte in JSON field");
            out << ch;
        }
    }
    return out.str() + '"';
}
std::string pin_json(const Pin &value) {
    return "{\"path\":" + quote(value.path) + ",\"size\":" + std::to_string(value.size) +
           ",\"sha256\":" + quote(value.sha256) + "}";
}
void fresh(const std::filesystem::path &path, std::string_view data) {
    const auto fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0600);
    require(fd >= 0, "Exclusive output open failed");
    std::size_t at{};
    while (at < data.size()) {
        const auto result = ::write(fd, data.data() + at, data.size() - at);
        if (result < 0 && errno == EINTR)
            continue;
        if (result <= 0) {
            ::close(fd);
            throw std::runtime_error("Output write failed");
        }
        at += static_cast<std::size_t>(result);
    }
    const auto synced = ::fsync(fd), closed = ::close(fd);
    require(synced == 0 && closed == 0, "Output file sync failed");
    const auto directory = ::open(path.parent_path().c_str(), O_RDONLY | O_DIRECTORY);
    require(directory >= 0, "Output directory open failed");
    const auto directory_synced = ::fsync(directory), directory_closed = ::close(directory);
    require(directory_synced == 0 && directory_closed == 0, "Output directory sync failed");
}
std::string utc() {
    const auto now = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    std::tm converted{};
    require(::gmtime_r(&now, &converted) != nullptr, "UTC conversion failed");
    std::ostringstream out;
    out << std::put_time(&converted, "%Y-%m-%dT%H:%M:%SZ");
    return out.str();
}
std::string source_json() {
    std::string result = "{\"compiled_sources\":[";
    bool comma{};
    for (const auto &value : sample_compiled::sources) {
        if (comma)
            result += ',';
        comma = true;
        result += pin_json({value.path, value.sha256, value.size});
    }
    return result + "],\"compiler_path\":" + quote(sample_compiled::compiler_path) +
           ",\"compiler_sha256\":" + quote(sample_compiled::compiler_sha256) +
           ",\"compile_flags\":" + quote(sample_compiled::compile_flags) +
           ",\"formatter_path\":" + quote(sample_compiled::formatter_path) +
           ",\"formatter_sha256\":" + quote(sample_compiled::formatter_sha256) + "}";
}
void verify_sources() {
    for (const auto &value : sample_compiled::sources)
        check({value.path, value.sha256, value.size});
    require(pin(sample_compiled::compiler_path).sha256 == sample_compiled::compiler_sha256,
            "Compiler changed");
    require(pin(sample_compiled::formatter_path).sha256 == sample_compiled::formatter_sha256,
            "Formatter changed");
}
}
