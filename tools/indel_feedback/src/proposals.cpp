#include "indel_feedback/core.h"

#include <algorithm>
#include <cmath>
#include <map>

namespace indel_feedback {
namespace {
std::size_t base(char value) {
  const auto found = std::string("ACGT").find(value);
  require(found != std::string::npos, "invalid CRF symbol");
  return found;
}
std::pair<std::size_t, std::size_t> step(std::size_t old, char value,
                                         std::size_t k) {
  const auto next =
      ((old << 2U) & ((std::size_t{1} << (2U * k)) - 1U)) | base(value);
  return {next, 4U * next + (old >> (2U * (k - 1U)))};
}
double add(double a, double b) {
  if (a == -std::numeric_limits<double>::infinity()) {
    return b;
  }
  if (b == -std::numeric_limits<double>::infinity()) {
    return a;
  }
  const auto maximum = std::max(a, b);
  return maximum + std::log(std::exp(a - maximum) + std::exp(b - maximum));
}
} // namespace
void validate(const Frame &frame) {
  require(frame.state_length >= 1 && frame.state_length <= 4 &&
              frame.timesteps >= 1 && frame.timesteps <= 256,
          "bounded CRF geometry differs");
  const auto states = std::size_t{1} << (2U * frame.state_length);
  require(frame.initial_state < states &&
              frame.scores.size() == frame.timesteps * states * 4U &&
              std::isfinite(frame.stay_score) &&
              std::all_of(
                  frame.scores.begin(), frame.scores.end(),
                  [](double value) { return std::isfinite(value); }),
          "invalid CRF state/score tensor");
}
double likelihood(const Frame &frame, const std::string &sequence) {
  validate(frame);
  dna(sequence);
  require(sequence.size() <= 128, "sequence likelihood length cap");
  const auto columns = std::size_t{1} << (2U * (frame.state_length + 1U));
  std::vector<std::size_t> indices;
  std::size_t state = frame.initial_state;
  for (const auto value : sequence) {
    const auto [next, index] = step(state, value, frame.state_length);
    state = next;
    indices.push_back(index);
  }
  std::vector<double> masses(sequence.size() + 1,
                             -std::numeric_limits<double>::infinity());
  masses[0] = 0;
  for (std::size_t row = 0; row < frame.timesteps; ++row) {
    for (std::size_t emitted = sequence.size(); emitted > 0; --emitted) {
      masses[emitted] =
          add(masses[emitted] + frame.stay_score,
              masses[emitted - 1] +
                  frame.scores[row * columns + indices[emitted - 1]]);
    }
    masses[0] += frame.stay_score;
  }
  return masses.back();
}
std::vector<Proposal> proposals(const Frame &frame,
                                const std::string &available_segment) {
  validate(frame);
  dna(available_segment);
  require(!available_segment.empty() && available_segment.size() <= 32,
          "available native segment length bound");
  std::map<std::string, Proposal> unique;
  const auto put = [&](Edit edit, const std::string &mechanism) {
    auto sequence = available_segment;
    sequence.replace(edit.begin, edit.end - edit.begin, edit.replacement);
    if (!unique.contains(sequence)) {
      const auto score = likelihood(frame, sequence);
      unique.emplace(sequence,
                     Proposal{sequence, score, std::move(edit), mechanism});
    }
    require(unique.size() <= 512,
            "indel proposal count exceeded predeclared cap");
  };
  put({0, available_segment.size(), available_segment}, "identity");
  for (std::size_t position = 0; position < available_segment.size();
       ++position) {
    put({position, position + 1, ""}, "single-deletion");
  }
  for (std::size_t position = 0; position <= available_segment.size();
       ++position) {
    for (const auto symbol : std::string("ACGT")) {
      put({position, position, std::string(1, symbol)}, "single-insertion");
    }
  }
  std::size_t begin{};
  while (begin < available_segment.size()) {
    auto end = begin + 1;
    while (end < available_segment.size() &&
           available_segment[end] == available_segment[begin]) {
      ++end;
    }
    const auto old_length = end - begin;
    if (old_length >= 2) {
      for (std::size_t length = 1; length <= 6; ++length) {
        const auto difference =
            length > old_length ? length - old_length : old_length - length;
        if (difference <= 2) {
          put({begin, end, std::string(length, available_segment[begin])},
              "run-length-plus-minus-two");
        }
      }
    }
    begin = end;
  }
  std::vector<Proposal> result;
  for (auto &[sequence, proposal] : unique) {
    static_cast<void>(sequence);
    result.push_back(std::move(proposal));
  }
  return result;
}
std::pair<std::string, std::string> apply_edits(const std::string &sequence,
                                                const std::string &quality,
                                                std::vector<Edit> edits,
                                                bool enabled, bool reverse) {
  dna(sequence, true);
  require(sequence.size() == quality.size() &&
              std::all_of(quality.begin(), quality.end(),
                          [](char c) { return c >= 33 && c <= 126; }),
          "native complete SEQ/Q differs");
  std::sort(edits.begin(), edits.end(), [](const Edit &a, const Edit &b) {
    return std::pair{a.begin, a.end} < std::pair{b.begin, b.end};
  });
  auto oriented_sequence = reverse ? reverse_complement(sequence) : sequence;
  auto oriented_quality = quality;
  if (reverse) {
    std::reverse(oriented_quality.begin(), oriented_quality.end());
  }
  std::size_t previous{};
  bool first = true;
  std::size_t previous_begin{};
  for (const auto &edit : edits) {
    dna(edit.replacement);
    require(
        edit.begin <= edit.end && edit.end <= sequence.size() &&
            (first || (previous <= edit.begin && previous_begin != edit.begin)),
        "edits overlap, share an insertion boundary or exceed native parent");
    previous = edit.end;
    previous_begin = edit.begin;
    first = false;
  }
  if (!enabled) {
    return {sequence, quality};
  }
  std::string rebuilt_sequence, rebuilt_quality;
  std::size_t cursor{};
  for (const auto &edit : edits) {
    rebuilt_sequence += oriented_sequence.substr(cursor, edit.begin - cursor) +
                        edit.replacement;
    rebuilt_quality += oriented_quality.substr(cursor, edit.begin - cursor) +
                       std::string(edit.replacement.size(), '!');
    cursor = edit.end;
  }
  rebuilt_sequence += oriented_sequence.substr(cursor);
  rebuilt_quality += oriented_quality.substr(cursor);
  auto independent_sequence = oriented_sequence,
       independent_quality = oriented_quality;
  for (auto it = edits.rbegin(); it != edits.rend(); ++it) {
    independent_sequence.replace(it->begin, it->end - it->begin,
                                 it->replacement);
    independent_quality.replace(it->begin, it->end - it->begin,
                                std::string(it->replacement.size(), '!'));
  }
  require(rebuilt_sequence == independent_sequence &&
              rebuilt_quality == independent_quality,
          "independent full SEQ/Q reconstruction differs");
  if (reverse) {
    rebuilt_sequence = reverse_complement(rebuilt_sequence);
    std::reverse(rebuilt_quality.begin(), rebuilt_quality.end());
  }
  return {rebuilt_sequence, rebuilt_quality};
}
} // namespace indel_feedback
