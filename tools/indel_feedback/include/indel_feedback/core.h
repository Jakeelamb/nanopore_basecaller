#pragma once

#include "json.hpp"

#include <cstddef>
#include <filesystem>
#include <limits>
#include <map>
#include <string>
#include <utility>
#include <vector>

namespace indel_feedback {
using Json = nlohmann::json;
using Span = std::pair<std::size_t, std::size_t>;
using Spans = std::vector<Span>;
namespace fs = std::filesystem;
void require(bool condition, const std::string &message);
void dna(const std::string &sequence, bool allow_n = false);
std::size_t natural(const std::string &value);
std::vector<std::string> split(const std::string &line, char delimiter = '\t');
std::vector<std::pair<std::size_t, char>> cigar(const std::string &text);
std::string reverse_complement(const std::string &sequence);
std::string digest(const std::string &bytes);
std::string file_digest(const fs::path &path);
Json pin(const fs::path &path);
void check_pin(const Json &value);
Json read_json(const fs::path &path,
               std::uintmax_t maximum = 8U * 1024U * 1024U);
void fresh(const fs::path &path, const std::string &bytes);
void verify_sources();
Json source_witness();

struct Counts {
  std::size_t m{}, x{}, i{}, d{};
  Counts &operator+=(const Counts &other);
  bool operator==(const Counts &) const = default;
};
Json counts_json(const Counts &counts);
struct Geometry {
  std::vector<std::size_t> boundaries;
  Spans overlaps;
  std::size_t radius{};
};
struct Classified {
  Counts counts;
  Json events = Json::array();
  std::size_t insertion_events{}, deletion_events{}, substitution_events{};
  std::size_t excluded_insertion_events{}, excluded_deletion_bases{},
      excluded_query_bases{};
};
Classified classify_alignment(const std::string &sequence,
                              const std::string &quality,
                              const std::string &reference, std::size_t start,
                              const std::string &cigar_text,
                              const Spans &domain,
                              const Geometry *geometry = nullptr);
Json classify_request(const Json &request);

struct Frame {
  std::size_t timesteps{}, state_length{}, initial_state{};
  double stay_score{};
  std::vector<double> scores;
};
void validate(const Frame &frame);
double likelihood(const Frame &frame, const std::string &sequence);
struct Edit {
  std::size_t begin{}, end{};
  std::string replacement;
  bool operator==(const Edit &) const = default;
};
struct Proposal {
  std::string sequence;
  double neural_log_likelihood{-std::numeric_limits<double>::infinity()};
  Edit edit;
  std::string mechanism;
};
std::vector<Proposal> proposals(const Frame &frame,
                                const std::string &available_segment);
std::pair<std::string, std::string> apply_edits(const std::string &sequence,
                                                const std::string &quality,
                                                std::vector<Edit> edits,
                                                bool enabled, bool reverse);
Json propose_request(const Json &request);
void controls();
} // namespace indel_feedback
