#pragma once
#include "json.hpp"

#include <cstdint>
#include <filesystem>
#include <map>
#include <set>
#include <string>
#include <variant>
#include <vector>

namespace archive_consumer {
namespace fs = std::filesystem;
using Json = nlohmann::json;
using Fields = std::map<std::string, std::string>;
inline constexpr std::uint64_t maximum_trace_bytes = 104857600;
struct FilePin {
    fs::path path;
    std::uint64_t size;
    std::string sha256;
};
struct Raw {
    FilePin original;
};
struct Gzip {
    FilePin original;
    FilePin archive;
};
using TraceStorage = std::variant<Raw, Gzip>;
struct Trace {
    std::size_t query_index;
    Json native_completion;
    Json producer;
    TraceStorage storage;
};
using TraceMap = std::map<std::size_t, Trace>;
struct Edit {
    std::size_t a, b;
    std::string replacement;
    std::size_t query;
};
std::pair<std::string, std::string> apply_edits(const std::string& original,
                                                const std::string& quality,
                                                std::vector<Edit> changes);
void require(bool condition, const std::string& message);
std::size_t natural(const std::string& value);
std::size_t integer(const Json& value);
std::vector<std::string> split(const std::string& value, char delimiter = '\t');
std::string text(const fs::path& path, std::uintmax_t maximum = 8388608);
std::string sha256(const fs::path& path);
std::string hash_text(const std::string& value);
Json pin(const fs::path& path);
void check(const Json& value);
Json parse(const std::string& bytes);
Json read(const fs::path& path, std::uintmax_t maximum = 8388608);
void fresh(const fs::path& path, const std::string& bytes);
void write(const fs::path& path, const Json& value);
Fields fields(const fs::path& path, const std::string& schema);
void add_pin(Fields& fields, const std::string& prefix, const Json& value);
void dna(const std::string& value);
Json source_witness();
void verify_sources();
Json own_dependencies();
Json legacy_witness();
Json dependencies();
fs::path connector_root();
void validate_completion(const Json& value, const std::string& schema);
void validate_plan(const Json& value);
void validate_receipt(const Json& value, const Json& binary, const Json& argv, const Json& inputs);
void validate_runtime(const Json& runtime_pin, const Json& binary);
Json command_environment();
void complete(const fs::path& output, const std::string& schema, Json value);
void output_directory(const fs::path& output);
void exact_keys(const Json& value, const std::vector<std::string>& keys);
FilePin file_pin(const Json& value);
Json as_json(const FilePin& value);
Trace parse_trace(const Json& value);
TraceMap parse_traces(const Json& descriptors, const std::set<std::size_t>& queries);
void verify_storage(const TraceStorage& storage);
void verify_codec_dependencies();
void same_catalogue(const Json& actual, const Json& expected, std::size_t count);
void validate_native_catalogue(const Json& row,
                               const Json& result,
                               const Json& seal,
                               const Json& producer,
                               const Json& argv,
                               const Json& decoder,
                               const Trace& trace);
void verify_legacy_binding(const Json& value);
void validate_geometry(const Json& planned,
                       const Json& target,
                       const Json& row,
                       const Json& result,
                       const Json& construction,
                       const Fields& base,
                       const Fields& frame);
void apply_request(const Json& request_pin, const fs::path& output);
void emit(const Json& planned,
          const Json& decoded,
          const TraceMap& traces,
          const Json& request_pin,
          const fs::path& output);
int controls(const fs::path& scratch);
}
