#include "indel_feedback/core.h"

#include <algorithm>
#include <functional>
#include <iostream>
#include <stdexcept>

namespace indel_feedback {
void prefix_controls() {
  std::size_t passed{};
  const auto check = [&](const std::string &name, const std::function<void()> &test) {
    test();
    ++passed;
    std::cout << "PASS " << name << '\n';
  };
  check("prefix deterministic full sequence edits", [] {
    const std::string native = "ACGTAA";
    const auto first = nominate_prefix(native, 8, {native, "ACGTA"});
    const auto second = nominate_prefix(native, 8, {"ACGTA", native});
    require(first.status == PrefixNominationStatus::ready &&
                first.proposals.size() == second.proposals.size(),
            "prefix order changed proposal census");
    for (std::size_t i = 0; i < first.proposals.size(); ++i) {
      const auto &proposal = first.proposals[i];
      const auto &other = second.proposals[i];
      auto rebuilt = native;
      rebuilt.replace(proposal.edit.begin, proposal.edit.end - proposal.edit.begin,
                      proposal.edit.replacement);
      require(rebuilt == proposal.sequence && proposal.sequence == other.sequence &&
                  proposal.edit == other.edit && proposal.mechanism == other.mechanism &&
                  proposal.sequence != native && proposal.sequence != "ACGTA",
              "prefix edit or original exclusion differs");
    }
  });
  check("prefix exact full and row bounds", [] {
    const auto maximum = nominate_prefix(std::string(512, 'A'), 2048, {});
    require(maximum.status == PrefixNominationStatus::ready &&
                maximum.tail_begin == 480 && maximum.tail_end == 512 &&
                !maximum.proposals.empty(),
            "prefix exact boundary rejected");
    for (const auto &[sequence, rows] :
         std::vector<std::pair<std::string, std::size_t>>{
             {"", 1}, {std::string(513, 'A'), 2048}, {"AC", 0}, {"AC", 2049}}) {
      const auto result = nominate_prefix(sequence, rows, {});
      require(result.status == PrefixNominationStatus::excluded &&
                  result.proposals.empty() && !result.arm_exclusions.empty() &&
                  result.visited == 0,
              "prefix overrun did not exclude whole new arm");
    }
  });
  check("prefix empty result and tail open run exclusions", [] {
    const auto single = nominate_prefix("A", 1, {"A"});
    require(single.excluded == 1 && single.exclusions.size() == 1 &&
                single.exclusions.at(0).at("reason").get<std::string>() == "empty-result",
            "empty result exclusion missing");
    const auto open = nominate_prefix(std::string(34, 'A'), 40, {});
    require(open.tail_begin == 2 && open.excluded == 1 &&
                open.exclusions.at(0).at("reason").get<std::string>() == "left-open-run",
            "left open run provenance missing");
    require(std::all_of(open.proposals.begin(), open.proposals.end(), [](const auto &proposal) {
              return proposal.mechanism != "run-length-plus-minus-two" && !proposal.sequence.empty();
            }),
            "left open run expanded");
    const auto visible = nominate_prefix("GGAA", 8, {});
    require(std::any_of(visible.proposals.begin(), visible.proposals.end(), [](const auto &proposal) {
              return proposal.sequence == "GGAAAA" && proposal.mechanism == "run-length-plus-minus-two";
            }),
            "visible maximal run plus two absent");
  });
  check("prefix tail preserves every earlier base", [] {
    std::string native;
    for (std::size_t i = 0; i < 20; ++i) {
      native += "ACGT";
    }
    const auto result = nominate_prefix(native, 128, {native});
    require(result.tail_begin == 48, "prefix tail endpoint differs");
    for (const auto &proposal : result.proposals) {
      require(proposal.edit.begin >= 48 && proposal.edit.end <= native.size() &&
                  proposal.sequence.substr(0, 48) == native.substr(0, 48) &&
                  !proposal.sequence.empty() && proposal.sequence.size() <= 514,
              "prefix tail edit changed earlier sequence");
    }
  });
  check("prefix enumeration counts without hidden clipping", [] {
    const auto result = nominate_prefix("ACGTACGTACGTACGTACGTACGTACGTACGT", 64, {});
    require(result.visited == 164 && result.eligible == 164 &&
                result.unique == 132 && result.duplicate == 32 && result.excluded == 0 &&
                result.proposals.size() == 132 && result.arm_exclusions.empty(),
            "prefix nomination was clipped or counted twice");
    require(result.visited == result.eligible + result.excluded &&
                result.eligible == result.unique + result.duplicate,
            "prefix count conservation differs");
  });
  check("prefix noncanonical sequence rejects", [] {
    bool rejected = false;
    try {
      static_cast<void>(nominate_prefix("ACGN", 8, {}));
    } catch (const std::invalid_argument &) {
      rejected = true;
    }
    require(rejected, "noncanonical prefix accepted");
  });
  std::cout << "prefix_controls_executed=" << passed << " skipped=0\n";
}
} // namespace indel_feedback
