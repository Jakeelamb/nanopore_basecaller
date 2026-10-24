#include "context_decoder/io.h"

#include <fcntl.h>
#include <openssl/evp.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <limits>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace context_decoder {
namespace {
void require(bool condition, const char* message) {
    if (!condition) {
        throw std::invalid_argument(message);
    }
}
std::vector<std::string> split(const std::string& line) {
    std::vector<std::string> values;
    std::size_t start = 0;
    while (true) {
        const auto end = line.find('\t', start);
        values.push_back(line.substr(start, end == std::string::npos ? end : end - start));
        if (end == std::string::npos) {
            return values;
        }
        start = end + 1;
    }
}
std::size_t number(const std::string& text) {
    std::size_t value = 0;
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    require(result.ec == std::errc{} && result.ptr == text.data() + text.size(),
            "invalid unsigned field");
    return value;
}
double real(const std::string& text) {
    std::size_t used = 0;
    const auto value = std::stod(text, &used);
    require(used == text.size() && std::isfinite(value), "invalid finite numeric field");
    return value;
}
double half(std::uint16_t bits) {
    const auto sign = (bits & 0x8000U) == 0 ? 1.0 : -1.0;
    const auto exponent = static_cast<int>((bits >> 10U) & 31U);
    const auto fraction = static_cast<double>(bits & 1023U);
    require(exponent != 31, "nonfinite DGS1 half payload");
    if (exponent == 0) {
        return sign * fraction * std::pow(2.0, -24);
    }
    return sign * (1.0 + fraction / 1024.0) * std::pow(2.0, exponent - 15);
}
void same(const Fields& a, const Fields& b, const std::string& key) {
    require(a.at(key) == b.at(key), "context/frame linkage mismatch");
}
void file_pin(const Fields& f, const std::string& prefix) {
    const std::filesystem::path path(f.at(prefix + "_path"));
    require(path.is_absolute() && std::filesystem::is_regular_file(path),
            "absolute input file required");
    require(std::filesystem::file_size(path) == number(f.at(prefix + "_size")),
            "input byte size changed");
    require(sha256(path) == f.at(prefix + "_sha256"), "consumed input hash changed");
}
}

