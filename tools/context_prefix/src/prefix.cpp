#include "context_prefix/prefix.h"
#include "prefix_sources.h"
#include <algorithm>
#include <array>
#include <charconv>
#include <chrono>
#include <cmath>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <iomanip>
#include <map>
#include <openssl/evp.h>
#include <set>
#include <sstream>
#include <stdexcept>
#include <unistd.h>

namespace context_prefix {
namespace {
std::string digest(EVP_MD_CTX* context) {
    std::array<unsigned char, EVP_MAX_MD_SIZE> bytes{};
    unsigned length{};
    require(EVP_DigestFinal_ex(context, bytes.data(), &length) == 1 && length == 32,
            "SHA256 finalization failed");
    std::ostringstream result;
    result << std::hex << std::setfill('0');
    for (unsigned i = 0; i < length; ++i)
        result << std::setw(2) << static_cast<unsigned>(bytes[i]);
    return result.str();
}
using Digest = std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)>;
Digest hash_context() {
    Digest result(EVP_MD_CTX_new(), EVP_MD_CTX_free);
    require(result && EVP_DigestInit_ex(result.get(), EVP_sha256(), nullptr) == 1,
            "SHA256 initialization failed");
    return result;
}
std::size_t number(const std::string& value) {
    std::size_t result{};
    const auto [end, error] = std::from_chars(value.data(), value.data() + value.size(), result);
    require(error == std::errc{} && end == value.data() + value.size(), "Invalid unsigned integer");
    return result;
}
bool hexadecimal(const std::string& value) {
    return value.size() == 64 && std::all_of(value.begin(), value.end(), [](char ch) {
               return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
           });
}
void sync_directory(const std::filesystem::path& path) {
    const int fd = ::open(path.c_str(), O_RDONLY | O_DIRECTORY);
    require(fd >= 0, "Cannot open output directory");
    const int result = ::fsync(fd);
    const int closed = ::close(fd);
    require(result == 0 && closed == 0, "Cannot sync output directory");
}
}
void require(bool condition, const std::string& message) {
    if (!condition)
        throw std::runtime_error(message);
}
std::string quote(const std::string& value) {
    std::ostringstream out;
    out << '"';
    for (const auto ch : value) {
        const auto byte = static_cast<unsigned char>(ch);
        if (ch == '"' || ch == '\\')
            out << '\\' << ch;
        else if (byte < 32)
            out << "\\u00" << std::hex << std::setw(2) << std::setfill('0')
                << static_cast<unsigned>(byte) << std::dec;
        else
            out << ch;
    }
    out << '"';
    return out.str();
}
std::string utc() {
    const auto now = std::chrono::system_clock::now();
    const auto value = std::chrono::system_clock::to_time_t(now);
    std::tm broken{};
    require(gmtime_r(&value, &broken) != nullptr, "UTC clock conversion failed");
    std::ostringstream out;
    out << std::put_time(&broken, "%Y-%m-%dT%H:%M:%SZ");
    return out.str();
}
std::string bytes_sha(std::span<const std::byte> bytes) {
    auto context = hash_context();
    require(EVP_DigestUpdate(context.get(), bytes.data(), bytes.size()) == 1,
            "SHA256 update failed");
    return digest(context.get());
}
Pin pin(const std::filesystem::path& path) {
    const auto resolved = std::filesystem::canonical(path);
    std::ifstream stream(resolved, std::ios::binary);
    require(static_cast<bool>(stream), "Cannot read pinned file: " + resolved.string());
    auto context = hash_context();
    std::array<char, 1 << 20> buffer{};
    std::uintmax_t size{};
    while (stream) {
        stream.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
        const auto count = stream.gcount();
        require(count >= 0, "Negative pinned read length");
        require(EVP_DigestUpdate(context.get(), buffer.data(), static_cast<std::size_t>(count)) ==
                    1,
                "SHA256 file update failed");
        size += static_cast<std::uintmax_t>(count);
    }
    require(stream.eof() && size == std::filesystem::file_size(resolved),
            "Pinned file read failed");
    return {resolved, size, digest(context.get())};
}
void check(const Pin& value) {
    const auto actual = pin(value.path);
    require(actual.path == value.path && actual.size == value.size && actual.sha256 == value.sha256,
            "Missing or changed pinned file: " + value.path.string());
}
std::string pin_json(const Pin& value) {
    return "{\"path\":" + quote(value.path.string()) + ",\"size\":" + std::to_string(value.size) +
           ",\"sha256\":" + quote(value.sha256) + "}";
}
void fresh_bytes(const std::filesystem::path& path, std::span<const std::byte> bytes) {
    const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0644);
    require(fd >= 0, "Cannot exclusively create output: " + path.string());
    std::size_t offset{};
    try {
        while (offset < bytes.size()) {
            const auto count = ::write(fd, bytes.data() + offset, bytes.size() - offset);
            require(count > 0, "Output write failed");
            offset += static_cast<std::size_t>(count);
        }
        require(::fsync(fd) == 0, "Output fsync failed");
    } catch (...) {
        ::close(fd);
        throw;
    }
    require(::close(fd) == 0, "Output close failed");
    sync_directory(path.parent_path());
}
void fresh(const std::filesystem::path& path, const std::string& text) {
    fresh_bytes(path, std::as_bytes(std::span(text.data(), text.size())));
}
std::string compiled_source_json() {
    std::string out = "{\"compiled_sources\":[";
    bool first = true;
    for (const auto& item : prefix_compiled::sources) {
        if (!first)
            out += ',';
        first = false;
        out += pin_json({item.path, item.size, item.sha256});
    }
    out += "],\"native_assets\":[";
    first = true;
    for (const auto& item : prefix_compiled::native_assets) {
        if (!first)
            out += ',';
        first = false;
        out += pin_json({item.path, item.size, item.sha256});
    }
    return out + "],\"compiler_path\":" + quote(prefix_compiled::compiler_path) +
           ",\"compiler_sha256\":" + quote(prefix_compiled::compiler_sha256) +
           ",\"compile_flags\":" + quote(prefix_compiled::compile_flags) +
           ",\"formatter_path\":" + quote(prefix_compiled::formatter_path) +
           ",\"formatter_sha256\":" + quote(prefix_compiled::formatter_sha256) + "}";
}
void check_compiled_sources() {
    for (const auto& item : prefix_compiled::sources)
        check({item.path, item.size, item.sha256});
    for (const auto& item : prefix_compiled::native_assets)
        check({item.path, item.size, item.sha256});
}
Request read_request(const std::filesystem::path& path, const std::string& sha) {
    const auto request_pin = pin(path);
    require(hexadecimal(sha) && request_pin.sha256 == sha, "Request SHA256 differs");
    require(request_pin.size <= 32768, "Request exceeds byte bound");
    std::ifstream stream(path);
    std::string line;
    require(static_cast<bool>(std::getline(stream, line)) && line == "context-prefix-request/1",
            "Unknown prefix request schema");
    std::map<std::string, std::string> values;
    while (std::getline(stream, line)) {
        const auto tab = line.find('\t');
        require(tab != std::string::npos && tab > 0 && tab + 1 < line.size() &&
                    line.find('\t', tab + 1) == std::string::npos &&
                    values.emplace(line.substr(0, tab), line.substr(tab + 1)).second,
                "Duplicate or malformed request field");
    }
    const std::set<std::string> expected{"role",
                                         "uuid",
                                         "acquisition_id",
                                         "pod5_path",
                                         "pod5_size",
                                         "pod5_sha256",
                                         "allowlist_path",
                                         "allowlist_size",
                                         "allowlist_sha256",
                                         "model_path",
                                         "model_manifest_path",
                                         "model_manifest_size",
                                         "model_manifest_sha256",
                                         "native_producer_path",
                                         "native_producer_size",
                                         "native_producer_sha256",
                                         "horizons",
                                         "lookahead",
                                         "front_trim",
                                         "pore_policy",
                                         "device",
                                         "input_dtype",
                                         "score_dtype",
                                         "threads"};
    std::set<std::string> keys;
    for (const auto& [key, value] : values) {
        static_cast<void>(value);
        keys.insert(key);
    }
    require(keys == expected, "Unknown or missing request field");
    require(values.at("role") == "exploratory_development" &&
                values.at("uuid") == "7214d805-8331-49aa-af61-478be074d7a6" &&
                values.at("acquisition_id") == "de8117b1abf27d6d4ac91526772636b9a5ca7fde" &&
                values.at("horizons") == "4096,12288" && values.at("lookahead") == "0" &&
                values.at("front_trim") == "10" && values.at("pore_policy") == "disabled" &&
                values.at("device") == "cpu" &&
                values.at("input_dtype") == "float32_from_native_half" &&
                values.at("score_dtype") == "float32" && values.at("threads") == "2",
            "Prefix policy or development identity differs");
    auto bound = [&](const std::string& key) {
        Pin result{values.at(key + "_path"), number(values.at(key + "_size")),
                   values.at(key + "_sha256")};
        require(result.path.is_absolute() && hexadecimal(result.sha256), "Invalid input pin");
        check(result);
        return result;
    };
    Request result{request_pin,
                   bound("pod5"),
                   bound("allowlist"),
                   bound("model_manifest"),
                   bound("native_producer"),
                   values.at("model_path"),
                   values.at("uuid"),
                   values.at("acquisition_id"),
                   {4096, 12288}};
    const auto stock = std::filesystem::path("/home/jake/Projects/nanopore_basecaller");
    const auto reference =
        std::filesystem::path("/home/jake/Projects/nanopore_basecaller-reference");
    require(result.pod5.path ==
                    std::filesystem::canonical(
                        stock / "data/raw/HG002/PAW70337/PAW70337_66b2eea5_de8117b1_33.pod5") &&
                result.model == std::filesystem::canonical(
                                    stock / "models/dna_r10.4.1_e8.2_400bps_hac@v6.0.0") &&
                result.allowlist.path ==
                    std::filesystem::canonical(
                        reference / "results/graph-prior/pilot-v1/development/parents.ids") &&
                result.native_producer.path ==
                    std::filesystem::canonical(
                        reference /
                        "results/graph-prior/pilot-v1/development/artifacts/native-call.json"),
            "Prefix input source location differs");
    std::ifstream ids(result.allowlist.path);
    std::set<std::string> unique;
    while (std::getline(ids, line))
        require(line.size() == 36 && unique.insert(line).second,
                "Invalid/duplicate allowlist UUID");
    require(unique.size() == 64 && unique.contains(result.uuid),
            "UUID absent from original 64-parent cohort");
    std::ifstream manifest(result.model_manifest.path);
    require(static_cast<bool>(std::getline(manifest, line)) && line == "context-prefix-model/1",
            "Unknown model manifest schema");
    std::set<std::string> names;
    while (std::getline(manifest, line)) {
        std::istringstream row(line);
        std::string name, size, hash;
        require(static_cast<bool>(std::getline(row, name, '\t')) &&
                    static_cast<bool>(std::getline(row, size, '\t')) &&
                    static_cast<bool>(std::getline(row, hash)) &&
                    name.find('/') == std::string::npos &&
                    (name == "config.toml" || name.ends_with(".tensor")) && hexadecimal(hash) &&
                    names.insert(name).second,
                "Invalid model manifest row");
        check({std::filesystem::canonical(result.model / name), number(size), hash});
    }
    std::set<std::string> actual;
    for (const auto& item : std::filesystem::directory_iterator(result.model))
        if (item.is_regular_file() &&
            (item.path().filename() == "config.toml" || item.path().extension() == ".tensor"))
            actual.insert(item.path().filename().string());
    require(names == actual && names.contains("config.toml") && names.size() > 2,
            "Model file census differs");
    return result;
}
DetachedPrefix detach(std::span<const std::int16_t> source, std::size_t horizon,
                      float calibration_scale, float calibration_offset) {
    require(horizon > 10 && horizon <= 12288 && horizon <= source.size(),
            "Invalid visible prefix horizon");
    require(std::isfinite(calibration_scale) && calibration_scale > 0 &&
                std::isfinite(calibration_offset),
            "Invalid calibration");
    return {{source.begin(), source.begin() + static_cast<std::ptrdiff_t>(horizon)},
            horizon,
            calibration_scale,
            calibration_offset};
}
void validate_acquisition(const Request& request, const std::string& uuid,
                          const std::string& acquisition, const std::string& flowcell,
                          std::uint16_t sample_rate) {
    require(uuid == request.uuid && acquisition == request.acquisition_id &&
                flowcell == "PAW70337" && sample_rate == 5000,
            "POD5 UUID/acquisition/flowcell/sample rate differs");
}
double difference(std::span<const float> a, std::span<const float> b) {
    require(a.size() == b.size(), "Comparison shape differs");
    double maximum{};
    for (std::size_t i = 0; i < a.size(); ++i) {
        require(std::isfinite(a[i]) && std::isfinite(b[i]), "Nonfinite native value");
        maximum =
            std::max(maximum, std::abs(static_cast<double>(a[i]) - static_cast<double>(b[i])));
    }
    return maximum;
}
}
