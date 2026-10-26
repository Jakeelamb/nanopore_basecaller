#include "archive_consumer/core.h"

#include <fcntl.h>
#include <openssl/evp.h>
#include <sys/stat.h>
#include <unistd.h>
#include <zlib.h>

#include <algorithm>
#include <array>
#include <iomanip>
#include <memory>
#include <set>
#include <sstream>
#include <type_traits>

namespace archive_consumer {
namespace {
class Digest {
public:
    Digest() : context_(EVP_MD_CTX_new(), EVP_MD_CTX_free) {
        require(context_ != nullptr &&
                        EVP_DigestInit_ex(context_.get(), EVP_sha256(), nullptr) == 1,
                "Archive SHA256 initialization failed");
    }
    void update(const unsigned char* bytes, std::size_t size) {
        require(EVP_DigestUpdate(context_.get(), bytes, size) == 1, "Archive SHA256 update failed");
    }
    std::string finish() {
        std::array<unsigned char, EVP_MAX_MD_SIZE> bytes{};
        unsigned size{};
        require(EVP_DigestFinal_ex(context_.get(), bytes.data(), &size) == 1 && size == 32,
                "Archive SHA256 finalization failed");
        std::ostringstream out;
        out << std::hex << std::setfill('0');
        for (unsigned i = 0; i < size; ++i) {
            out << std::setw(2) << static_cast<unsigned>(bytes[i]);
        }
        return out.str();
    }

private:
    std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> context_;
};
class OpenFile {
public:
    explicit OpenFile(const FilePin& expected)
            : path_(expected.path), fd_(::open(path_.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW)) {
        require(fd_ >= 0, "Archive storage open failed");
        if (::fstat(fd_, &before_) != 0 || !S_ISREG(before_.st_mode) || before_.st_size < 0 ||
            static_cast<std::uint64_t>(before_.st_size) != expected.size) {
            ::close(fd_);
            fd_ = -1;
            require(false, "Stored FilePin size/type differs");
        }
    }
    OpenFile(const OpenFile&) = delete;
    OpenFile& operator=(const OpenFile&) = delete;
    ~OpenFile() { ::close(fd_); }
    std::size_t take(std::array<unsigned char, 65536>& bytes) const {
        const auto count = ::read(fd_, bytes.data(), bytes.size());
        require(count >= 0, "Archive storage read failed");
        return static_cast<std::size_t>(count);
    }
    void rewind() const { require(::lseek(fd_, 0, SEEK_SET) == 0, "Archive rewind failed"); }
    void unchanged() const {
        struct stat after{}, named{};
        require(::fstat(fd_, &after) == 0 && ::lstat(path_.c_str(), &named) == 0 &&
                        S_ISREG(named.st_mode) && before_.st_dev == after.st_dev &&
                        before_.st_ino == after.st_ino && after.st_dev == named.st_dev &&
                        after.st_ino == named.st_ino && before_.st_size == after.st_size &&
                        before_.st_mtim.tv_sec == after.st_mtim.tv_sec &&
                        before_.st_mtim.tv_nsec == after.st_mtim.tv_nsec &&
                        before_.st_ctim.tv_sec == after.st_ctim.tv_sec &&
                        before_.st_ctim.tv_nsec == after.st_ctim.tv_nsec &&
                        fs::canonical(path_) == path_,
                "Archive storage changed while opened");
    }

private:
    fs::path path_;
    int fd_;
    struct stat before_{};
};
class Inflater {
public:
    Inflater() { require(inflateInit2(&stream, 15 + 16) == Z_OK, "Gzip initialization failed"); }
    Inflater(const Inflater&) = delete;
    Inflater& operator=(const Inflater&) = delete;
    ~Inflater() { inflateEnd(&stream); }
    z_stream stream{};
};
void stored_pin(const OpenFile& input, const FilePin& expected) {
    Digest digest;
    std::array<unsigned char, 65536> bytes{};
    std::uint64_t count{};
    while (true) {
        const auto size = input.take(bytes);
        if (size == 0) {
            break;
        }
        require(size <= expected.size - count, "Stored FilePin byte bound exceeded");
        count += size;
        digest.update(bytes.data(), size);
    }
    require(count == expected.size && digest.finish() == expected.sha256,
            "Stored FilePin SHA256/size differs");
    input.unchanged();
}
void gzip_raw(const OpenFile& input, const FilePin& original) {
    input.rewind();
    Inflater inflater;
    auto& stream = inflater.stream;
    Digest digest;
    std::array<unsigned char, 65536> compressed{}, raw{};
    std::uint64_t count{};
    bool first = true;
    while (true) {
        if (stream.avail_in == 0) {
            const auto size = input.take(compressed);
            require(size > 0, "Gzip truncated before checked end/CRC");
            if (first) {
                const std::array<unsigned char, 10> header{31, 139, 8, 0, 0, 0, 0, 0, 0, 255};
                require(size >= header.size() &&
                                std::equal(header.begin(), header.end(), compressed.begin()),
                        "Deterministic gzip6/mtime0/empty-name/OS255 header differs");
                first = false;
            }
            stream.next_in = compressed.data();
            stream.avail_in = static_cast<uInt>(size);
        }
        stream.next_out = raw.data();
        stream.avail_out = static_cast<uInt>(raw.size());
        const auto before = stream.avail_in;
        const auto status = inflate(&stream, Z_NO_FLUSH);
        const auto emitted = raw.size() - static_cast<std::size_t>(stream.avail_out);
        require(emitted <= original.size - count, "Gzip raw byte bound exceeded");
        count += emitted;
        digest.update(raw.data(), emitted);
        require(status == Z_OK || status == Z_STREAM_END, "Gzip data/CRC integrity failed");
        if (status == Z_STREAM_END) {
            require(stream.avail_in == 0 && input.take(compressed) == 0,
                    "Gzip trailing bytes or concatenated member forbidden");
            break;
        }
        require(emitted > 0 || stream.avail_in < before, "Gzip made no progress");
    }
    require(count == original.size && digest.finish() == original.sha256,
            "Gzip original SHA256/size differs");
    input.unchanged();
}
}
void verify_codec_dependencies() {
    const auto deps = own_dependencies();
    require(std::string(zlibVersion()) == deps.at("zlib_version").get<std::string>() &&
                    std::string(ZLIB_VERSION) == deps.at("zlib_version").get<std::string>(),
            "Pinned zlib header/runtime version differs");
    for (const auto& header : deps.at("zlib_headers")) {
        check(header);
    }
    check(deps.at("zlib_library"));
    check(deps.at("crypto_library"));
}
void exact_keys(const Json& value, const std::vector<std::string>& keys) {
    require(value.is_object() && value.size() == keys.size(), "Object field census differs");
    for (const auto& key : keys) {
        require(value.contains(key), "Required field absent: " + key);
    }
}
FilePin file_pin(const Json& value) {
    exact_keys(value, {"path", "size", "sha256"});
    FilePin result{value.at("path").get<std::string>(),
                   static_cast<std::uint64_t>(integer(value.at("size"))),
                   value.at("sha256").get<std::string>()};
    require(result.path.is_absolute() && result.path.lexically_normal() == result.path &&
                    result.sha256.size() == 64 &&
                    result.sha256.find_first_not_of("0123456789abcdef") == std::string::npos,
            "Malformed absolute SHA256 FilePin");
    return result;
}
Json as_json(const FilePin& value) {
    return {{"path", value.path.string()}, {"size", value.size}, {"sha256", value.sha256}};
}
Trace parse_trace(const Json& value) {
    exact_keys(value, {"query_index", "native_completion", "producer", "storage"});
    const auto& storage = value.at("storage");
    require(storage.is_object(), "Object field census differs");
    const auto codec = storage.at("codec").get<std::string>();
    const auto original = file_pin(storage.at("original"));
    require(original.path.filename() == "phase-trace.bin" && original.size <= maximum_trace_bytes,
            "Only bounded original native phase trace may use storage resolution");
    static_cast<void>(file_pin(value.at("native_completion")));
    static_cast<void>(file_pin(value.at("producer")));
    const auto query = integer(value.at("query_index"));
    require(query < 512, "Foreign trace query");
    if (codec == "raw") {
        exact_keys(storage, {"codec", "original"});
        return {query, value.at("native_completion"), value.at("producer"), Raw{original}};
    }
    require(codec == "gzip", "Unsupported trace codec");
    exact_keys(storage, {"codec", "original", "archive"});
    const auto archive = file_pin(storage.at("archive"));
    require(archive.path != original.path && archive.size <= maximum_trace_bytes,
            "Gzip storage path/byte bound differs");
    return {query, value.at("native_completion"), value.at("producer"), Gzip{original, archive}};
}
void verify_storage(const TraceStorage& storage) {
    std::visit(
            [](const auto& value) {
                require(value.original.size <= maximum_trace_bytes,
                        "Original trace exceeds byte bound");
                if constexpr (std::is_same_v<std::decay_t<decltype(value)>, Raw>) {
                    const OpenFile input(value.original);
                    stored_pin(input, value.original);
                } else {
                    require(value.archive.size <= maximum_trace_bytes,
                            "Compressed trace exceeds byte bound");
                    const OpenFile input(value.archive);
                    stored_pin(input, value.archive);
                    gzip_raw(input, value.original);
                }
            },
            storage);
}
void same_catalogue(const Json& actual, const Json& expected, std::size_t count) {
    const auto catalogue = [count](const Json& rows) {
        require(rows.is_array() && rows.size() == count, "File catalogue count differs");
        std::map<fs::path, Json> result;
        for (const auto& row : rows) {
            require(result.emplace(file_pin(row).path, row).second, "Duplicate catalogue path");
        }
        return result;
    };
    require(catalogue(actual) == catalogue(expected), "File catalogue membership differs");
}
void validate_native_catalogue(const Json& row,
                               const Json& result,
                               const Json& seal,
                               const Json& producer,
                               const Json& argv,
                               const Json& decoder,
                               const Trace& trace) {
    const fs::path directory =
            fs::path(row.at("result").at("path").get<std::string>()).parent_path();
    require(integer(row.at("query_index")) == trace.query_index &&
                    row.at("completion") == trace.native_completion &&
                    row.at("producer") == trace.producer &&
                    file_pin(row.at("completion")).path == directory / "complete.json" &&
                    file_pin(row.at("result")).path == directory / "result.json",
            "Original native row/storage origin differs");
    const auto original =
            std::visit([](const auto& value) { return as_json(value.original); }, trace.storage);
    require(file_pin(original).path == directory / "phase-trace.bin" &&
                    result.at("phase_trace") == original,
            "Original result/trace identity differs");
    exact_keys(seal, {"schema", "complete", "files"});
    require(seal.at("schema") == "context-decoder-complete/1" && seal.at("complete") == true,
            "Actual native completion schema/status differs");
    const auto attempt = pin(directory / "attempt.json");
    const auto expected = Json::array({attempt, row.at("result"), original});
    same_catalogue(seal.at("files"), expected, 3);
    auto produced = expected;
    produced.push_back(row.at("completion"));
    same_catalogue(producer.at("produced_files"), produced, 4);
    const auto stdout_pin = producer.at("raw_files").at(5);
    require(parse(text(stdout_pin.at("path").get<std::string>(), 8192)) ==
                    Json{{"completion", row.at("completion")}},
            "Raw native stdout names a different completion");
    const auto observed = read(attempt.at("path").get<std::string>());
    require(observed.at("schema") == "context-decoder-attempt/1" &&
                    observed.at("binary") == decoder.at("binary") && observed.at("argv") == argv &&
                    observed.at("cpp_standard") == 23 && observed.at("fast_math") == false &&
                    observed.at("fp_contract") == "off",
            "Original decoder attempt binary/argv/arithmetic differs");
    same_catalogue(observed.at("compiled_sources"), decoder.at("compiled_sources"), 32);
    for (const auto& member : seal.at("files")) {
        if (member == original) {
            verify_storage(trace.storage);
        } else {
            check(member);
        }
    }
}
}
