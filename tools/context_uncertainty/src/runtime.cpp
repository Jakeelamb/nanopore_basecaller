#include "compiled_sources.h"
#include "context_uncertainty/uncertainty.h"
#include <algorithm>
#include <charconv>
#include <cmath>
#include <fcntl.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <memory>
#include <openssl/evp.h>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <system_error>
#include <tuple>
#include <unistd.h>

namespace context_uncertainty {
namespace {
const std::filesystem::path export_root = "/home/jake/Projects/nanopore_basecaller-reference/"
                                          "results/graph-prior/pilot-v1/development/native-export";
const std::filesystem::path registry_path =
    "/home/jake/Projects/nanopore_basecaller-reference/results/graph-prior/pilot-v1/development/"
    "artifacts/native-call.json";
const std::string registry_sha = "f8470d591314a24e95ec594c5334d4969e0336be95115b644509da18e5543adf";
const std::string aligned_sha = "db01733a1847c37b3e30da8839af233728b7bc00421828f291b3da3c3bf2c6fe";
const std::string config_sha = "e550ccbedb68ed74d6ee88e2f510adf33c52a1c868bd5e3a2bfbb7dfe6154c3f";
constexpr std::size_t maximum_state_cells = 20000000;
using Hash = std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)>;
Hash hash_start() {
    Hash result(EVP_MD_CTX_new(), EVP_MD_CTX_free);
    require(result != nullptr && EVP_DigestInit_ex(result.get(), EVP_sha256(), nullptr) == 1,
            "SHA256 initialization failed");
    return result;
}
std::string hash_end(Hash &context) {
    std::array<unsigned char, EVP_MAX_MD_SIZE> bytes{};
    unsigned length{};
    require(EVP_DigestFinal_ex(context.get(), bytes.data(), &length) == 1, "SHA256 final failed");
    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (unsigned i = 0; i < length; ++i)
        out << std::setw(2) << static_cast<unsigned>(bytes[i]);
    return out.str();
}
std::vector<std::string> split(const std::string &line) {
    std::vector<std::string> result;
    std::size_t begin{};
    while (true) {
        const auto end = line.find('\t', begin);
        result.push_back(line.substr(begin, end == std::string::npos ? end : end - begin));
        if (end == std::string::npos)
            return result;
        begin = end + 1;
    }
}
bool digest(const std::string &value) {
    return value.size() == 64 && std::all_of(value.begin(), value.end(), [](char c) {
               return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
           });
}
std::string text(const std::filesystem::path &path, std::uintmax_t maximum) {
    require(std::filesystem::file_size(path) <= maximum, "Metadata file exceeds declared bound");
    std::ifstream stream(path, std::ios::binary);
    require(stream.good(), "Cannot open metadata file");
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}
Pin row_pin(const std::vector<std::string> &row, std::size_t index) {
    require(index + 2 < row.size() && std::filesystem::path(row[index]).is_absolute() &&
                digest(row[index + 2]),
            "Malformed consumed file pin");
    return {row[index], natural(row[index + 1]), row[index + 2]};
}
std::string reverse_complement(std::string value) {
    std::reverse(value.begin(), value.end());
    for (auto &base : value) {
        const auto index = std::string("ACGT").find(base);
        require(index != std::string::npos, "Noncanonical native sequence");
        base = std::string("TGCA")[index];
    }
    return value;
}
std::string source_json() {
    std::string result = "{\"compiled_sources\":[";
    bool first = true;
    for (const auto &source : compiled_sources) {
        if (!first)
            result += ',';
        first = false;
        result += pin_json({source.path, source.size, source.sha256});
    }
    return result + "],\"compiler_path\":" + quote(compiler_path) +
           ",\"compiler_sha256\":" + quote(compiler_sha256) +
           ",\"compile_flags\":" + quote(compile_flags) +
           ",\"formatter_path\":" + quote(formatter_path) +
           ",\"formatter_sha256\":" + quote(formatter_sha256) + "}";
}
void sources() {
    for (const auto &source : compiled_sources)
        check({source.path, source.size, source.sha256});
    require(pin(compiler_path).sha256 == compiler_sha256 &&
                pin(formatter_path).sha256 == formatter_sha256,
            "Compiled compiler/formatter changed");
}
std::map<std::string, Pin> declarations(const Pin &registry) {
    require(registry.path == registry_path && registry.sha256 == registry_sha,
            "Original registered export manifest differs");
    check(registry);
    const auto bytes = text(registry.path, 2097152);
    const std::regex pattern(
        R"PIN(\{\s*"path"\s*:\s*"([^"\\]+)"\s*,\s*"sha256"\s*:\s*"([0-9a-f]{64})"\s*,\s*"size"\s*:\s*([0-9]+)\s*\})PIN");
    std::map<std::string, Pin> result;
    for (auto cursor = std::sregex_iterator(bytes.begin(), bytes.end(), pattern);
         cursor != std::sregex_iterator(); ++cursor) {
        const auto &match = *cursor;
        Pin item{match[1].str(), natural(match[3].str()), match[2].str()};
        require(item.path.parent_path() == export_root &&
                    result.emplace(item.path.string(), item).second,
                "Original export declaration location/duplication differs");
    }
    require(result.size() == 3179, "Pinned original declaration census differs");
    std::set<std::string> actual;
    for (const auto &entry : std::filesystem::directory_iterator(export_root)) {
        require(entry.is_regular_file() && !entry.is_symlink(), "Foreign export directory entry");
        actual.insert(entry.path().string());
    }
    require(actual.size() == result.size(), "Original export membership count changed");
    for (const auto &[path, item] : result)
        require(actual.contains(path) && std::filesystem::file_size(item.path) == item.size,
                "Original export artifact missing/size changed");
    return result;
}
void native_parents(Inputs &input, const Pin &alignment) {
    require(alignment.sha256 == aligned_sha, "Original native alignment differs");
    check(alignment);
    std::istringstream stream(text(alignment.path, 33554432));
    std::set<std::string> seen;
    std::string line;
    while (std::getline(stream, line)) {
        if (line.empty() || line.front() == '@')
            continue;
        const auto row = split(line);
        require(row.size() >= 11, "Malformed native alignment row");
        const auto flags = natural(row[1]);
        if ((flags & 0x900U) != 0)
            continue;
        require(input.parents.contains(row[0]) && seen.insert(row[0]).second,
                "Foreign/duplicate native parent");
        auto &parent = input.parents.at(row[0]);
        const auto whole = metadata(parent.metadata.path);
        parent.reverse = (flags & 16U) != 0;
        parent.contig = row[2];
        parent.cigar = row[5];
        auto sequence = row[9], quality = row[10];
        if (parent.reverse) {
            sequence = reverse_complement(sequence);
            std::reverse(quality.begin(), quality.end());
        }
        const bool mapped = (flags & 4U) == 0 && row[2] != "*" && row[5] != "*";
        bool autosomal = false;
        for (std::size_t chromosome = 1; chromosome <= 22; ++chromosome)
            autosomal = autosomal || row[2] == "chr" + std::to_string(chromosome);
        require(!mapped || natural(row[3]) > 0, "Mapped native position is zero");
        parent.reference_start = mapped ? natural(row[3]) - 1 : 0;
        parent.eligible = mapped && autosomal && natural(row[4]) >= 30 && natural(row[4]) < 255 &&
                          sequence == whole.at("SEQ") && quality == whole.at("Q");
        parent.reason = !mapped                                          ? "native_unmapped"
                        : !autosomal                                     ? "native_non_autosome"
                        : natural(row[4]) < 30 || natural(row[4]) >= 255 ? "native_mapq"
                        : sequence != whole.at("SEQ") || quality != whole.at("Q")
                            ? "native_parent_seq_q_mismatch"
                            : "eligible";
    }
    require(seen.size() == input.parents.size(), "Native parent census incomplete");
}
void retain(Inputs &input) {
    for (const auto &[parent_id, parent] : input.parents) {
        const auto whole = metadata(parent.metadata.path);
        require(whole.at("format") == "DGP1" && whole.at("read_id") == parent_id &&
                    whole.at("stride") == "6",
                "Original parent metadata geometry differs");
        std::vector<Chunk *> chunks;
        for (auto &chunk : input.chunks)
            if (chunk.parent == parent_id)
                chunks.push_back(&chunk);
        const auto count = natural(whole.at("chunk_count")),
                   signal = natural(whole.at("signal_samples"));
        require(chunks.size() == count && count > 0, "Parent chunk count differs");
        std::vector<Fields> values;
        for (std::size_t i = 0; i < count; ++i) {
            require(chunks[i]->index == i, "Parent chunk indices incomplete");
            values.push_back(metadata(chunks[i]->metadata.path));
            const auto &meta = values.back();
            require(meta.at("format") == "DGM1" && meta.at("read_id") == parent_id &&
                        natural(meta.at("chunk_index")) == i &&
                        natural(meta.at("chunk_count")) == count && meta.at("C") == "1024" &&
                        meta.at("signal_samples") == whole.at("signal_samples") &&
                        meta.at("num_trimmed_samples") == whole.at("num_trimmed_samples") &&
                        meta.at("model_path") == "/home/jake/Projects/nanopore_basecaller/models/"
                                                 "dna_r10.4.1_e8.2_400bps_hac@v6.0.0" &&
                        meta.at("score_file") == chunks[i]->scores.path.filename().string(),
                    "DGM parent/chunk/model binding differs");
            chunks[i]->timesteps = natural(meta.at("T"));
            chunks[i]->time_offset = natural(meta.at("time_offset"));
            require(chunks[i]->timesteps > 0 && chunks[i]->timesteps <= 4096 &&
                        meta.at("MOVES").size() == chunks[i]->timesteps &&
                        meta.at("SEQ").size() == meta.at("Q").size() &&
                        static_cast<std::size_t>(
                            std::count(meta.at("MOVES").begin(), meta.at("MOVES").end(), '1')) ==
                            meta.at("SEQ").size() &&
                        std::all_of(meta.at("MOVES").begin(), meta.at("MOVES").end(),
                                    [](char x) { return x == '0' || x == '1'; }),
                    "Native chunk moves/SEQ/Q geometry differs");
        }
        std::string sequence, quality, moves;
        std::size_t front{};
        for (std::size_t i = 0; i < count; ++i) {
            const auto &meta = values[i];
            std::size_t end{}, next_front{};
            if (i + 1 < count) {
                const auto finish =
                    natural(meta.at("input_offset")) + natural(meta.at("raw_chunk_size"));
                const auto next_start = natural(values[i + 1].at("input_offset"));
                require(finish >= next_start && (finish - next_start) % 6 == 0,
                        "Retained chunk overlap differs");
                const auto overlap = (finish - next_start) / 6;
                require(meta.at("MOVES").size() >= overlap / 2, "Retained rear exceeds chunk");
                end = meta.at("MOVES").size() - overlap / 2;
                next_front = overlap - overlap / 2;
            } else if (count == 1 || meta.at("variable_chunk_sizes") == "1") {
                end = (std::min(signal, natural(meta.at("raw_chunk_size"))) + 5) / 6;
            } else {
                end = meta.at("MOVES").size();
            }
            require(front <= end && end <= meta.at("MOVES").size(),
                    "Retained timestep range invalid");
            auto &chunk = *chunks[i];
            chunk.retained_start = front;
            chunk.retained_end = end;
            chunk.chunk_start = static_cast<std::size_t>(
                std::count(meta.at("MOVES").begin(),
                           meta.at("MOVES").begin() + static_cast<std::ptrdiff_t>(front), '1'));
            chunk.chunk_end =
                chunk.chunk_start +
                static_cast<std::size_t>(
                    std::count(meta.at("MOVES").begin() + static_cast<std::ptrdiff_t>(front),
                               meta.at("MOVES").begin() + static_cast<std::ptrdiff_t>(end), '1'));
            chunk.parent_start = sequence.size();
            sequence +=
                meta.at("SEQ").substr(chunk.chunk_start, chunk.chunk_end - chunk.chunk_start);
            quality += meta.at("Q").substr(chunk.chunk_start, chunk.chunk_end - chunk.chunk_start);
            moves += meta.at("MOVES").substr(front, end - front);
            chunk.parent_end = sequence.size();
            front = next_front;
        }
        if (moves.size() > signal / 6) {
            require(moves.size() == signal / 6 + 1, "Retained partial overhang differs");
            if (moves.back() == '1') {
                sequence.pop_back();
                quality.pop_back();
                --chunks.back()->chunk_end;
            }
            moves.pop_back();
            --chunks.back()->retained_end;
            chunks.back()->parent_end = sequence.size();
        }
        require(sequence == whole.at("SEQ") && quality == whole.at("Q") &&
                    moves == whole.at("MOVES"),
                "Complete native stitching differs from DGP1");
    }
}
std::string proposal_line(const Proposal &p) {
    std::ostringstream out;
    out << std::setprecision(17) << p.chunk << '\t' << p.parent << '\t' << p.chunk_index << '\t'
        << p.contig << '\t' << p.reverse << '\t' << p.chunk_begin << '\t' << p.chunk_end << '\t'
        << p.read_begin << '\t' << p.read_end << '\t' << p.time_begin << '\t' << p.time_end << '\t'
        << p.ref_begin << '\t' << p.ref_end << '\t' << p.core_ref_begin << '\t' << p.core_ref_end
        << '\t' << p.native << '\t' << p.uncertainty << '\t' << p.emission_entropy << '\t'
        << p.stay_entropy << '\t' << p.tie << '\n';
    return out.str();
}
Proposal proposal(const std::vector<std::string> &r) {
    require(r.size() == 20 && digest(r[19]) && (r[4] == "0" || r[4] == "1"),
            "Malformed proposal row");
    return {r[0],
            r[1],
            r[3],
            r[15],
            r[19],
            natural(r[2]),
            natural(r[5]),
            natural(r[6]),
            natural(r[7]),
            natural(r[8]),
            natural(r[9]),
            natural(r[10]),
            natural(r[11]),
            natural(r[12]),
            natural(r[13]),
            natural(r[14]),
            natural(r[4]) != 0,
            finite(r[16]),
            finite(r[17]),
            finite(r[18])};
}
std::string proposal_header(const Inputs &input) {
    return "uncertainty-proposals/1\t" + input.manifest.sha256 + '\t' + source_identity() + '\n';
}
}
void require(bool condition, const std::string &message) {
    if (!condition)
        throw std::invalid_argument(message);
}
std::size_t natural(const std::string &value) {
    std::size_t result{};
    const auto converted = std::from_chars(value.data(), value.data() + value.size(), result);
    require(!value.empty() && converted.ec == std::errc{} &&
                converted.ptr == value.data() + value.size(),
            "Invalid unsigned integer");
    return result;
}
double finite(const std::string &value) {
    std::size_t used{};
    const auto result = std::stod(value, &used);
    require(used == value.size() && std::isfinite(result), "Invalid finite numeric field");
    return result;
}
std::string sha256(const std::string &bytes) {
    auto context = hash_start();
    require(EVP_DigestUpdate(context.get(), bytes.data(), bytes.size()) == 1,
            "SHA256 update failed");
    return hash_end(context);
}
Pin pin(const std::filesystem::path &path) {
    const auto resolved = std::filesystem::canonical(path);
    std::ifstream stream(resolved, std::ios::binary);
    require(stream.good(), "Cannot open consumed file: " + path.string());
    auto context = hash_start();
    std::array<char, 262144> buffer{};
    std::uintmax_t size{};
    while (stream) {
        stream.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
        const auto count = stream.gcount();
        require(count >= 0, "Negative file read count");
        size += static_cast<std::uintmax_t>(count);
        require(EVP_DigestUpdate(context.get(), buffer.data(), static_cast<std::size_t>(count)) ==
                    1,
                "File SHA256 update failed");
    }
    require(stream.eof() && size == std::filesystem::file_size(resolved),
            "Consumed file read failed");
    return {resolved, size, hash_end(context)};
}
void check(const Pin &expected) {
    require(pin(expected.path) == expected,
            "Missing or changed consumed file: " + expected.path.string());
}
std::string quote(const std::string &value) {
    std::ostringstream out;
    out << '"';
    for (const char character : value) {
        const auto c = static_cast<unsigned char>(character);
        if (c == '"' || c == '\\')
            out << '\\' << static_cast<char>(c);
        else if (c < 32)
            out << "\\u" << std::hex << std::setfill('0') << std::setw(4)
                << static_cast<unsigned>(c) << std::dec;
        else
            out << static_cast<char>(c);
    }
    out << '"';
    return out.str();
}
std::string pin_json(const Pin &value) {
    return "{\"path\":" + quote(value.path.string()) + ",\"size\":" + std::to_string(value.size) +
           ",\"sha256\":" + quote(value.sha256) + "}";
}
Fields metadata(const std::filesystem::path &path) {
    std::istringstream stream(text(path, 2097152));
    Fields result;
    std::string line;
    while (std::getline(stream, line)) {
        const auto row = split(line);
        require(row.size() == 2 && !row[0].empty() && result.emplace(row[0], row[1]).second,
                "Duplicate/malformed native metadata field");
    }
    return result;
}
Inputs read_inputs(const std::filesystem::path &path, const std::string &expected) {
    Inputs input;
    input.manifest = pin(path);
    require(input.manifest.sha256 == expected, "Uncertainty input manifest hash differs");
    std::istringstream stream(text(path, 8388608));
    std::string line;
    require(static_cast<bool>(std::getline(stream, line)), "Missing uncertainty input header");
    const auto header = split(line);
    require(header.size() == 3 && header[0] == "uncertainty-inputs/1" &&
                header[1] == "development" && digest(header[2]),
            "Uncertainty manifest schema/role differs");
    input.ancestry = header[2];
    std::map<std::string, Pin> source_map;
    std::optional<Pin> alignment;
    std::set<std::string> chunk_ids;
    while (std::getline(stream, line)) {
        const auto row = split(line);
        if (row[0] == "SOURCE") {
            require(row.size() == 4, "Malformed metadata source pin");
            const auto item = row_pin(row, 1);
            require(source_map.emplace(item.path.string(), item).second,
                    "Duplicate metadata source");
            input.sources.push_back(item);
        } else if (row[0] == "ALIGN") {
            require(row.size() == 4 && !alignment, "Duplicate/malformed native alignment");
            alignment = row_pin(row, 1);
        } else if (row[0] == "PARENT") {
            require(row.size() == 5, "Malformed parent record");
            Parent parent;
            parent.id = row[1];
            parent.metadata = row_pin(row, 2);
            require(input.parents.emplace(parent.id, parent).second, "Duplicate parent");
        } else if (row[0] == "CHUNK") {
            require(row.size() == 10, "Malformed chunk record");
            Chunk chunk;
            chunk.id = row[1];
            chunk.parent = row[2];
            chunk.index = natural(row[3]);
            chunk.scores = row_pin(row, 4);
            chunk.metadata = row_pin(row, 7);
            require(chunk.id == chunk.parent + "/" + std::to_string(chunk.index) &&
                        chunk_ids.insert(chunk.id).second,
                    "Duplicate/malformed chunk identity");
            input.chunks.push_back(std::move(chunk));
        } else {
            require(false, "Unknown uncertainty manifest record");
        }
    }
    require(input.parents.size() == 64 && input.chunks.size() == 1557 && alignment,
            "Registered parent/chunk/alignment census differs");
    for (const auto &source : input.sources)
        check(source);
    require(source_map.contains(registry_path.string()) &&
                std::any_of(input.sources.begin(), input.sources.end(),
                            [&](const auto &item) { return item.sha256 == input.ancestry; }) &&
                std::any_of(input.sources.begin(), input.sources.end(),
                            [](const auto &item) { return item.sha256 == config_sha; }),
            "Original registry/config/ancestry source missing");
    const auto original = declarations(source_map.at(registry_path.string()));
    for (const auto &[source_path, item] : original)
        if (item.path.extension() != ".scores")
            require(source_map.contains(source_path) && source_map.at(source_path) == item,
                    "Original non-score export source census differs");
    std::set<std::string> members;
    for (const auto &[id, parent] : input.parents) {
        static_cast<void>(id);
        require(original.contains(parent.metadata.path.string()) &&
                    original.at(parent.metadata.path.string()) == parent.metadata &&
                    source_map.contains(parent.metadata.path.string()) &&
                    source_map.at(parent.metadata.path.string()) == parent.metadata &&
                    members.insert(parent.metadata.path.string()).second,
                "Parent lacks registered metadata pin");
    }
    for (const auto &chunk : input.chunks) {
        require(input.parents.contains(chunk.parent) &&
                    original.contains(chunk.scores.path.string()) &&
                    original.at(chunk.scores.path.string()) == chunk.scores &&
                    original.contains(chunk.metadata.path.string()) &&
                    original.at(chunk.metadata.path.string()) == chunk.metadata &&
                    source_map.contains(chunk.metadata.path.string()) &&
                    source_map.at(chunk.metadata.path.string()) == chunk.metadata &&
                    members.insert(chunk.scores.path.string()).second &&
                    members.insert(chunk.metadata.path.string()).second,
                "Chunk lacks unique original producer membership/pins");
    }
    require(members.size() == 3178 && std::is_sorted(input.chunks.begin(), input.chunks.end(),
                                                     [](const auto &a, const auto &b) {
                                                         return std::tie(a.parent, a.index) <
                                                                std::tie(b.parent, b.index);
                                                     }),
            "Canonical original chunk census differs");
    require(source_map.contains(alignment->path.string()) &&
                source_map.at(alignment->path.string()) == *alignment,
            "Native alignment lacks source pin");
    retain(input);
    native_parents(input, *alignment);
    return input;
}
Frame read_scores(const Chunk &chunk, const Fields &meta) {
    check(chunk.scores);
    std::ifstream stream(chunk.scores.path, std::ios::binary);
    std::string line;
    require(static_cast<bool>(std::getline(stream, line)) && line.size() < 4096,
            "Missing/oversized DGS1 header");
    const auto h = split(line);
    require(h.size() == 15 && h[0] == "DGS1" && natural(h[1]) == chunk.timesteps &&
                h[2] == "1024" && h[3] == "4" && h[4] == "6" && finite(h[5]) == 2 &&
                (h[10] == "0" || h[10] == "1") && (finite(h[11]) == 0 || finite(h[11]) == 5) &&
                h[12] == meta.at("time_offset") && h[13] == meta.at("token") &&
                chunk.scores.path.filename() == h[13] + "_s" + h[14] + ".scores",
            "DGS1 header/metadata/model binding differs");
    static_cast<void>(natural(h[6]));
    for (const auto index : {7U, 8U, 9U})
        static_cast<void>(finite(h[index]));
    require(chunk.scores.size == line.size() + 1 + chunk.timesteps * 1024 * 2,
            "DGS1 payload length differs");
    Frame frame{chunk.timesteps, 4, finite(h[5]), {}};
    frame.scores.reserve(chunk.timesteps * 1024);
    const auto clamp = finite(h[11]);
    std::array<unsigned char, 8192> buffer{};
    std::size_t remaining = chunk.timesteps * 1024 * 2;
    while (remaining > 0) {
        const auto amount = std::min(remaining, buffer.size());
        stream.read(reinterpret_cast<char *>(buffer.data()), static_cast<std::streamsize>(amount));
        require(stream.gcount() == static_cast<std::streamsize>(amount), "Truncated DGS1 payload");
        for (std::size_t i = 0; i < amount; i += 2) {
            const auto bits = static_cast<std::uint16_t>(
                static_cast<unsigned>(buffer[i]) | (static_cast<unsigned>(buffer[i + 1]) << 8U));
            const auto value = half(bits);
            frame.scores.push_back(clamp == 0 ? value : std::clamp(value, -clamp, clamp));
        }
        remaining -= amount;
    }
    require(stream.peek() == std::char_traits<char>::eof(), "Trailing DGS1 payload bytes");
    return frame;
}
std::string source_identity() {
    std::string bytes;
    for (const auto &source : compiled_sources)
        bytes += std::string(source.path) + '\t' + std::to_string(source.size) + '\t' +
                 source.sha256 + '\n';
    return sha256(bytes);
}
void synced_write(const std::filesystem::path &path, const std::string &value) {
    const int descriptor = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0600);
    require(descriptor >= 0, "Exclusive output creation failed: " + path.string());
    std::size_t written{};
    while (written < value.size()) {
        const auto count = ::write(descriptor, value.data() + written, value.size() - written);
        if (count <= 0) {
            ::close(descriptor);
            require(false, "Output write failed");
        }
        written += static_cast<std::size_t>(count);
    }
    const auto sync = ::fsync(descriptor), closed = ::close(descriptor);
    require(sync == 0 && closed == 0, "Output sync/close failed");
}
Invocation begin(int argc, char **argv) {
    Invocation result;
    for (int i = 1; i + 1 < argc; ++i)
        if (std::string(argv[i]) == "--output")
            result.output = std::filesystem::absolute(argv[i + 1]);
    require(!result.output.empty() && std::filesystem::create_directory(result.output),
            "Fresh output directory required");
    std::string attempt = "{\"schema\":\"uncertainty-native-attempt/1\",\"argv\":[";
    for (int i = 0; i < argc; ++i) {
        if (i != 0)
            attempt += ',';
        attempt += quote(argv[i]);
    }
    attempt +=
        "],\"binary\":" + pin_json(pin("/proc/self/exe")) + ",\"source\":" + source_json() + "}\n";
    synced_write(result.output / "attempt.json", attempt);
    sources();
    require(argc >= 2, "Uncertainty command required");
    result.command = argv[1];
    require(result.command == "qualify" || result.command == "scan" || result.command == "merge",
            "Unknown uncertainty command");
    for (int i = 2; i < argc; i += 2) {
        require(i + 1 < argc && result.options.emplace(argv[i], argv[i + 1]).second,
                "Duplicate/missing CLI argument");
    }
    const std::set<std::string> allowed =
        result.command == "qualify" ? std::set<std::string>{"--output"}
        : result.command == "scan"
            ? std::set<std::string>{"--output", "--manifest", "--manifest-sha256", "--begin",
                                    "--count"}
            : std::set<std::string>{"--output", "--manifest", "--manifest-sha256", "--parts",
                                    "--parts-sha256"};
    for (const auto &[key, value] : result.options) {
        static_cast<void>(value);
        require(allowed.contains(key), "Unknown CLI argument");
    }
    if (result.command != "qualify")
        require(result.options.contains("--manifest") &&
                    result.options.contains("--manifest-sha256"),
                "Pinned manifest required");
    if (result.command == "scan")
        require(result.options.contains("--begin") && result.options.contains("--count"),
                "Explicit scan bounds required");
    if (result.command == "merge")
        require(result.options.contains("--parts") && result.options.contains("--parts-sha256"),
                "Pinned collected parts required");
    return result;
}
void finish(const Invocation &invocation, const std::string &result,
            const std::vector<std::string> &files, const std::vector<Pin> &inputs) {
    sources();
    for (const auto &item : inputs)
        check(item);
    synced_write(invocation.output / "result.json", result + '\n');
    std::string complete =
        "{\"schema\":\"uncertainty-native-complete/1\",\"complete\":true,\"command\":" +
        quote(invocation.command) + ",\"source_id\":" + quote(source_identity()) +
        ",\"attempt\":" + pin_json(pin(invocation.output / "attempt.json")) +
        ",\"result\":" + pin_json(pin(invocation.output / "result.json")) + ",\"files\":[";
    bool first = true;
    for (const auto &name : files) {
        if (!first)
            complete += ',';
        first = false;
        complete += pin_json(pin(invocation.output / name));
    }
    complete += "],\"inputs\":[";
    first = true;
    for (const auto &item : inputs) {
        if (!first)
            complete += ',';
        first = false;
        complete += pin_json(item);
    }
    complete += "],\"source\":" + source_json() + "}\n";
    synced_write(invocation.output / "complete.json", complete);
    const int directory = ::open(invocation.output.c_str(), O_RDONLY | O_DIRECTORY);
    require(directory >= 0, "Completion directory open failed");
    const auto sync = ::fsync(directory), closed = ::close(directory);
    require(sync == 0 && closed == 0, "Completion directory sync failed");
    std::cout << "{\"completion\":" << pin_json(pin(invocation.output / "complete.json")) << "}\n";
}
std::string scan(const Inputs &input, std::size_t begin, std::size_t count,
                 const std::filesystem::path &output) {
    require(begin < input.chunks.size() && count > 0 && count <= input.chunks.size() - begin,
            "Invalid scan chunk slice");
    std::size_t cells{};
    for (std::size_t i = begin; i < begin + count; ++i) {
        const auto next = input.chunks[i].timesteps * 256;
        require(next <= maximum_state_cells && cells <= maximum_state_cells - next,
                "Scan exceeds 20M state-timestep cells before payload/DP work");
        cells += next;
    }
    std::string proposals = proposal_header(input), chunks = "uncertainty-chunks/1\t" +
                                                             input.manifest.sha256 + '\t' +
                                                             source_identity() + '\n';
    std::map<std::string, std::size_t> exclusions;
    std::size_t proposed{}, eligible{}, timesteps{};
    double partitions{};
    for (std::size_t i = begin; i < begin + count; ++i) {
        const auto &chunk = input.chunks[i];
        const auto &parent = input.parents.at(chunk.parent);
        const auto meta = metadata(chunk.metadata.path);
        const auto scores = read_scores(chunk, meta);
        auto status = parent.reason;
        std::size_t nominations{};
        if (parent.eligible) {
            const auto values = posterior(scores);
            const auto selected = nominate(scores, values, parent, chunk, meta,
                                           metadata(parent.metadata.path), exclusions);
            for (const auto &candidate : selected)
                proposals += proposal_line(candidate);
            nominations = selected.size();
            proposed += nominations;
            partitions += values.log_partition;
            ++eligible;
        }
        timesteps += scores.timesteps;
        chunks += chunk.id + '\t' + chunk.scores.sha256 + '\t' + status + '\t' +
                  std::to_string(nominations) + '\n';
    }
    synced_write(output / "proposals.tsv", proposals);
    synced_write(output / "chunks.tsv", chunks);
    std::string result = "{\"schema\":\"uncertainty-scan/"
                         "1\",\"development_only\":true,\"biological_qualification\":false,"
                         "\"online_causality\":false,\"begin\":" +
                         std::to_string(begin) + ",\"chunks\":" + std::to_string(count) +
                         ",\"eligible_chunks\":" + std::to_string(eligible) +
                         ",\"timesteps\":" + std::to_string(timesteps) +
                         ",\"state_timestep_cells\":" + std::to_string(cells) +
                         ",\"local_greedy_proposals\":" + std::to_string(proposed) +
                         ",\"exclusions\":{";
    bool first = true;
    for (const auto &[reason, number] : exclusions) {
        if (!first)
            result += ',';
        first = false;
        result += quote(reason) + ':' + std::to_string(number);
    }
    std::ostringstream number;
    number << std::setprecision(17) << partitions;
    return result + "},\"sum_chunk_log_partitions_diagnostic_only\":" + number.str() +
           ",\"partition_sum_is_joint_likelihood\":false,\"policy\":\"mean_0.5_conditional_base_"
           "entropy_plus_0.5_stay_entropy_v1\"}";
}
std::string merge(const Inputs &input, const Pin &parts, const std::filesystem::path &output,
                  std::vector<Pin> &consumed) {
    check(parts);
    std::istringstream stream(text(parts.path, 2097152));
    std::string line;
    require(static_cast<bool>(std::getline(stream, line)) &&
                line == "uncertainty-parts/1\t" + input.manifest.sha256 + '\t' + source_identity(),
            "Collected parts/source header differs");
    std::set<std::string> qualified;
    std::vector<Proposal> all;
    std::map<std::string, const Chunk *> census;
    for (const auto &chunk : input.chunks)
        census.emplace(chunk.id, &chunk);
    while (std::getline(stream, line)) {
        const auto row = split(line);
        require(row.size() == 10 && row[0] == "PART", "Malformed collected part record");
        const auto chunk_file = row_pin(row, 1), proposal_file = row_pin(row, 4),
                   completion = row_pin(row, 7);
        check(chunk_file);
        check(proposal_file);
        check(completion);
        consumed.insert(consumed.end(), {chunk_file, proposal_file, completion});
        std::istringstream statuses(text(chunk_file.path, 1048576));
        std::string header;
        require(static_cast<bool>(std::getline(statuses, header)) &&
                    header ==
                        "uncertainty-chunks/1\t" + input.manifest.sha256 + '\t' + source_identity(),
                "Scan chunk header differs");
        std::set<std::string> local;
        while (std::getline(statuses, header)) {
            const auto value = split(header);
            require(value.size() == 4 && census.contains(value[0]) &&
                        value[1] == census.at(value[0])->scores.sha256 &&
                        qualified.insert(value[0]).second && local.insert(value[0]).second,
                    "Duplicate/foreign/unqualified scan chunk");
            static_cast<void>(natural(value[3]));
        }
        std::istringstream values(text(proposal_file.path, 16777216));
        require(static_cast<bool>(std::getline(values, header)) &&
                    header + '\n' == proposal_header(input),
                "Scan proposal header differs");
        while (std::getline(values, header)) {
            auto candidate = proposal(split(header));
            require(local.contains(candidate.chunk) && input.parents.contains(candidate.parent),
                    "Proposal lacks consumed chunk");
            const auto &chunk = *census.at(candidate.chunk);
            require(candidate.parent == chunk.parent && candidate.chunk_index == chunk.index &&
                        candidate.read_begin < candidate.read_end &&
                        candidate.read_end - candidate.read_begin == 21 &&
                        candidate.chunk_begin < candidate.chunk_end &&
                        candidate.chunk_end - candidate.chunk_begin == 21 &&
                        candidate.read_begin >= chunk.parent_start &&
                        candidate.read_end <= chunk.parent_end &&
                        candidate.time_begin >= chunk.retained_start &&
                        candidate.time_end <= chunk.retained_end &&
                        candidate.tie == sha256("uncertainty-v1\n" + candidate.parent + '\n' +
                                                std::to_string(candidate.read_begin) + '\n' +
                                                candidate.chunk + '\n'),
                    "Merged proposal ownership/identity differs");
            all.push_back(std::move(candidate));
        }
    }
    require(qualified.size() == input.chunks.size(),
            "Global nomination requires all1557 disjoint qualified chunks");
    const auto selected = select(std::move(all), 512);
    auto output_rows = proposal_header(input);
    for (const auto &candidate : selected)
        output_rows += proposal_line(candidate);
    synced_write(output / "nominations.tsv", output_rows);
    return "{\"schema\":\"uncertainty-nominations/1\",\"qualified_chunks\":" +
           std::to_string(qualified.size()) +
           ",\"nominations\":" + std::to_string(selected.size()) +
           ",\"cap\":512,\"development_only\":true,\"biological_qualification\":false,\"online_"
           "causality\":false,\"method\":\"neural_entropy_only_no_truth_or_reference_disagreement_"
           "score\"}";
}
}