std::string sha256(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    require(input.good(), "cannot open hashed file");
    std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> context(EVP_MD_CTX_new(),
                                                                    EVP_MD_CTX_free);
    require(context != nullptr && EVP_DigestInit_ex(context.get(), EVP_sha256(), nullptr) == 1,
            "SHA256 initialization failed");
    std::array<char, 65536> buffer{};
    while (input) {
        input.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
        const auto count = input.gcount();
        require(count >= 0, "invalid input read");
        require(EVP_DigestUpdate(context.get(), buffer.data(), static_cast<std::size_t>(count)) ==
                        1,
                "SHA256 update failed");
    }
    require(input.eof(), "input read failed");
    std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
    unsigned int size = 0;
    require(EVP_DigestFinal_ex(context.get(), digest.data(), &size) == 1 && size == 32,
            "SHA256 finalization failed");
    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (std::size_t i = 0; i < size; ++i) {
        out << std::setw(2) << static_cast<unsigned int>(digest[i]);
    }
    return out.str();
}
Fields fields(const std::filesystem::path& path, const std::string& schema) {
    std::ifstream input(path);
    require(input.good(), "cannot open metadata");
    std::string line;
    require(static_cast<bool>(std::getline(input, line)) &&
                    (line == schema || line == "format\t" + schema),
            "metadata schema mismatch");
    Fields result;
    if (line == "format\t" + schema) {
        result.emplace("format", schema);
    }
    while (std::getline(input, line)) {
        const auto values = split(line);
        require(values.size() == 2 && !values[0].empty() && line.find('\r') == std::string::npos,
                "malformed metadata field");
        require(result.emplace(values[0], values[1]).second, "duplicate metadata field");
    }
    require(input.eof(), "metadata read failed");
    return result;
}
BoundFrame load_frame(const std::filesystem::path& manifest, const std::string& expected_hash) {
    require(sha256(manifest) == expected_hash, "frame constructor output changed");
    auto f = fields(manifest, "context-frame/1");
    const std::set<std::string> allowed{"plan_sha256",
                                        "query_index",
                                        "parent",
                                        "chunk_index",
                                        "tensor_path",
                                        "tensor_size",
                                        "tensor_sha256",
                                        "metadata_path",
                                        "metadata_size",
                                        "metadata_sha256",
                                        "t_start",
                                        "t_end",
                                        "initial_context",
                                        "initial_state",
                                        "reverse",
                                        "contig",
                                        "ref_start",
                                        "ref_end",
                                        "location_receipt_path",
                                        "location_receipt_size",
                                        "location_receipt_sha256",
                                        "location_sam_path",
                                        "location_sam_size",
                                        "location_sam_sha256",
                                        "location_status",
                                        "context_path",
                                        "context_size",
                                        "context_sha256",
                                        "graph_sha256",
                                        "stock",
                                        "scalar_controls_path",
                                        "scalar_controls_size",
                                        "scalar_controls_sha256"};
    std::set<std::string> supplied;
    for (const auto& [key, value] : f) {
        static_cast<void>(value);
        supplied.insert(key);
    }
    require(supplied == allowed, "unknown or missing inference field");
    for (const auto& key :
         {"tensor", "metadata", "location_receipt", "location_sam", "context", "scalar_controls"}) {
        file_pin(f, key);
    }
    require(f.at("reverse") == "0" || f.at("reverse") == "1", "invalid orientation");
    const auto meta = fields(f.at("metadata_path"), "DGM1");
    require(meta.at("read_id") == f.at("parent") && meta.at("chunk_index") == f.at("chunk_index"),
            "metadata parent/chunk mismatch");
    const auto tensor_name = std::filesystem::path(f.at("tensor_path")).filename().string();
    require(meta.at("score_file") == tensor_name, "tensor/metadata filename mismatch");
    std::ifstream tensor(f.at("tensor_path"), std::ios::binary);
    std::string header;
    require(static_cast<bool>(std::getline(tensor, header)), "DGS1 header missing");
    const auto h = split(header);
    require(h.size() == 15 && h[0] == "DGS1" && h[2] == "1024" && h[3] == "4" && h[4] == "6",
            "unsupported DGS1 geometry");
    require(h[13] == meta.at("token") && h[12] == meta.at("time_offset") && h[1] == meta.at("T") &&
                    h[2] == meta.at("C"),
            "DGS1 producer metadata mismatch");
    require(tensor_name == h[13] + "_s" + h[14] + ".scores", "DGS1 token/slot mismatch");
    const auto total_t = number(h[1]);
    require(total_t > 0 && total_t <= 1000000, "DGS1 time bound");
    const auto start = number(f.at("t_start"));
    const auto end = number(f.at("t_end"));
    require(start < end && end <= total_t && end - start <= 256, "score interval bounds");
    require(std::filesystem::file_size(f.at("tensor_path")) ==
                    header.size() + 1 + total_t * 1024 * 2,
            "DGS1 consumed payload size mismatch");
    const auto clamp = real(h[11]);
    require(clamp == 0.0 || clamp == 5.0, "unsupported DGS1 clamp");
    Frame scores{end - start, 4, number(f.at("initial_state")), real(h[5]), {}};
    const auto initial = f.at("initial_context");
    require(initial.size() == 4, "initial k4 context missing");
    std::size_t computed = 0;
    for (const char character : initial) {
        std::size_t next = 0;
        static_cast<void>(transition(computed, static_cast<unsigned char>(character), 4, next));
        computed = next;
    }
    require(computed == scores.initial_state, "initial state/context mismatch");
    tensor.seekg(static_cast<std::streamoff>(header.size() + 1 + start * 1024 * 2));
    scores.scores.reserve(scores.timesteps * 1024);
    for (std::size_t i = 0; i < scores.timesteps * 1024; ++i) {
        std::array<unsigned char, 2> bytes{};
        tensor.read(reinterpret_cast<char*>(bytes.data()), 2);
        require(tensor.gcount() == 2, "truncated consumed tensor interval");
        const auto bits = static_cast<std::uint16_t>(static_cast<unsigned int>(bytes[0]) |
                                                     (static_cast<unsigned int>(bytes[1]) << 8U));
        const auto value = half(bits);
        scores.scores.push_back(clamp == 0.0 ? value : std::clamp(value, -clamp, clamp));
    }
    auto context_fields = fields(f.at("context_path"), "context-paths/1");
    for (const auto& key :
         {"plan_sha256", "query_index", "parent", "chunk_index", "tensor_sha256", "t_start",
          "t_end", "initial_context", "initial_state", "reverse", "contig", "ref_start", "ref_end",
          "graph_sha256", "location_receipt_sha256", "location_sam_sha256"}) {
        same(f, context_fields, key);
        context_fields.erase(key);
    }
    RetrievedContext context;
    if (f.at("location_status") == "usable") {
        context.availability = Availability::usable;
    } else if (f.at("location_status") == "ambiguous") {
        context.availability = Availability::ambiguous;
    } else {
        require(f.at("location_status") == "missing", "invalid location status");
        context.availability = Availability::missing;
    }
    for (const auto& [key, sequence] : context_fields) {
        require(key.starts_with("sequence_"), "unknown context inference field");
        context.sequences.push_back(sequence);
    }
    static_cast<void>(canonical_context(context));
    for (const auto& key :
         {"tensor", "metadata", "location_receipt", "location_sam", "context", "scalar_controls"}) {
        file_pin(f, key);
    }
    const auto controls = std::filesystem::path(f.at("scalar_controls_path"));
    const auto stock = f.at("stock");
    return BoundFrame{std::move(scores), std::move(context), stock, std::move(f), controls};
}
std::size_t check_retained_scalar(const BoundFrame& frame) {
    std::ifstream input(frame.scalar_controls);
    require(input.good(), "retained scalar controls missing");
    std::string line;
    std::size_t comparisons = 0;
    while (std::getline(input, line)) {
        const auto values = split(line);
        require(values.size() == 2, "invalid scalar control row");
        const auto observed = sequence_likelihood(frame.scores, values[0]);
        const auto expected = values[1] == "impossible" ? -std::numeric_limits<double>::infinity()
                                                        : real(values[1]);
        require(std::bit_cast<std::uint64_t>(observed) == std::bit_cast<std::uint64_t>(expected),
                "retained unchanged Rust scalar bit parity failed");
        ++comparisons;
    }
    require(input.eof() && comparisons > 0, "incomplete scalar controls");
    file_pin(frame.binding, "scalar_controls");
    return comparisons;
}
std::string quote(const std::string& text) {
    std::string out = "\"";
    for (const char character : text) {
        switch (character) {
        case '\\':
            out += "\\\\";
            break;
        case '"':
            out += "\\\"";
            break;
        case '\n':
            out += "\\n";
            break;
        case '\t':
            out += "\\t";
            break;
        default:
            require(static_cast<unsigned char>(character) >= 32, "control byte in JSON text");
            out += character;
        }
    }
    return out + '"';
}
void fresh(const std::filesystem::path& path, const std::string& text) {
    const int descriptor = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0600);
    require(descriptor >= 0, "exclusive output creation failed");
    std::size_t written = 0;
    while (written < text.size()) {
        const auto count = ::write(descriptor, text.data() + written, text.size() - written);
        if (count <= 0) {
            static_cast<void>(::close(descriptor));
            throw std::runtime_error("output write failed");
        }
        written += static_cast<std::size_t>(count);
    }
    const auto status = ::fsync(descriptor);
    const auto closed = ::close(descriptor);
    require(status == 0 && closed == 0, "output sync/close failed");
}
}
