#pragma once
#include "json.hpp"

#include <cstddef>
#include <filesystem>
#include <optional>
#include <span>
#include <string>
#include <vector>

namespace prefix_feedback {
using Json = nlohmann::json;
namespace fs = std::filesystem;
struct Policy {
    std::size_t beam_width{128};
    std::size_t maximum_symbols{512};
    std::size_t minimum_symbols{1};
    std::size_t maximum_locations{8};
    double context_weight{0.5};
};
struct Spec {
    std::string read_id;
    std::string plan_sha256;
    std::size_t state_length{4};
    double stay_score{2.0};
    Policy policy;
    Json resource_manifest = nullptr;
};
struct Block {
    Json binding;
    std::size_t row_begin{};
    std::size_t row_end{};
    std::vector<double> scores;
};
struct Location {
    std::string id;
    std::string contig;
    std::string strand;
    std::size_t query_begin{};
    std::size_t query_end{};
    std::size_t query_length{};
    std::size_t reference_begin{};
    std::size_t reference_end{};
    std::size_t reference_length{};
    unsigned int mapq{};
    std::string cigar;
    std::string continuation;
    Json evidence;
};
struct Node {
    std::string sequence;
    std::size_t state{};
    std::size_t location{};
    double mass{};
    bool operator==(const Node&) const = default;
};
struct Session {
    Spec spec;
    std::size_t consumed_rows{};
    std::size_t next_block{};
    std::vector<Node> signal;
    std::vector<Node> conditioned;
    std::vector<Location> locations;
    std::vector<Location> first_locations;
    std::vector<Block> consumed;
    Json updates = Json::array();
    Json last_binding;
    bool signal_pruned{};
    bool conditioned_pruned{};
    bool symbol_bound{};
    bool context_bound{};
};
void require(bool condition, const std::string& message);
std::string digest(const std::string& bytes);
std::string file_digest(const fs::path& path);
Json pin(const fs::path& path);
void check_pin(const Json& value);
std::string read_text(const fs::path& path, std::size_t maximum = 8388608);
Json read_json(const fs::path& path);
void fresh(const fs::path& path, const Json& value);
void fresh_bytes(const fs::path& path, const std::string& bytes);
Json source_witness();
void verify_sources();
std::string source_id();
void dna(const std::string& value);
std::string reverse_complement(std::string value);
double log_add(double a, double b);
std::size_t transition(std::size_t previous, std::size_t base, std::size_t k, std::size_t& next);
Session start(const Spec& spec);
Json state_json(const Session& session);
Session restore(const Json& state);
std::string state_id(const Session& session);
Json batch(const Session& session, const std::string& previous_state);
void advance(Session& session, const Block& block, const std::optional<Json>& update);
Block load_block(const Json& request, const Spec& spec);
Json validate_resources(const Json& manifest, const std::string& plan_sha256);
void validate_command_evidence(const Json& receipt, const Json& expected_sources);
std::vector<Location> parse_locations(const Json& update, const Json& resources = Json::object());
Json parse_paf(const std::string& paf, const Json& query);
double likelihood(const Session& session, const std::string& sequence);
Json edits(const std::string& source, const std::string& target);
std::string apply_edits(const std::string& source, const Json& changes);
int controls();
}
