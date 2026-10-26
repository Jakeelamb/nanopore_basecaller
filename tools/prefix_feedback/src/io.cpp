#include "compiled_sources.h"
#include "prefix_feedback/session.h"

#include <fcntl.h>
#include <openssl/evp.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <limits>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>

namespace prefix_feedback {
void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::invalid_argument(message);
    }
}
namespace {
std::string finish(EVP_MD_CTX* context) {
    std::array<unsigned char, EVP_MAX_MD_SIZE> bytes{};
    unsigned int size{};
    require(EVP_DigestFinal_ex(context, bytes.data(), &size) == 1 && size == 32,
            "SHA256 finalization");
    std::ostringstream stream;
    stream << std::hex << std::setfill('0');
    for (unsigned int index = 0; index < size; ++index) {
        stream << std::setw(2) << static_cast<unsigned int>(bytes[index]);
    }
    return stream.str();
}
using Context = std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)>;
Context context() {
    Context result(EVP_MD_CTX_new(), EVP_MD_CTX_free);
    require(result != nullptr && EVP_DigestInit_ex(result.get(), EVP_sha256(), nullptr) == 1,
            "SHA256 initialization");
    return result;
}
std::vector<std::string> split(const std::string& line) {
    std::vector<std::string> result;
    std::istringstream stream(line);
    std::string field;
    while (std::getline(stream, field, '\t')) {
        result.push_back(field);
    }
    return result;
}
std::size_t natural(const std::string& value) {
    require(!value.empty() && value.find_first_not_of("0123456789") == std::string::npos,
            "unsigned integer required");
    return static_cast<std::size_t>(std::stoull(value));
}
double real(const std::string& value) {
    std::size_t used{};
    const auto result = std::stod(value, &used);
    require(used == value.size() && std::isfinite(result), "finite number required");
    return result;
}
double half(std::uint16_t bits) {
    const double sign = (bits & 0x8000U) == 0 ? 1.0 : -1.0;
    const int exponent = static_cast<int>((bits >> 10U) & 31U);
    require(exponent != 31, "nonfinite binary16 score");
    const double fraction = static_cast<double>(bits & 1023U);
    return exponent == 0 ? sign * std::ldexp(fraction, -24)
                         : sign * std::ldexp(1.0 + fraction / 1024.0, exponent - 15);
}
}
std::string digest(const std::string& bytes) {
    auto value = context();
    require(EVP_DigestUpdate(value.get(), bytes.data(), bytes.size()) == 1, "SHA256 text update");
    return finish(value.get());
}
std::string file_digest(const fs::path& path) {
    require(fs::is_regular_file(path) && !fs::is_symlink(path),
            "regular nonsymlink input required");
    auto value = context();
    std::ifstream input(path, std::ios::binary);
    require(input.good(), "cannot open input");
    std::array<char, 65536> buffer{};
    while (input) {
        input.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
        require(EVP_DigestUpdate(value.get(), buffer.data(),
                                 static_cast<std::size_t>(input.gcount())) == 1,
                "SHA256 file update");
    }
    require(input.eof(), "input read failed");
    return finish(value.get());
}
Json pin(const fs::path& path) {
    require(path.is_absolute(), "absolute pin required");
    return {{"path", path.string()}, {"size", fs::file_size(path)}, {"sha256", file_digest(path)}};
}
void check_pin(const Json& value) {
    require(value.is_object() && value.size() == 3 &&
                    pin(value.at("path").get<std::string>()) == value,
            "consumed input pin differs");
}
std::string read_text(const fs::path& path, std::size_t maximum) {
    require(fs::is_regular_file(path) && !fs::is_symlink(path) && fs::file_size(path) <= maximum,
            "input type/size bound");
    std::ifstream stream(path, std::ios::binary);
    std::ostringstream bytes;
    bytes << stream.rdbuf();
    require(!stream.bad(), "text input failed");
    return bytes.str();
}
Json read_json(const fs::path& path) { return Json::parse(read_text(path)); }
void fresh(const fs::path& path, const Json& value) {
    fresh_bytes(path, value.dump(2) + '\n');
}
void fresh_bytes(const fs::path& path, const std::string& bytes) {
    const int descriptor = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    require(descriptor >= 0, "fresh output required");
    std::size_t offset{};
    while (offset < bytes.size()) {
        const auto count = ::write(descriptor, bytes.data() + offset, bytes.size() - offset);
        if (count <= 0) {
            ::close(descriptor);
            throw std::runtime_error("output write failed");
        }
        offset += static_cast<std::size_t>(count);
    }
    const bool synced = ::fsync(descriptor) == 0;
    const bool closed = ::close(descriptor) == 0;
    require(synced && closed, "output sync failed");
}
Json source_witness() {
    Json sources = Json::array();
    for (const auto& source : compiled_sources) {
        sources.push_back({{"path", source.path}, {"sha256", source.sha256}});
    }
    return {{"root", compiled_root}, {"sources", sources}};
}
void verify_sources() {
    require(fs::current_path() == fs::path(compiled_root), "compiled source cwd differs");
    for (const auto& source : compiled_sources) {
        require(file_digest(source.path) == source.sha256, "compiled source-root corruption");
    }
}
std::string source_id() { return digest(source_witness().dump()); }
void dna(const std::string& value) {
    require(value.find_first_not_of("ACGT") == std::string::npos, "noncanonical DNA");
}
std::string reverse_complement(std::string value) {
    dna(value);
    std::reverse(value.begin(), value.end());
    for (auto& base : value) {
        base = std::string("TGCA")[std::string("ACGT").find(base)];
    }
    return value;
}
Block load_block(const Json& request, const Spec& spec) {
    const std::set<std::string> allowed{"tensor",
                                        "read_id",
                                        "parent_id",
                                        "chunk_index",
                                        "block_index",
                                        "row_begin",
                                        "row_end",
                                        "chunk_row_begin",
                                        "chunk_row_end",
                                        "available_score_end",
                                        "available_signal_end",
                                        "chunk_signal_begin",
                                        "chunk_signal_end",
                                        "declared_chunk_lookahead",
                                        "orientation",
                                        "release_receipt"};
    std::set<std::string> actual;
    for (const auto& [key, value] : request.items()) {
        static_cast<void>(value);
        actual.insert(key);
    }
    require(actual == allowed, "block fields differ; completed calls/guards forbidden");
    require(request.at("read_id") == spec.read_id && request.at("parent_id") == spec.read_id &&
                    request.at("orientation") == "signal-forward",
            "block parent/orientation differs");
    check_pin(request.at("tensor"));
    check_pin(request.at("release_receipt"));
    const auto release = read_json(request.at("release_receipt").at("path").get<std::string>());
    require(release.at("schema") == "prefix-release/1" && release.at("read_id") == spec.read_id &&
                    release.at("tensor") == request.at("tensor"),
            "released tensor provenance differs");
    auto binding_without_receipt = request;
    binding_without_receipt.erase("release_receipt");
    require(release.at("binding") == binding_without_receipt, "released endpoint/geometry differs");
    const auto path = request.at("tensor").at("path").get<std::string>();
    std::ifstream stream(path, std::ios::binary);
    std::string line;
    require(static_cast<bool>(std::getline(stream, line)) && line.size() < 4096,
            "DGS header absent/bound");
    const auto fields = split(line);
    require(fields.size() == 15 && fields[0] == "DGS1" &&
                    natural(fields[2]) == (std::size_t{1} << (2 * (spec.state_length + 1))) &&
                    fields[3] == std::to_string(spec.state_length) && fields[4] == "6" &&
                    real(fields[5]) == spec.stay_score,
            "DGS geometry/options differ");
    const auto rows = natural(fields[1]);
    const auto channels = natural(fields[2]);
    const auto clamp = real(fields[11]);
    require(clamp == 0.0 || clamp == 5.0, "unsupported DGS clamp");
    Block block{request,
                request.at("row_begin").get<std::size_t>(),
                request.at("row_end").get<std::size_t>(),
                {}};
    require(block.row_begin < block.row_end && rows == block.row_end - block.row_begin &&
                    rows <= 512 &&
                    request.at("chunk_row_end").get<std::size_t>() -
                                    request.at("chunk_row_begin").get<std::size_t>() ==
                            rows,
            "released row bound");
    require(fs::file_size(path) == line.size() + 1 + rows * channels * 2, "DGS byte size differs");
    require(request.at("available_score_end") == block.row_end &&
                    request.at("available_signal_end") == request.at("chunk_signal_end") &&
                    request.at("chunk_signal_begin").get<std::size_t>() <
                            request.at("chunk_signal_end").get<std::size_t>(),
            "available endpoint differs");
    require(request.at("declared_chunk_lookahead").get<std::size_t>() ==
                    request.at("chunk_signal_end").get<std::size_t>() -
                            request.at("chunk_signal_begin").get<std::size_t>(),
            "chunk lookahead disclosure differs");
    block.scores.reserve(rows * channels);
    for (std::size_t index = 0; index < rows * channels; ++index) {
        std::array<unsigned char, 2> bytes{};
        stream.read(reinterpret_cast<char*>(bytes.data()), 2);
        require(stream.gcount() == 2, "short DGS payload");
        const auto bits = static_cast<std::uint16_t>(static_cast<unsigned int>(bytes[0]) |
                                                     (static_cast<unsigned int>(bytes[1]) << 8U));
        const auto value = half(bits);
        block.scores.push_back(clamp == 0.0 ? value : std::clamp(value, -clamp, clamp));
    }
    check_pin(request.at("tensor"));
    return block;
}
}
