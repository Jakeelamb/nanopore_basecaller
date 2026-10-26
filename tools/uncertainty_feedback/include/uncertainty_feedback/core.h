#pragma once
#include "json.hpp"

#include <filesystem>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace uncertainty_feedback {
namespace fs = std::filesystem;
using Json = nlohmann::json;
using Fields = std::map<std::string, std::string>;
void require(bool condition, const std::string& message);
std::size_t natural(const std::string& text);
std::size_t integer(const Json& value);
std::vector<std::string> split(const std::string& text, char delimiter = '\t');
std::string text(const fs::path& path, std::uintmax_t maximum = 16777216);
std::string sha256(const fs::path& path);
std::string hash_text(const std::string& value);
Json pin(const fs::path& path);
void check(const Json& value);
Json parse(const std::string& bytes);
Json read(const fs::path& path, std::uintmax_t maximum = 16777216);
void fresh(const fs::path& path, const std::string& bytes);
void write(const fs::path& path, const Json& value);
Fields metadata(const fs::path& path);
Fields fields(const fs::path& path, const std::string& schema);
void tabular(const fs::path& path, const std::string& schema, const Fields& values);
void add_pin(Fields& fields, const std::string& prefix, const Json& value);
std::string reverse_complement(std::string value);
void dna(const std::string& value);
std::vector<std::pair<std::size_t, char>> cigar(const std::string& value);
std::vector<std::size_t> emissions(const Fields& value);
Json source_witness();
void verify_sources();
void validate_completion(const Json& value, const std::string& schema);
void validate_plan(const Json& value);
void validate_receipt(const Json& value, const Json& binary, const Json& argv, const Json& inputs);
void validate_runtime(const Json& runtime_pin, const Json& binary);
void validate_scalar_build(const Json& value);
Json dependencies();
fs::path connector_root();
void validate_nomination_worker(const Json& worker,
                                const std::string& phase,
                                const Json& source_id,
                                const Json& prepared);
Json frozen_masks(const Json& supplied);
Json scalar_build_inputs();
Json scalar_build_argv();
Json command_environment();
void seal_runtime(const Json& request, const fs::path& output);
void complete(const fs::path& output, const std::string& schema, Json value);
Json load_complete(const fs::path& path, const std::string& expected, const std::string& schema);
void output_directory(const fs::path& output);
Json project(const Json& window, const Json& graph);
void plan(const Json& config, const fs::path& output);
void batch(const Json& planned, const std::vector<std::size_t>& ids, const fs::path& output);
void qualify_graph(const Json& config,
                   const Json& planned,
                   const Json& batch_manifest,
                   const Json& raw_receipt,
                   const fs::path& raw,
                   const fs::path& output);
void frame_requests(const Json& planned, const Json& qualified, const fs::path& output);
void frames(const Json& planned, const Json& qualified, const Json& scalar, const fs::path& output);
void apply(const Json& planned, const Json& decoded, const fs::path& output);
void exposure(const Json& request, const fs::path& output);
int controls();
}
