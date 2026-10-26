#include "archive_consumer/core.h"

#include "compiled_sources.h"

#include <fcntl.h>
#include <openssl/evp.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <charconv>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <memory>
#include <sstream>
#include <stdexcept>

namespace archive_consumer {
void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::invalid_argument(message);
    }
}
std::size_t natural(const std::string& value) {
    std::size_t result{};
    const auto parsed = std::from_chars(value.data(), value.data() + value.size(), result);
    require(!value.empty() && parsed.ec == std::errc{} && parsed.ptr == value.data() + value.size(),
            "Invalid unsigned integer");
    return result;
}
std::size_t integer(const Json& value) {
    require(value.is_number_unsigned() ||
                    (value.is_number_integer() && value.get<std::int64_t>() >= 0),
            "Nonnegative JSON integer required");
    return value.get<std::size_t>();
}
std::vector<std::string> split(const std::string& value, char delimiter) {
    std::vector<std::string> result;
    std::size_t start{};
    while (true) {
        const auto end = value.find(delimiter, start);
        result.push_back(value.substr(start, end == std::string::npos ? end : end - start));
        if (end == std::string::npos) {
            return result;
        }
        start = end + 1;
    }
}
std::string text(const fs::path& path, std::uintmax_t maximum) {
    require(fs::is_regular_file(path) && !fs::is_symlink(path) && fs::file_size(path) <= maximum,
            "File absent, symlink or outside byte bound: " + path.string());
    std::ifstream input(path, std::ios::binary);
    require(input.good(), "Cannot read " + path.string());
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}
namespace {
std::string digest(EVP_MD_CTX* context) {
    std::array<unsigned char, EVP_MAX_MD_SIZE> bytes{};
    unsigned count{};
    require(EVP_DigestFinal_ex(context, bytes.data(), &count) == 1 && count == 32,
            "SHA256 finalization failed");
    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (unsigned i = 0; i < count; ++i) {
        out << std::setw(2) << static_cast<unsigned>(bytes[i]);
    }
    return out.str();
}
auto hash_context() {
    std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> result(EVP_MD_CTX_new(),
                                                                   EVP_MD_CTX_free);
    require(result != nullptr && EVP_DigestInit_ex(result.get(), EVP_sha256(), nullptr) == 1,
            "SHA256 initialization failed");
    return result;
}
}
std::string hash_text(const std::string& bytes) {
    auto context = hash_context();
    require(EVP_DigestUpdate(context.get(), bytes.data(), bytes.size()) == 1,
            "SHA256 update failed");
    return digest(context.get());
}
std::string sha256(const fs::path& path) {
    std::ifstream input(path, std::ios::binary);
    require(input.good(), "Cannot hash " + path.string());
    auto context = hash_context();
    std::array<char, 65536> bytes{};
    while (input) {
        input.read(bytes.data(), static_cast<std::streamsize>(bytes.size()));
        require(EVP_DigestUpdate(context.get(), bytes.data(),
                                 static_cast<std::size_t>(input.gcount())) == 1,
                "SHA256 update failed");
    }
    require(input.eof(), "Hash read failed");
    return digest(context.get());
}
Json pin(const fs::path& path) {
    require(path.lexically_normal() == path, "Non-normalized FilePin path");
    require(path.is_absolute() && fs::is_regular_file(path) && !fs::is_symlink(path),
            "Absolute nonsymlink regular input required");
    return {{"path", path.string()}, {"size", fs::file_size(path)}, {"sha256", sha256(path)}};
}
void check(const Json& value) {
    require(value.is_object() && value.size() == 3 && value.contains("path") &&
                    value.contains("size") && value.contains("sha256"),
            "Malformed file pin");
    require(pin(value.at("path").get<std::string>()) == value,
            "Missing or changed consumed file: " + value.at("path").get<std::string>());
}
Json parse(const std::string& bytes) {
    require(bytes.size() <= 16777216, "JSON byte bound exceeded");
    std::vector<std::set<std::string>> keys;
    const auto callback = [&keys](int depth, Json::parse_event_t event, Json& value) {
        require(depth <= 32, "JSON nesting bound exceeded");
        if (event == Json::parse_event_t::object_start) {
            keys.emplace_back();
        } else if (event == Json::parse_event_t::key) {
            require(!keys.empty() && keys.back().insert(value.get<std::string>()).second,
                    "Duplicate JSON key");
        } else if (event == Json::parse_event_t::object_end) {
            require(!keys.empty(), "JSON object stack mismatch");
            keys.pop_back();
        }
        return true;
    };
    return Json::parse(bytes, callback, true, false);
}
Json read(const fs::path& path, std::uintmax_t maximum) { return parse(text(path, maximum)); }
void fresh(const fs::path& path, const std::string& bytes) {
    const int fd = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    require(fd >= 0, "Exclusive output creation failed: " + path.string());
    std::size_t offset{};
    while (offset < bytes.size()) {
        const auto count = ::write(fd, bytes.data() + offset, bytes.size() - offset);
        if (count <= 0) {
            static_cast<void>(::close(fd));
            throw std::runtime_error("Output write failed");
        }
        offset += static_cast<std::size_t>(count);
    }
    const int synced = ::fsync(fd), closed = ::close(fd);
    require(synced == 0 && closed == 0, "Output sync/close failed");
}
void write(const fs::path& path, const Json& value) { fresh(path, value.dump(2) + "\n"); }
Fields fields(const fs::path& path, const std::string& schema) {
    std::istringstream input(text(path, 4194304));
    std::string line;
    require(static_cast<bool>(std::getline(input, line)) && line == schema,
            "Tabular schema differs");
    Fields result;
    while (std::getline(input, line)) {
        const auto row = split(line);
        require(row.size() == 2 && result.emplace(row[0], row[1]).second,
                "Duplicate/malformed tabular field");
    }
    return result;
}
void add_pin(Fields& fields, const std::string& prefix, const Json& value) {
    for (const auto& key : {"path", "sha256"}) {
        fields[prefix + '_' + key] = value.at(key).get<std::string>();
    }
    fields[prefix + "_size"] = std::to_string(integer(value.at("size")));
}
void dna(const std::string& value) {
    require(value.find_first_not_of("ACGT") == std::string::npos, "Noncanonical DNA");
}
Json source_witness() {
    Json result = {
            {"compiled_sources", Json::array()},
            {"compiler",
             Json{{"path", compiler_path}, {"size", compiler_size}, {"sha256", compiler_sha256}}}};
    for (const auto& item : compiled_sources) {
        result["compiled_sources"].push_back(
                {{"path", item.path}, {"size", item.size}, {"sha256", item.sha256}});
    }
    return result;
}
void verify_sources() {
    const auto witness = source_witness();
    for (const auto& value : witness.at("compiled_sources")) {
        check(value);
    }
    check(witness.at("compiler"));
    verify_codec_dependencies();
}
Json dependencies() {
    const auto reference = own_dependencies().at("legacy_dependencies");
    check(reference);
    return read(reference.at("path").get<std::string>());
}
fs::path connector_root() { return source_root_path; }
void validate_completion(const Json& value, const std::string& schema) {
    require(value.at("schema") == schema && value.at("complete") == true,
            "Completion schema/status differs");
    require(value.at("source_witness") == legacy_witness(),
            "Connector source witness changed or missing");
    if (value.contains("plan")) {
        validate_plan(value.at("plan"));
        require(value.at("plan_sha256") == value.at("plan").at("plan_sha256"),
                "Embedded authoritative plan identity differs");
    }
}
void validate_plan(const Json& value) {
    validate_completion(value, "uncertainty-feedback-plan/1");
    check(value.at("windows"));
    require(value.at("plan_sha256") == value.at("windows").at("sha256"),
            "Declared plan identity differs from authoritative windows bytes");
    check(value.at("joins"));
    check(value.at("parents"));
    require(read(value.at("parents").at("path").get<std::string>()).size() == 64,
            "Full64 parent plan census differs");
    const auto config = read(connector_root() / "config/uncertainty-feedback-v1.json");
    require(value.at("audit").at("sha256") == config.at("inputs").at("audit_sha256"),
            "Plan lost frozen nomination audit root");
    check(value.at("audit"));
    const auto joins = read(value.at("joins").at("path").get<std::string>());
    require(joins.is_array() && joins.size() == 512 &&
                    integer(value.at("nomination_count")) == joins.size(),
            "Fixed complete plan census differs");
    std::string canonical;
    for (std::size_t i = 0; i < joins.size(); ++i) {
        const auto& row = joins.at(i);
        const auto& window = row.at("window");
        require(integer(row.at("query_index")) == i && integer(window.at("query_index")) == i &&
                        window.at("schema") == "graph-prior-window/1",
                "Plan/window stable query join differs");
        const std::set<std::string> expected = {
                "schema",      "query_index", "read_id",   "contig",     "ref_start",
                "ref_end",     "core_start",  "core_end",  "read_start", "read_end",
                "chunk_index", "chunk_start", "chunk_end", "t_start",    "t_end",
                "reverse",     "stock",       "context",   "score_file"};
        std::set<std::string> supplied;
        for (const auto& [key, item] : window.items()) {
            static_cast<void>(item);
            supplied.insert(key);
        }
        require(supplied == expected, "Authoritative Window field census differs");
        canonical += window.dump() + "\n";
    }
    require(text(value.at("windows").at("path").get<std::string>()) == canonical,
            "Plan joins differ from authoritative windows bytes");
}
namespace {
std::string shell_quote(const std::string& value) {
    if (!value.empty() &&
        value.find_first_not_of(
                "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_@%+=:,./-") ==
                std::string::npos) {
        return value;
    }
    std::string result = "'";
    for (const auto character : value) {
        result += character == '\'' ? "'\"'\"'" : std::string(1, character);
    }
    return result + '\'';
}
std::string joined(const Json& argv, bool shell) {
    require(argv.is_array() && !argv.empty(), "Nonempty literal argv required");
    std::string result;
    for (const auto& item : argv) {
        const auto value = item.get<std::string>();
        if (!result.empty()) {
            result += ' ';
        }
        result += shell ? shell_quote(value) : value;
    }
    return result;
}
std::string clock_key(std::string value) {
    require(!value.empty() && value.back() == '\n', "Raw clock LF required");
    value.pop_back();
    require(value.size() == 20 || value.size() == 25 || value.size() == 32,
            "Raw UTC clock shape differs");
    require(value[4] == '-' && value[7] == '-' && value[10] == 'T' && value[13] == ':' &&
                    value[16] == ':',
            "Raw UTC clock separators differ");
    for (std::size_t i = 0; i < 19; ++i) {
        if (i != 4 && i != 7 && i != 10 && i != 13 && i != 16) {
            require(value[i] >= '0' && value[i] <= '9', "Raw UTC clock digit differs");
        }
    }
    if (value.size() == 32) {
        require(value[19] == '.', "Raw UTC fraction differs");
        for (std::size_t i = 20; i < 26; ++i) {
            require(value[i] >= '0' && value[i] <= '9', "Raw UTC fraction digit differs");
        }
    }
    require((value.size() == 20 && value.ends_with('Z')) ||
                    (value.size() == 25 && value.substr(19) == "+00:00") ||
                    (value.size() == 32 && value.substr(26) == "+00:00"),
            "Raw UTC offset differs");
    return value.substr(0, 19) + (value.size() == 32 ? value.substr(20, 6) : "000000");
}
Json runtime_libraries(const Json& receipt) {
    const auto stdout_pin = receipt.at("raw_files").at(5);
    std::istringstream input(text(stdout_pin.at("path").get<std::string>(), 1048576));
    std::string line;
    std::set<fs::path> paths;
    while (std::getline(input, line)) {
        require(line.find("not found") == std::string::npos, "Runtime library unresolved");
        std::istringstream tokens(line);
        std::string token;
        bool found = false;
        while (tokens >> token) {
            if (token.starts_with('/')) {
                paths.insert(fs::canonical(token));
                found = true;
            }
        }
        require(found || line.find("linux-vdso") != std::string::npos,
                "Unsupported runtime-inspection output");
    }
    require(!paths.empty(), "Runtime library closure is empty");
    Json result = Json::array();
    for (const auto& path : paths) {
        result.push_back(pin(path));
    }
    return result;
}
}
Json command_environment() {
    return {{"HOME", "/home/jake"},
            {"PATH", "/usr/bin:/bin"},
            {"LC_ALL", "C"},
            {"UV_PROJECT_ENVIRONMENT", "/home/jake/Projects/nanopore_basecaller-retrieval/.venv"},
            {"UV_OFFLINE", "1"},
            {"UV_PYTHON_DOWNLOADS", "never"},
            {"PYTHONDONTWRITEBYTECODE", "1"}};
}
namespace {
void receipt_in_context(const Json& value,
                        const Json& binary,
                        const Json& argv,
                        const Json& inputs,
                        const Json& witness,
                        const fs::path& cwd) {
    require(value.at("schema") == "uncertainty-feedback-command/1" &&
                    value.at("complete") == true && value.at("source_witness") == witness,
            "Actual producer completion/source context differs");
    check(binary);
    require(value.at("binary") == binary && value.at("argv") == argv &&
                    value.at("inputs") == inputs && value.at("exit_status") == 0,
            "Actual producer binary/argv/input tuple/status differs");
    for (const auto& item : inputs) {
        check(item);
    }
    const std::vector<std::string> names = {"command.sh",      "cwd.txt", "start.txt", "end.txt",
                                            "exit-status.txt", "stdout",  "stderr",    "time.txt"};
    require(value.at("raw_files").is_array() && value.at("raw_files").size() == names.size(),
            "Actual producer raw8 inventory differs");
    fs::path directory;
    for (std::size_t i = 0; i < names.size(); ++i) {
        const auto& item = value.at("raw_files").at(i);
        check(item);
        const fs::path path = item.at("path").get<std::string>();
        if (i == 0) {
            directory = path.parent_path();
        }
        require(path.parent_path() == directory && path.filename() == names[i],
                "Actual producer raw8 names/directories differ");
    }
    require(text(directory / "command.sh", 65536) == joined(argv, true) + "\n" &&
                    text(directory / "cwd.txt", 4096) == cwd.string() + "\n" &&
                    text(directory / "exit-status.txt", 32) == "0\n",
            "Actual raw command/cwd/exit differs");
    require(clock_key(text(directory / "start.txt", 128)) <=
                    clock_key(text(directory / "end.txt", 128)),
            "Actual raw clocks reversed");
    std::istringstream timing(text(directory / "time.txt", 65536));
    std::string line;
    std::map<std::string, std::string> rows;
    while (std::getline(timing, line)) {
        if (line.starts_with('\t')) {
            const auto split_at = line.find(": ");
            if (split_at != std::string::npos) {
                require(rows.emplace(line.substr(1, split_at - 1), line.substr(split_at + 2))
                                .second,
                        "Duplicate GNU time field");
            }
        }
    }
    require(rows.at("Exit status") == "0" &&
                    rows.at("Command being timed") == '"' + joined(argv, false) + '"',
            "Actual GNU time command/exit differs");
}
}
void validate_receipt(const Json& value, const Json& binary, const Json& argv, const Json& inputs) {
    validate_completion(value, "uncertainty-feedback-command/1");
    receipt_in_context(value, binary, argv, inputs, legacy_witness(), connector_root());
}
void validate_runtime(const Json& runtime_pin, const Json& binary) {
    check(runtime_pin);
    const auto value = read(runtime_pin.at("path").get<std::string>());
    validate_completion(value, "uncertainty-feedback-runtime/1");
    require(value.at("binary") == binary, "Runtime binary binding differs");
    check(value.at("inspection"));
    const auto receipt = read(value.at("inspection").at("path").get<std::string>());
    const auto inspector = dependencies().at("runtime_inspector");
    validate_receipt(receipt, inspector, Json::array({inspector.at("path"), binary.at("path")}),
                     Json::array({binary}));
    require(receipt.at("environment") == command_environment() && receipt.at("runtime").is_null() &&
                    receipt.at("extra_runtimes").empty(),
            "Runtime-inspection clean bootstrap differs");
    require(value.at("libraries") == runtime_libraries(receipt),
            "Actual runtime library closure differs");
    for (const auto& item : value.at("libraries")) {
        check(item);
    }
}
void complete(const fs::path& output, const std::string& schema, Json value) {
    verify_sources();
    value["schema"] = schema;
    value["complete"] = true;
    value["source_witness"] = source_witness();
    value["consumer_binary"] = pin(fs::canonical("/proc/self/exe"));
    if (!value.contains("truth_input")) {
        value["truth_input"] = false;
    }
    value["hg005_input"] = false;
    write(output / "complete.json", value);
    const int directory = ::open(output.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
    require(directory >= 0, "Output directory sync open failed");
    const int synced = ::fsync(directory), closed = ::close(directory);
    require(synced == 0 && closed == 0, "Output directory sync/close failed");
}
void output_directory(const fs::path& output) {
    require(output.is_absolute() && !fs::exists(output), "Fresh absolute output required");
    fs::create_directories(output);
}
}
