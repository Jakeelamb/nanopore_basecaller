#include "indel_feedback/core.h"

#include <algorithm>
#include <cmath>
#include <functional>
#include <iostream>
#include <map>
#include <stdexcept>

namespace indel_feedback {
namespace {
void expect(bool value, const std::string &message) {
  require(value, "control: " + message);
}
void rejects(const std::function<void()> &function) {
  bool rejected{};
  try {
    function();
  } catch (const std::invalid_argument &) {
    rejected = true;
  }
  expect(rejected, "invalid input accepted");
}
Frame peaked(const std::string &target) {
  Frame result{target.size(), 1, 0, -8,
               std::vector<double>(target.size() * 16, -20)};
  std::size_t state{};
  for (std::size_t row = 0; row < target.size(); ++row) {
    const auto next = std::string("ACGT").find(target[row]);
    result.scores[row * 16 + next * 4 + state] = 3;
    state = next;
  }
  return result;
}
std::map<std::string, long double> census(const Frame &frame) {
  std::map<std::string, long double> masses;
  const auto columns = std::size_t{1} << (2U * (frame.state_length + 1U));
  const auto mask = (std::size_t{1} << (2U * frame.state_length)) - 1U;
  std::function<void(std::size_t, std::size_t, const std::string &,
                     long double)>
      visit;
  visit = [&](std::size_t row, std::size_t state, const std::string &sequence,
              long double mass) {
    if (row == frame.timesteps) {
      masses[sequence] += mass;
      return;
    }
    visit(row + 1, state, sequence,
          mass * std::exp(static_cast<long double>(frame.stay_score)));
    for (std::size_t symbol = 0; symbol < 4; ++symbol) {
      // Explicit tiny path census: sum in linear long-double space, not the
      // production DP.
      const auto next = (state * 4 + symbol) & mask;
      const auto old_prefix =
          state / (std::size_t{1} << (2U * (frame.state_length - 1U)));
      const auto value = frame.scores[row * columns + next * 4 + old_prefix];
      visit(row + 1, next, sequence + std::string("ACGT")[symbol],
            mass * std::exp(static_cast<long double>(value)));
    }
  };
  visit(0, frame.initial_state, "", 1);
  return masses;
}
} // namespace
void controls() {
  std::size_t passed{};
  const auto check = [&](const std::string &name,
                         const std::function<void()> &function) {
    function();
    ++passed;
    std::cout << "PASS " << name << '\n';
  };
  check("tiny exhaustive census and total marginal mass", [] {
    for (std::size_t k = 1; k <= 2; ++k) {
      for (std::size_t t = 1; t <= 4; ++t) {
        const auto columns = std::size_t{1} << (2U * (k + 1U));
        Frame frame{t, k, 1, -0.3, std::vector<double>(t * columns)};
        for (std::size_t i = 0; i < frame.scores.size(); ++i) {
          frame.scores[i] = static_cast<double>(i % 11U) / 10.0 - 0.7;
        }
        long double exact_mass{}, dp_mass{};
        for (const auto &[sequence, mass] : census(frame)) {
          const auto observed = likelihood(frame, sequence);
          const auto expected = static_cast<double>(std::log(mass));
          expect(std::abs(observed - expected) < 1e-11,
                 "marginal likelihood differs from full path census");
          exact_mass += mass;
          dp_mass += std::exp(static_cast<long double>(observed));
        }
        expect(std::abs(exact_mass - dp_mass) < 1e-10L * exact_mass,
               "total sequence mass differs from all paths");
        expect(likelihood(frame, std::string(t + 1, 'A')) ==
                   -std::numeric_limits<double>::infinity(),
               "impossible sequence has mass");
      }
    }
  });
  check("repeated paths aggregate instead of Viterbi", [] {
    Frame frame{3, 1, 0, 0, std::vector<double>(48, 0)};
    expect(std::abs(likelihood(frame, "A") - std::log(3.0)) < 1e-12 &&
               std::abs(likelihood(frame, "AA") - std::log(3.0)) < 1e-12 &&
               likelihood(frame, "") == 0,
           "stay path multiplicity lost");
  });
  check("known run lengths two three four", [] {
    for (std::size_t length = 2; length <= 4; ++length) {
      const auto candidates =
          proposals(peaked(std::string(length, 'A')),
                    std::string(length == 4 ? 3 : length + 1, 'A'));
      const auto winner = std::max_element(candidates.begin(), candidates.end(),
                                           [](const auto &a, const auto &b) {
                                             return a.neural_log_likelihood <
                                                    b.neural_log_likelihood;
                                           });
      expect(winner != candidates.end() &&
                 winner->sequence == std::string(length, 'A'),
             "incorrect signal run length");
    }
  });
  check("nonrepeat insertion ambiguity", [] {
    const auto candidates = proposals(peaked("ACGT"), "ACT");
    const auto winner = std::max_element(
        candidates.begin(), candidates.end(), [](const auto &a, const auto &b) {
          return a.neural_log_likelihood < b.neural_log_likelihood;
        });
    expect(winner->sequence == "ACGT" &&
               winner->mechanism == "single-insertion",
           "nonrepeat indel missing");
  });
  check("bounded deterministic nomination without truth", [] {
    const auto frame = peaked("AAAA");
    const auto first = proposals(frame, "AAA"),
               second = proposals(frame, "AAA");
    expect(first.size() == second.size() && first.size() <= 512,
           "nomination cap/determinism");
    for (std::size_t i = 0; i < first.size(); ++i) {
      expect(first[i].sequence == second[i].sequence &&
                 first[i].edit == second[i].edit,
             "unstable proposal");
      expect(apply_edits("AAA", "123", {first[i].edit}, true, false).first ==
                 first[i].sequence,
             "proposal reconstruction");
    }
    rejects([&] { static_cast<void>(proposals(frame, std::string(33, 'A'))); });
  });
  check("both terminal insertions excluded", [] {
    const auto result =
        classify_alignment("TACGTA", "123456", "ACGT", 0, "1I4=1I", {{0, 4}});
    expect(result.counts == Counts{4, 0, 0, 0} &&
               result.excluded_insertion_events == 2 &&
               result.excluded_query_bases == 2,
           "terminal insertion policy");
  });
  check("two flank insertion and gap rejection", [] {
    const auto yes =
        classify_alignment("ACAGT", "12345", "ACGT", 0, "2=1I2=", {{1, 3}});
    const auto no = classify_alignment("ACAGT", "12345", "ACGT", 0,
                                       "2=1I2=", {{0, 2}, {3, 4}});
    expect(yes.counts == Counts{2, 0, 1, 0} && yes.insertion_events == 1 &&
               no.counts.i == 0 && no.excluded_insertion_events == 1,
           "two flank convention differs");
  });
  check("deletion boundaries and event base separation", [] {
    const auto result =
        classify_alignment("AC", "12", "GACG", 0, "1D2=1D", {{0, 4}});
    expect(result.counts == Counts{2, 0, 0, 2} && result.deletion_events == 2,
           "boundary deletion counts");
    const auto crossing =
        classify_alignment("ACT", "123", "ACCCGT", 0, "2=3D1=", {{1, 3}});
    expect(crossing.counts == Counts{1, 0, 0, 1} &&
               crossing.deletion_events == 1 &&
               crossing.excluded_deletion_bases == 2 &&
               crossing.events.at(0).at("crossing_domain") == true,
           "crossing deletion split/double-count");
  });
  check("adjacent insertion deletion", [] {
    const auto result =
        classify_alignment("ATG", "123", "ACG", 0, "1=1I1D1=", {{0, 3}});
    expect(result.counts == Counts{2, 0, 1, 1} &&
               result.insertion_events == 1 && result.deletion_events == 1,
           "adjacent indel conservation");
  });
  check("repeat annotation and chunk overlap are not partitions", [] {
    Geometry geometry{{3, 4}, {{2, 5}}, 1};
    const auto result = classify_alignment("CAAAAGT", "1234567", "CAAAGT", 0,
                                           "4=1I2=", {{0, 6}}, &geometry);
    const auto &annotation = result.events.at(0).at("annotations");
    expect(result.counts.i == 1 &&
               annotation.at("homopolymer_compatible") == true &&
               annotation.at("chunk_overlap") == true &&
               annotation.at("chunk_boundary_near") == true &&
               result.insertion_events == 1,
           "overlapping annotations changed totals");
    const auto other =
        classify_alignment("CATGT", "12345", "CAGT", 0, "2=1I2=", {{0, 4}});
    expect(
        other.events.at(0).at("annotations").at("unknown_mechanism") == true &&
            other.events.at(0).at("annotations").at("chunk_overlap").is_null(),
        "unknown/missing geometry lost");
  });
  check("zero exposure preserves no counted events", [] {
    const auto result =
        classify_alignment("ATG", "123", "ACG", 0, "1=1I1D1=", {});
    expect(result.counts == Counts{} && result.events.empty() &&
               result.excluded_insertion_events == 1 &&
               result.excluded_deletion_bases == 1,
           "zero domain accrued errors");
  });
  check("reverse SAM uses alignment oriented SEQ", [] {
    const auto result =
        classify_alignment("ACGA", "1234", "ACGA", 0, "4=", {{0, 4}});
    expect(result.counts.m == 4, "alignment orientation changed");
    rejects([] {
      static_cast<void>(
          classify_alignment("TCGT", "4321", "ACGA", 0, "4=", {{0, 4}}));
    });
  });
  check("full forward reverse and disabled SEQ Q", [] {
    const std::vector<Edit> edits{{1, 2, "TT"}, {4, 5, ""}};
    const auto forward = apply_edits("ACGTAC", "123456", edits, true, false);
    expect(forward == std::pair{std::string("ATTGTC"), std::string("1!!346")},
           "full forward reconstruction");
    const auto reverse =
        apply_edits(reverse_complement("ACGTAC"), "654321", edits, true, true);
    expect(reverse.first == reverse_complement(forward.first) &&
               reverse.second == "643!!1",
           "full reverse reconstruction");
    expect(apply_edits("ACGTAC", "123456", edits, false, false) ==
               std::pair{std::string("ACGTAC"), std::string("123456")},
           "disabled identity differs");
    rejects([] {
      static_cast<void>(
          apply_edits("ACGT", "1234", {{1, 3, "A"}, {2, 4, "G"}}, true, false));
    });
    rejects([] {
      static_cast<void>(
          apply_edits("ACGT", "1234", {{1, 1, "A"}, {1, 1, "G"}}, true, false));
    });
  });
  check("invalid score geometry alphabet CIGAR rejects", [] {
    rejects([] {
      static_cast<void>(
          likelihood(Frame{1, 1, 4, 0, std::vector<double>(16)}, "A"));
    });
    rejects([] { static_cast<void>(likelihood(peaked("AC"), "N")); });
    rejects([] { static_cast<void>(cigar("2M")); });
    rejects([] { static_cast<void>(cigar("2=0I")); });
    rejects([] {
      static_cast<void>(
          classify_alignment("AC", "12", "AC", 0, "3=", {{0, 2}}));
    });
  });
  std::cout << "controls_executed=" << passed << " skipped=0\n";
}
} // namespace indel_feedback
