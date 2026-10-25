#include "context_model/model.h"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <tuple>

namespace context_model {
namespace {
constexpr double log_four = 1.3862943611198906188;
constexpr double zero = -std::numeric_limits<double>::infinity();
double add(double a, double b) {
    if (a == zero)
        return b;
    if (b == zero)
        return a;
    const auto high = std::max(a, b);
    return high + std::log1p(std::exp(std::min(a, b) - high));
}
void rates_valid(const MutationRates &rates) {
    for (const auto value : {rates.insertion, rates.deletion, rates.substitution})
        context_study::require(std::isfinite(value) && value > 0 && value < 1,
                               "mutation rates must be finite and strictly between zero and one");
}
std::size_t checked_add(std::size_t a, std::size_t b) {
    context_study::require(b <= std::numeric_limits<std::size_t>::max() - a,
                           "work count addition overflow");
    return a + b;
}
std::size_t checked_product(std::size_t a, std::size_t b) {
    context_study::require(a == 0 || b <= std::numeric_limits<std::size_t>::max() / a,
                           "work count multiplication overflow");
    return a * b;
}
std::vector<const context_study::Candidate *> pool(const context_study::CandidateCase &input) {
    std::vector<const context_study::Candidate *> result;
    for (const auto &[sequence, candidate] : input.candidates) {
        context_study::require(sequence == candidate.sequence, "candidate key differs from DNA");
        if ((candidate.origins & (context_study::native_origin | context_study::escape_origin)) !=
            0) {
            context_study::require(candidate.log_mass && std::isfinite(candidate.log_mass->value),
                                   "primary candidate lacks a finite retained neural mass");
            result.push_back(&candidate);
        }
    }
    context_study::require(
        !result.empty() && input.candidates.contains(input.native) &&
            (input.candidates.at(input.native).origins & context_study::native_origin) != 0,
        "primary pool lacks native candidate");
    return result;
}
bool preferred(const ScoredCandidate &a, const ScoredCandidate &b, const std::string &native) {
    if (a.objective != b.objective)
        return a.objective > b.objective;
    if ((a.sequence == native) != (b.sequence == native))
        return a.sequence == native;
    return a.sequence < b.sequence;
}
std::string number(double value) {
    std::ostringstream out;
    out << std::setprecision(17) << value;
    return out.str();
}
class Kernel {
  public:
    explicit Kernel(ModelPolicy policy) : policy_(policy) { validate(policy_); }
    ContextLogMass mass(std::string_view center, const ContextDistribution &context) {
        context_study::require(center.size() <= policy_.maximum_center &&
                                   context_study::dna(std::string(center)),
                               "candidate outside declared DNA support");
        const auto background = -std::log(static_cast<double>(policy_.maximum_center + 1)) -
                                static_cast<double>(center.size()) * log_four;
        if (policy_.novel_mass == 1)
            return {background, background, background, 0};
        double graph = zero;
        for (const auto &path : context.paths()) {
            const auto key = std::pair{path.sequence, std::string(center)};
            auto found = masses_.find(key);
            if (found == masses_.end()) {
                auto normalizer = normalizers_.find(path.sequence.size());
                if (normalizer == normalizers_.end())
                    normalizer = normalizers_
                                     .emplace(path.sequence.size(),
                                              log_length_normalizer(path.sequence.size(), policy_))
                                     .first;
                found = masses_
                            .emplace(key, log_sequence_mass(path.sequence, center, policy_.rates) -
                                              normalizer->second)
                            .first;
            }
            graph = add(graph, std::log(path.mass) + found->second);
        }
        const auto mixture =
            add(std::log(policy_.novel_mass) + background, std::log1p(-policy_.novel_mass) + graph);
        const auto ratio = mixture - background;
        context_study::require(std::isfinite(graph) && std::isfinite(mixture) &&
                                   std::isfinite(ratio),
                               "nonfinite marginalized context mass");
        return {graph, background, mixture, ratio};
    }

