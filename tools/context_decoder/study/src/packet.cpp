#include "context_study/packet.h"
#include "compiled_sources.h"
#include "wire_fields.h"
#include <algorithm>
#include <charconv>
#include <cmath>
#include <fcntl.h>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <memory>
#include <openssl/evp.h>
#include <set>
#include <sstream>
#include <system_error>
#include <unistd.h>

namespace context_study {
namespace {
constexpr std::uintmax_t packet_limit = 134217728;
std::string hex(const unsigned char *bytes, unsigned length) {
    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (unsigned i = 0; i < length; ++i)
        out << std::setw(2) << static_cast<unsigned>(bytes[i]);
    return out.str();
}
using Hash = std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)>;
Hash hash_context() {
    Hash context(EVP_MD_CTX_new(), EVP_MD_CTX_free);
    require(context != nullptr && EVP_DigestInit_ex(context.get(), EVP_sha256(), nullptr) == 1,
            "SHA256 initialization failed");
    return context;
}
std::string final_hash(Hash &context) {
    std::array<unsigned char, EVP_MAX_MD_SIZE> bytes{};
    unsigned length{};
    require(EVP_DigestFinal_ex(context.get(), bytes.data(), &length) == 1, "SHA256 final failed");
    return hex(bytes.data(), length);
}
Record split(const std::string &line) {
    Record fields;
    std::size_t begin = 0;
    while (true) {
        const auto end = line.find('\t', begin);
        fields.push_back(line.substr(begin, end == std::string::npos ? end : end - begin));
        if (end == std::string::npos)
            return fields;
        begin = end + 1;
    }
}
void token(const std::string &value) {
    require(!value.empty() && value != ".", "empty identity token");
}
void canonicalize(std::vector<std::string> &values) {
    std::sort(values.begin(), values.end());
    values.erase(std::unique(values.begin(), values.end()), values.end());
}
}
bool digest(const std::string &value) {
    return value.size() == 64 && std::all_of(value.begin(), value.end(), [](char c) {
               return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
           });
}
std::string sha256(const std::string &bytes) {
    auto context = hash_context();
    require(EVP_DigestUpdate(context.get(), bytes.data(), bytes.size()) == 1,
            "SHA256 update failed");
    return final_hash(context);
}
std::string file_sha256(const std::filesystem::path &path) {
    std::ifstream input(path, std::ios::binary);
    require(input.good(), "cannot open hash input " + path.string());
    auto context = hash_context();
    std::array<char, 65536> buffer{};
    while (input) {
        input.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
        require(EVP_DigestUpdate(context.get(), buffer.data(),
                                 static_cast<std::size_t>(input.gcount())) == 1,
                "SHA256 update failed");
    }
    require(input.eof(), "hash read failed");
    return final_hash(context);
}
std::size_t natural(const std::string &text) {
    require(!text.empty() && (text.size() == 1 || text.front() != '0'), "noncanonical integer");
    std::size_t value{};
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    require(result.ec == std::errc{} && result.ptr == text.data() + text.size(),
            "invalid unsigned integer");
    return value;
}
double finite_number(const std::string &text) {
    double value{};
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    require(!text.empty() && result.ec == std::errc{} && result.ptr == text.data() + text.size() &&
                std::isfinite(value),
            "invalid finite number");
    return value;
}
bool boolean(const std::string &text) {
    require(text == "0" || text == "1", "invalid boolean");
    return text == "1";
}
RawPacket read_records(const std::filesystem::path &path, const std::string &expected,
                       const std::string &schema) {
    require(digest(expected), "invalid packet hash");
    require(std::filesystem::is_regular_file(path) &&
                std::filesystem::file_size(path) <= packet_limit,
            "packet file/size invalid");
    std::ifstream file(path, std::ios::binary);
    const std::string bytes((std::istreambuf_iterator<char>(file)),
                            std::istreambuf_iterator<char>());
    require(!bytes.empty() && bytes.back() == '\n' && sha256(bytes) == expected,
            "packet bytes/hash mismatch");
    require(std::all_of(bytes.begin(), bytes.end(),
                        [](char c) { return (c >= 32 && c <= 126) || c == '\n' || c == '\t'; }),
            "packet must be ASCII TSV");
    std::istringstream input(bytes);
    std::string line;
    std::getline(input, line);
    const auto header = split(line);
    require(header.size() == 3 && header[0] == "SCHEMA" && header[1] == schema && digest(header[2]),
            "packet schema/header mismatch");
    RawPacket result{header[2], {}};
    while (std::getline(input, line)) {
        require(!line.empty(), "empty packet record");
        result.records.push_back(split(line));
        require(result.records.size() <= 5000000, "packet record count exceeds cap");
    }
    return result;
}
Packet read_candidates(const std::filesystem::path &path, const std::string &expected) {
    return parse_candidates(read_records(path, expected, "context-candidate-case/1"));
}
Packet parse_candidates(const RawPacket &raw) {
    Packet result{raw.manifest, {}};
    std::map<std::string, std::size_t> indices;
    for (const auto &fields : raw.records) {
        require(!fields.empty(), "empty packet record");
        const auto &type = fields.at(0);
        const auto width = wire::candidate_widths.find(type);
        require(width != wire::candidate_widths.end() && fields.size() == width->second,
                "unknown candidate record or field count");
        if (type == "CASE") {
            using namespace wire::CASE;
            require(result.cases.size() < 1024 && !indices.contains(fields[case_id]),
                    "case cap or duplicate case");
            CandidateCase item;
            item.id = fields[case_id];
            item.domain = fields[domain];
            item.parent = fields[parent];
            item.contig = fields[contig];
            token(item.id);
            token(item.parent);
            token(item.contig);
            require(item.domain == "ordinary" || item.domain == "private-ordinary" ||
                        item.domain == "private-withheld",
                    "invalid domain");
            require(fields[strand] == "+" || fields[strand] == "-", "invalid strand");
            item.reverse = fields[strand] == "-";
            item.read = {natural(fields[read_start]), natural(fields[read_end])};
            item.owned = {natural(fields[owned_start]), natural(fields[owned_end])};
            item.reference = {natural(fields[ref_start]), natural(fields[ref_end])};
            item.core = {natural(fields[core_start]), natural(fields[core_end])};
            item.future = natural(fields[future_bases]);
            item.left = fields[left_guard];
            item.right = fields[right_guard];
            item.native = fields[native];
            item.availability = fields[availability];
            item.escape_capped = boolean(fields[escape_capped]);
            item.conditioned_capped = boolean(fields[conditioned_capped]);
            item.escape_empty = boolean(fields[escape_empty]);
            item.conditioned_empty = boolean(fields[conditioned_empty]);
            item.ancestry = fields[geometry_ancestry_sha256];
            item.geometry = fields[geometry_sha256];
            require(digest(item.ancestry) && digest(item.geometry), "invalid geometry digest");
            std::string geometry = "context-geometry/1";
            for (const auto index : wire::geometry_indices)
                geometry += '\t' + fields[index];
            require(sha256(geometry + '\n') == item.geometry, "geometry digest mismatch");
            require(dna(item.left) && dna(item.right) && dna(item.native) &&
                        item.future <= item.right.size(),
                    "invalid guard DNA/future span");
            require(item.read.begin <= item.owned.begin && item.owned.begin <= item.owned.end &&
                        item.owned.end <= item.read.end,
                    "invalid parent coordinate nesting");
            require(item.owned.begin - item.read.begin == item.left.size() &&
                        item.owned.end - item.owned.begin == item.native.size() &&
                        item.read.end - item.owned.end == item.right.size() - item.future,
                    "native-parent geometry differs");
            require(item.reference.begin <= item.core.begin && item.core.begin <= item.core.end &&
                        item.core.end <= item.reference.end &&
                        item.reference.end - item.reference.begin <= 4096,
                    "invalid genomic geometry");
            require(item.availability == "usable" || item.availability == "missing" ||
                        item.availability == "ambiguous" || item.availability == "inconsistent",
                    "invalid context availability");
            indices.emplace(item.id, result.cases.size());
            result.cases.push_back(std::move(item));
            continue;
        }
        require(indices.contains(fields[1]), "record precedes CASE or has unknown case");
        auto &item = result.cases[indices.at(fields[1])];
        if (type == "PATH" || type == "REFPATH") {
            require(dna(fields[2]), "invalid path DNA");
            auto &paths = type == "PATH" ? item.paths : item.reference_paths;
            require(paths.size() < 4096, "path input cap exceeded");
            paths.push_back(fields[2]);
        } else if (type == "CAND") {
            using namespace wire::CAND;
            const auto origin_value = natural(fields[origins]);
            require(origin_value > 0 && origin_value <= 15, "invalid candidate origin range");
            Candidate candidate{fields[sequence], static_cast<unsigned>(origin_value),
                                std::nullopt};
            require(dna(candidate.sequence) && candidate.origins > 0 && candidate.origins <= 15,
                    "invalid candidate DNA/origin");
            if (fields[log_mass] != ".")
                candidate.log_mass = GuardedLogMass{finite_number(fields[log_mass])};
            require(candidate.log_mass.has_value() || candidate.origins == graph_origin,
                    "unscored candidate must be graph-only");
            const auto old = item.candidates.find(candidate.sequence);
            if (old == item.candidates.end()) {
                require(item.candidates.size() < 4096, "candidate cap exceeded");
                item.candidates.emplace(candidate.sequence, candidate);
            } else {
                require(old->second.log_mass.has_value() == candidate.log_mass.has_value() &&
                            (!candidate.log_mass ||
                             old->second.log_mass->value == candidate.log_mass->value),
                        "conflicting duplicate candidate score");
                old->second.origins |= candidate.origins;
            }
        } else if (type == "BASE") {
            using namespace wire::BASE;
            require(std::find(roles.begin(), roles.end(), fields[role]) != roles.end(),
                    "unknown baseline role");
            Choice value{fields[sequence],
                         finite_number(fields[log_mass]),
                         finite_number(fields[potential]),
                         finite_number(fields[objective]),
                         fields[gate],
                         boolean(fields[abstained])};
            require(dna(value.sequence) && item.saved.emplace(fields[role], value).second,
                    "invalid/duplicate saved baseline");
        }
    }
    require(!result.cases.empty(), "empty case packet");
    for (auto &item : result.cases) {
        canonicalize(item.paths);
        canonicalize(item.reference_paths);
        require(item.paths.size() <= 32 &&
                    (item.availability == "usable" ? !item.paths.empty() : item.paths.empty()),
                "path availability differs");
        for (const auto &path_value : item.reference_paths)
            require(std::binary_search(item.paths.begin(), item.paths.end(), path_value),
                    "reference path is absent from context");
        require(item.candidates.contains(item.native) &&
                    (item.candidates.at(item.native).origins & native_origin) != 0,
                "native candidate absent");
        for (const auto &[sequence, candidate] : item.candidates)
            require((candidate.origins & native_origin) == 0 || sequence == item.native,
                    "foreign native candidate");
        require(item.saved.size() == roles.size(), "incomplete saved baseline");
        for (const auto &[role, choice] : item.saved) {
            static_cast<void>(role);
            require(item.candidates.contains(choice.sequence),
                    "saved sequence absent from candidate union");
        }
    }
    std::sort(result.cases.begin(), result.cases.end(),
              [](const auto &a, const auto &b) { return a.id < b.id; });
    return result;
}
std::string json_string(const std::string &value) {
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
            require(static_cast<unsigned char>(ch) >= 32, "unsupported JSON control character");
            out << ch;
        }
    }
    out << '"';
    return out.str();
}
std::string pin_json(const std::filesystem::path &path) {
    return "{\"path\":" + json_string(std::filesystem::canonical(path).string()) +
           ",\"size\":" + std::to_string(std::filesystem::file_size(path)) +
           ",\"sha256\":" + json_string(file_sha256(path)) + "}";
}
void synced_write(const std::filesystem::path &path, const std::string &bytes) {
    require(!std::filesystem::exists(path), "output already exists " + path.string());
    std::ofstream output(path, std::ios::binary);
    output << bytes;
    output.flush();
    require(output.good(), "output write failed");
    output.close();
    const int descriptor = ::open(path.c_str(), O_RDONLY);
    require(descriptor >= 0, "output sync open failed");
    const auto status = ::fsync(descriptor);
    const auto closed = ::close(descriptor);
    require(status == 0 && closed == 0, "output sync failed");
}
std::string source_json() {
    std::string result = "{\"compiled_sources\":[";
    bool first = true;
    for (const auto &source : compiled_sources) {
        if (!first)
            result += ',';
        first = false;
        result += "{\"path\":" + json_string(source.path) +
                  ",\"size\":" + std::to_string(source.size) +
                  ",\"sha256\":" + json_string(source.sha256) + "}";
    }
    return result + "],\"compiler_path\":" + json_string(compiler_path) +
           ",\"compiler_sha256\":" + json_string(compiler_sha256) +
           ",\"compile_flags\":" + json_string(compile_flags) +
           ",\"formatter_path\":" + json_string(formatter_path) +
           ",\"formatter_sha256\":" + json_string(formatter_sha256) + "}";
}
void verify_compiled_sources() {
    for (const auto &source : compiled_sources)
        require(std::filesystem::is_regular_file(source.path) &&
                    std::filesystem::file_size(source.path) == source.size &&
                    file_sha256(source.path) == source.sha256,
                "compiled source changed " + std::string(source.path));
    require(file_sha256(compiler_path) == compiler_sha256 &&
                file_sha256(formatter_path) == formatter_sha256,
            "compiler or formatter changed");
}
Invocation begin_invocation(int argc, char **argv, bool inference) {
    Invocation result;
    for (int i = 2; i + 1 < argc; ++i)
        if (std::string(argv[i]) == "--output")
            result.output = argv[i + 1];
    require(!result.output.empty() && !std::filesystem::exists(result.output),
            "fresh --output directory required");
    std::filesystem::create_directories(result.output);
    std::string attempt = "{\"schema\":\"context-study-native-attempt/1\",\"argv\":[";
    for (int i = 0; i < argc; ++i) {
        if (i != 0)
            attempt += ',';
        attempt += json_string(argv[i]);
    }
    attempt +=
        "],\"binary\":" + pin_json("/proc/self/exe") + ",\"source\":" + source_json() + "}\n";
    synced_write(result.output / "attempt.json", attempt);
    verify_compiled_sources();
    require(argc >= 2, "command required");
    result.command = argv[1];
    require(inference ? result.command == "replay"
                      : result.command == "qualify" || result.command == "evaluate",
            "unknown command");
    require((argc - 2) % 2 == 0, "option value required");
    for (int i = 2; i < argc; i += 2) {
        const std::string key = argv[i];
        const bool common = key == "--output" || key == "--cases" || key == "--cases-sha256";
        const bool truth = !inference && result.command == "evaluate" &&
                           (key == "--truth" || key == "--truth-sha256");
        require((common || truth) && (result.command != "qualify" || key == "--output") &&
                    result.options.emplace(key, argv[i + 1]).second,
                "unknown/duplicate option " + key);
    }
    require(result.options.size() == (result.command == "qualify" ? 1U
                                      : inference                 ? 3U
                                                                  : 5U),
            "required options absent");
    return result;
}
void finish_invocation(const Invocation &invocation, const std::string &result,
                       const std::vector<std::string> &files) {
    verify_compiled_sources();
    synced_write(invocation.output / "result.json", result + '\n');
    std::string complete =
        "{\"schema\":\"context-study-native-complete/1\",\"complete\":true,\"command\":" +
        json_string(invocation.command) +
        ",\"attempt\":" + pin_json(invocation.output / "attempt.json") +
        ",\"result\":" + pin_json(invocation.output / "result.json") + ",\"files\":[";
    for (std::size_t i = 0; i < files.size(); ++i) {
        if (i != 0)
            complete += ',';
        complete += pin_json(invocation.output / files[i]);
    }
    complete += "],\"inputs\":[";
    bool first_input = true;
    for (const auto *name : {"cases", "truth"}) {
        const auto key = "--" + std::string(name);
        if (!invocation.options.contains(key))
            continue;
        require(file_sha256(invocation.options.at(key)) == invocation.options.at(key + "-sha256"),
                "input changed before completion");
        if (!first_input)
            complete += ',';
        first_input = false;
        complete += pin_json(invocation.options.at(key));
    }
    complete += "],\"source\":" + source_json() + "}\n";
    synced_write(invocation.output / "complete.json", complete);
    std::cout << "{\"completion\":" << pin_json(invocation.output / "complete.json") << "}\n";
}
}