  private:
    ModelPolicy policy_;
    std::map<std::size_t, double> normalizers_;
    std::map<std::pair<std::string, std::string>, double> masses_;
};
ModelScores score(const context_study::CandidateCase &input, const ContextInput &context,
                  const ModelPolicy &policy, Kernel &kernel) {
    validate(policy);
    ModelScores result;
    const auto candidates = pool(input);
    for (const auto *candidate : candidates) {
        context_study::require(candidate->sequence.size() <= policy.maximum_center,
                               "eligible candidate exceeds frozen maximum center");
        const auto mass = context.distribution
                              ? kernel.mass(candidate->sequence, *context.distribution)
                              : ContextLogMass{0, 0, 0, 0};
        const auto background = -std::log(static_cast<double>(policy.maximum_center + 1)) -
                                static_cast<double>(candidate->sequence.size()) * log_four;
        const auto actual =
            context.distribution ? mass : ContextLogMass{background, background, background, 0};
        result.candidates.push_back({candidate->sequence, candidate->log_mass->value, actual,
                                     candidate->log_mass->value + actual.log_ratio});
    }
    result.baseline = result.candidates.front();
    for (auto value : result.candidates) {
        value.objective = value.signal;
        result.baseline.objective = result.baseline.signal;
        if (preferred(value, result.baseline, input.native))
            result.baseline = value;
    }
    result.baseline =
        *std::find_if(result.candidates.begin(), result.candidates.end(), [&](const auto &value) {
            return value.sequence == result.baseline.sequence;
        });
    result.raw = result.candidates.front();
    for (const auto &value : result.candidates)
        if (preferred(value, result.raw, input.native))
            result.raw = value;
    result.accepted = result.baseline;
    if (!context.distribution || policy.novel_mass == 1)
        result.gate = "reference_free_fallback";
    else if (result.raw.signal - result.baseline.signal < -0.5)
        result.gate = "signal_deficit_fallback";
    else if (result.raw.objective - result.baseline.objective < 0.5)
        result.gate = "objective_margin_fallback";
    else {
        result.accepted = result.raw;
        result.gate = "context_selected";
    }
    if (input.escape_capped || input.escape_empty) {
        result.accepted =
            *std::find_if(result.candidates.begin(), result.candidates.end(),
                          [&](const auto &value) { return value.sequence == input.native; });
        result.abstained = true;
        result.gate = input.escape_capped ? "center_bound_abstain" : "no_eligible_finalist_abstain";
    }
    return result;
}
}
std::vector<ModelPolicy> fixed_policies() {
    return {{108, {0.001, 0.001, 0.001}, 0.5}, {108, {0.01, 0.01, 0.01}, 0.5}};
}
void validate(const ModelPolicy &policy) {
    rates_valid(policy.rates);
    context_study::require(policy.maximum_center <= 108 && std::isfinite(policy.novel_mass) &&
                               policy.novel_mass > 0 && policy.novel_mass <= 1,
                           "invalid center support or novel mass");
}
ContextDistribution ContextDistribution::uniform(const std::vector<std::string> &paths,
                                                 std::string provenance) {
    const std::set<std::string> unique(paths.begin(), paths.end());
    context_study::require(!unique.empty(), "empty context is unavailable, not a distribution");
    std::vector<WeightedPath> weighted;
    for (const auto &sequence : unique)
        weighted.push_back({sequence, 1.0 / static_cast<double>(unique.size())});
    return ContextDistribution::weighted(weighted, std::move(provenance));
}
ContextDistribution ContextDistribution::weighted(const std::vector<WeightedPath> &paths,
                                                  std::string provenance) {
    context_study::require(!provenance.empty() && context_study::digest(provenance),
                           "pinned context provenance digest required");
    context_study::require(!paths.empty() && paths.size() <= 4096, "invalid context path census");
    std::map<std::string, double> merged;
    std::map<std::string, std::string> components;
    double total{};
    for (const auto &path : paths) {
        context_study::require(context_study::dna(path.sequence) && std::isfinite(path.mass) &&
                                   path.mass > 0,
                               "invalid canonical path or positive component mass");
        const auto component =
            path.component.empty() ? context_study::sha256(path.sequence) : path.component;
        context_study::require(context_study::digest(component),
                               "invalid component identity digest");
        const auto existing = components.find(component);
        context_study::require(existing == components.end() || existing->second == path.sequence,
                               "conflicting sequence aliases for one biological component");
        components[component] = path.sequence;
        total += path.mass;
        merged[path.sequence] += path.mass;
    }
    context_study::require(std::isfinite(total) && std::abs(total - 1) <= 1e-12,
                           "authoritative context masses must sum to one");
    ContextDistribution result;
    result.provenance_ = std::move(provenance);
    for (const auto &[sequence, mass] : merged)
        result.paths_.push_back({sequence, mass / total, context_study::sha256(sequence)});
    return result;
}
double log_sequence_mass(std::string_view source, std::string_view center,
                         const MutationRates &rates) {
    rates_valid(rates);
    context_study::require(context_study::dna(std::string(source)) &&
                               context_study::dna(std::string(center)) && center.size() <= 108,
                           "invalid mutation source or target DNA");
    const auto insertion = std::log(rates.insertion) - log_four;
    const auto leave = std::log1p(-rates.insertion);
    const auto deletion = leave + std::log(rates.deletion);
    const auto emit = leave + std::log1p(-rates.deletion);
    std::vector<double> row(center.size() + 1, zero), next(row);
    row[0] = 0;
    for (std::size_t j = 0; j <= source.size(); ++j) {
        std::fill(next.begin(), next.end(), zero);
        for (std::size_t n = 0; n <= center.size(); ++n) {
            if (n < center.size())
                row[n + 1] = add(row[n + 1], row[n] + insertion);
            if (j < source.size()) {
                next[n] = add(next[n], row[n] + deletion);
                if (n < center.size()) {
                    const auto substitution = source[j] == center[n]
                                                  ? std::log1p(-rates.substitution)
                                                  : std::log(rates.substitution / 3);
                    next[n + 1] = add(next[n + 1], row[n] + emit + substitution);
                }
            }
        }
        if (j == source.size())
            return row.back() + leave;
        row.swap(next);
    }
    throw std::logic_error("mutation DP did not terminate");
}
double log_length_normalizer(std::size_t source_length, const ModelPolicy &policy) {
    validate(policy);
    context_study::require(source_length <= 4096, "context source exceeds declared DNA bound");
    const auto insertion = std::log(policy.rates.insertion);
    const auto leave = std::log1p(-policy.rates.insertion);
    const auto deletion = leave + std::log(policy.rates.deletion);
    const auto emission = leave + std::log1p(-policy.rates.deletion);
    std::vector<double> row(policy.maximum_center + 1, zero), next(row);
    row[0] = 0;
    for (std::size_t j = 0; j <= source_length; ++j) {
        std::fill(next.begin(), next.end(), zero);
        for (std::size_t n = 0; n <= policy.maximum_center; ++n) {
            if (n < policy.maximum_center)
                row[n + 1] = add(row[n + 1], row[n] + insertion);
            if (j < source_length) {
                next[n] = add(next[n], row[n] + deletion);
                if (n < policy.maximum_center)
                    next[n + 1] = add(next[n + 1], row[n] + emission);
            }
        }
        if (j == source_length) {
            double total = zero;
            for (const auto value : row)
                total = add(total, value + leave);
            context_study::require(std::isfinite(total) && total <= 1e-12,
                                   "invalid capped-length normalizer");
            return total;
        }
        row.swap(next);
    }
    throw std::logic_error("length DP did not terminate");
}
ContextLogMass context_mass(std::string_view center, const ContextDistribution &context,
                            const ModelPolicy &policy) {
    Kernel kernel(policy);
    return kernel.mass(center, context);
}
std::string context_digest(const ContextInput &input) {
    std::string bytes = "context-model-context/1\n" + input.reason + '\n' + input.donor + '\n';
    if (input.distribution) {
        bytes += input.distribution->provenance() + '\n';
        for (const auto &path : input.distribution->paths())
            bytes += path.sequence + '\t' + number(path.mass) + '\n';
    }
    return context_study::sha256(bytes);
}
std::string candidate_digest(const context_study::CandidateCase &input) {
    std::string bytes = "context-model-primary-pool/1\n";
    for (const auto *candidate : pool(input))
        bytes += candidate->sequence + '\t' + number(candidate->log_mass->value) + '\n';
    return context_study::sha256(bytes);
}
Assignment assign_contexts(const context_study::Packet &packet) {
    Assignment assignments;
    auto available = [](const context_study::CandidateCase &input,
                        const std::vector<std::string> &paths) -> ContextInput {
        if (input.availability != "usable" || paths.empty())
            return {std::nullopt, "context_unavailable", "."};
        return {ContextDistribution::uniform(paths, input.ancestry), "available", input.id};
    };
    for (const auto &input : packet.cases) {
        Arms arms{{"graph", available(input, input.paths)},
                  {"reference", available(input, input.reference_paths)},
                  {"none", {std::nullopt, "disabled", "."}},
                  {"wrong", {std::nullopt, "no_eligible_donor", "."}}};
        const context_study::CandidateCase *donor = nullptr;
        std::string minimum;
        for (const auto &candidate : packet.cases) {
            const auto delta = candidate.native.size() > input.native.size()
                                   ? candidate.native.size() - input.native.size()
                                   : input.native.size() - candidate.native.size();
            if (candidate.parent == input.parent || candidate.contig == input.contig ||
                candidate.availability != "usable" || candidate.paths.empty() || delta > 8)
                continue;
            const auto hash =
                context_study::sha256("model-a-wrong-v1\n" + input.id + '\n' + candidate.id + '\n');
            if (donor == nullptr || std::tie(hash, candidate.id) < std::tie(minimum, donor->id)) {
                donor = &candidate;
                minimum = hash;
            }
        }
        if (donor != nullptr) {
            arms.at("wrong") = available(*donor, donor->paths);
            arms.at("wrong").reason = "foreign_parent_contig_donor";
        }
        context_study::require(assignments.emplace(input.id, std::move(arms)).second,
                               "duplicate case in context assignment");
    }
    return assignments;
}
std::size_t Work::total() const {
    return checked_add(context_cells, length_cells);
}
void enforce_work(const Work &work, std::size_t maximum_cells) {
    context_study::require(maximum_cells > 0 && maximum_cells <= maximum_work_cells &&
                               work.total() <= maximum_cells,
                           "priced model work exceeds declared cell cap before scoring");
}
Work price(const context_study::CandidateCase &input, const Arms &arms,
           const std::vector<ModelPolicy> &policies) {
    Work result;
    std::set<std::string> paths;
    for (const auto &[arm, context] : arms) {
        static_cast<void>(arm);
        if (context.distribution)
            for (const auto &path : context.distribution->paths())
                paths.insert(path.sequence);
    }
    std::set<std::size_t> lengths;
    for (const auto &path : paths)
        lengths.insert(path.size());
    const auto candidates = pool(input);
    for (const auto &policy : policies) {
        validate(policy);
        for (const auto *candidate : candidates) {
            context_study::require(candidate->sequence.size() <= policy.maximum_center,
                                   "eligible candidate exceeds frozen maximum center");
            for (const auto &path : paths)
                result.context_cells =
                    checked_add(result.context_cells,
                                checked_product(candidate->sequence.size() + 1, path.size() + 1));
        }
        for (const auto length : lengths)
            result.length_cells = checked_add(
                result.length_cells, checked_product(length + 1, policy.maximum_center + 1));
    }
    return result;
}
ModelScores score_model(const context_study::CandidateCase &input, const ContextInput &context,
                        const ModelPolicy &policy) {
    Kernel kernel(policy);
    return score(input, context, policy, kernel);
}
std::string score_packet(const context_study::Packet &packet, const std::filesystem::path &output,
                         std::size_t begin, std::size_t count, std::size_t maximum_cells,
                         bool price_only) {
    context_study::require(maximum_cells > 0 && maximum_cells <= maximum_work_cells &&
                               begin < packet.cases.size() && count > 0 &&
                               count <= packet.cases.size() - begin,
                           "invalid bounded model case slice or cell cap");
    const auto policies = fixed_policies();
    const auto assignments = assign_contexts(packet);
    std::ostringstream work, contexts;
    work << "case_id\tcontext_cells\tlength_cells\ttotal_cells\n";
    contexts << "case_id\tparent\tgeometry_sha256\tpool_sha256\tarm\tcontext_"
                "sha256\tdonor\tavailability\treference_equals_graph\n";
    Work total;
    for (std::size_t index = begin; index < begin + count; ++index) {
        const auto &input = packet.cases[index];
        const auto &arms = assignments.at(input.id);
        const auto cost = price(input, arms, policies);
        total.context_cells = checked_add(total.context_cells, cost.context_cells);
        total.length_cells = checked_add(total.length_cells, cost.length_cells);
        work << input.id << '\t' << cost.context_cells << '\t' << cost.length_cells << '\t'
             << cost.total() << '\n';
        const auto same = input.paths == input.reference_paths;
        for (const auto &[arm, context] : arms)
            contexts << input.id << '\t' << input.parent << '\t' << input.geometry << '\t'
                     << candidate_digest(input) << '\t' << arm << '\t' << context_digest(context)
                     << '\t' << context.donor << '\t' << context.reason << '\t' << same << '\n';
    }
    context_study::synced_write(output / "work.tsv", work.str());
    context_study::synced_write(output / "contexts.tsv", contexts.str());
    context_study::synced_write(
        output / "policies.json",
        "{\"schema\":\"context-model-fixed-policies/1\",\"maximum_center\":108,"
        "\"mutation_rates\":[0.001,0.01],\"novel_mass\":0.5,\"context_strength\":1,"
        "\"margin\":0.5,\"signal_deficit\":0.5,\"pool\":\"native_plus_escape\","
        "\"none_feature\":0,\"wrong_rule\":\"model-a-wrong-v1\","
        "\"partition\":\"development_exposed_no_independent_confirmation\"}\n");
    if (!price_only)
        enforce_work(total, maximum_cells);
    std::size_t rows{}, accepted{}, raw_changes{}, abstentions{};
    if (!price_only) {
        std::ostringstream candidates, decisions;
        candidates << std::setprecision(17);
        decisions << std::setprecision(17);
        candidates << "case_id\tparent\tgeometry_sha256\tpool_sha256\tmu\tarm\tcontext_"
                      "sha256\tcandidate_sha256\tsequence\tsignal\tlog_graph\tlog_background\tlog_"
                      "mixture\tlog_ratio\tobjective\n";
        decisions << "case_id\tparent\tgeometry_sha256\tpool_sha256\tmu\tarm\tbaseline_sha256\traw_"
                     "sha256\taccepted_sha256\tbaseline\traw\taccepted\tgate\tabstained\tbaseline_"
                     "signal\tbaseline_objective\traw_signal\traw_objective\taccepted_"
                     "signal\taccepted_objective\tneural_delta\tobjective_delta\n";
        for (std::size_t index = begin; index < begin + count; ++index) {
            const auto &input = packet.cases[index];
            const auto pool_hash = candidate_digest(input);
            std::map<std::string, std::string> sequence_hashes;
            for (const auto *candidate : pool(input))
                sequence_hashes.emplace(candidate->sequence,
                                        context_study::sha256(candidate->sequence));
            context_study::verify_replay(input, context_study::replay(input));
            for (const auto &policy : policies) {
                Kernel kernel(policy);
                for (const auto &[arm, context] : assignments.at(input.id)) {
                    const auto context_hash = context_digest(context);
                    const auto result = score(input, context, policy, kernel);
                    raw_changes +=
                        static_cast<std::size_t>(result.raw.sequence != result.baseline.sequence);
                    accepted += static_cast<std::size_t>(
                        !result.abstained && result.gate == "context_selected" &&
                        result.accepted.sequence != result.baseline.sequence);
                    abstentions += static_cast<std::size_t>(result.abstained);
                    for (const auto &value : result.candidates) {
                        ++rows;
                        candidates
                            << input.id << '\t' << input.parent << '\t' << input.geometry << '\t'
                            << pool_hash << '\t' << policy.rates.insertion << '\t' << arm << '\t'
                            << context_hash << '\t' << sequence_hashes.at(value.sequence) << '\t'
                            << value.sequence << '\t' << value.signal << '\t' << value.context.graph
                            << '\t' << value.context.background << '\t' << value.context.mixture
                            << '\t' << value.context.log_ratio << '\t' << value.objective << '\n';
                    }
                    decisions << input.id << '\t' << input.parent << '\t' << input.geometry << '\t'
                              << pool_hash << '\t' << policy.rates.insertion << '\t' << arm << '\t'
                              << sequence_hashes.at(result.baseline.sequence) << '\t'
                              << sequence_hashes.at(result.raw.sequence) << '\t'
                              << sequence_hashes.at(result.accepted.sequence) << '\t'
                              << result.baseline.sequence << '\t' << result.raw.sequence << '\t'
                              << result.accepted.sequence << '\t' << result.gate << '\t'
                              << result.abstained << '\t' << result.baseline.signal << '\t'
                              << result.baseline.objective << '\t' << result.raw.signal << '\t'
                              << result.raw.objective << '\t' << result.accepted.signal << '\t'
                              << result.accepted.objective << '\t'
                              << result.raw.signal - result.baseline.signal << '\t'
                              << result.raw.objective - result.baseline.objective << '\n';
                }
            }
        }
        context_study::synced_write(output / "candidates.tsv", candidates.str());
        context_study::synced_write(output / "decisions.tsv", decisions.str());
    }
    return "{\"schema\":\"context-model-result/1\",\"price_only\":" +
           std::string(price_only ? "true" : "false") +
           ",\"biological_qualification\":false,\"candidate_manifest\":" +
           context_study::json_string(packet.manifest) +
           ",\"packet_cases\":" + std::to_string(packet.cases.size()) +
           ",\"slice_begin\":" + std::to_string(begin) +
           ",\"slice_cases\":" + std::to_string(count) +
           ",\"context_cells\":" + std::to_string(total.context_cells) +
           ",\"length_cells\":" + std::to_string(total.length_cells) +
           ",\"total_cells\":" + std::to_string(total.total()) +
           ",\"cell_cap\":" + std::to_string(maximum_cells) +
           ",\"candidate_rows\":" + std::to_string(rows) +
           ",\"raw_changes\":" + std::to_string(raw_changes) +
           ",\"accepted_changes\":" + std::to_string(accepted) +
           ",\"abstentions\":" + std::to_string(abstentions) +
           ",\"interpretation\":\"conditional_PoE_background_contrast_not_prior_replacement\"}";
}
}
