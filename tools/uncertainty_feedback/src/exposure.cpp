#include "uncertainty_feedback/core.h"

#include <algorithm>
#include <fstream>
#include <sstream>

namespace uncertainty_feedback {
namespace {
using Spans = std::vector<std::pair<std::size_t, std::size_t>>;
using Regions = std::map<std::string, Spans>;
void merge(Spans& values) {
    std::sort(values.begin(), values.end());
    Spans result;
    for (const auto& span : values) {
        require(span.first < span.second, "Empty/reversed genomic interval");
        if (!result.empty() && span.first <= result.back().second) {
            result.back().second = std::max(result.back().second, span.second);
        } else {
            result.push_back(span);
        }
    }
    values = std::move(result);
}
Regions bed(const fs::path& path) {
    std::ifstream input(path);
    require(input.good(), "Cannot read frozen BED");
    Regions result;
    std::string line;
    while (std::getline(input, line)) {
        const auto row = split(line);
        require(row.size() >= 3, "Malformed BED row");
        result[row[0]].emplace_back(natural(row[1]), natural(row[2]));
    }
    require(input.eof(), "Frozen BED read failed");
    for (auto& [contig, spans] : result) {
        static_cast<void>(contig);
        merge(spans);
    }
    return result;
}
Spans intersection(const Spans& a, const Spans& b) {
    Spans result;
    std::size_t i{}, j{};
    while (i < a.size() && j < b.size()) {
        const auto start = std::max(a[i].first, b[j].first),
                   end = std::min(a[i].second, b[j].second);
        if (start < end) {
            result.emplace_back(start, end);
        }
        if (a[i].second < b[j].second) {
            ++i;
        } else {
            ++j;
        }
    }
    return result;
}
std::string serialize(const Regions& regions) {
    std::string result;
    for (const auto& [contig, spans] : regions) {
        for (const auto& [a, b] : spans) {
            result += contig + '\t' + std::to_string(a) + '\t' + std::to_string(b) + '\n';
        }
    }
    return result;
}
std::size_t bases(const Regions& regions) {
    std::size_t result{};
    for (const auto& [contig, spans] : regions) {
        static_cast<void>(contig);
        for (const auto& [a, b] : spans) {
            result += b - a;
        }
    }
    return result;
}
}
void exposure(const Json& request, const fs::path& output) {
    require(request.at("schema") == "uncertainty-feedback-exposure-request/1",
            "Exposure request schema differs");
    check(request.at("plan"));
    const auto planned = read(request.at("plan").at("path").get<std::string>());
    validate_plan(planned);
    const auto masks = frozen_masks(request.at("masks"));
    check(planned.at("joins"));
    const auto joins = read(planned.at("joins").at("path").get<std::string>());
    Regions targets;
    std::string per_parent;
    for (const auto& target : joins) {
        const auto& w = target.at("window");
        const auto contig = w.at("contig").get<std::string>();
        const auto a = integer(w.at("core_start")), b = integer(w.at("core_end"));
        targets[contig].emplace_back(a, b);
        per_parent += contig + '\t' + std::to_string(a) + '\t' + std::to_string(b) + '\t' +
                      w.at("read_id").get<std::string>() + '\t' +
                      std::to_string(integer(w.at("query_index"))) + '\n';
    }
    for (auto& [contig, spans] : targets) {
        static_cast<void>(contig);
        merge(spans);
    }
    fresh(output / "nominated-union.bed", serialize(targets));
    fresh(output / "nominated-by-parent.bed", per_parent);
    Json domains = Json::object();
    for (const auto& [name, item] : masks.items()) {
        require(name == "100" || name == "500", "Only frozen mask100/500 accepted");
        check(item);
        const auto frozen = bed(item.at("path").get<std::string>());
        Regions matched;
        for (const auto& [contig, spans] : targets) {
            if (frozen.contains(contig)) {
                matched[contig] = intersection(spans, frozen.at(contig));
            }
        }
        const auto path = output / ("union-mask-" + name + ".bed");
        fresh(path, serialize(matched));
        domains[name] = {
                {"mask", item}, {"intersected_union", pin(path)}, {"union_bases", bases(matched)}};
    }
    complete(output, "uncertainty-feedback-exposure-geometry/1",
             {{"plan", request.at("plan")},
              {"plan_sha256", planned.at("plan_sha256")},
              {"nominated_union", pin(output / "nominated-union.bed")},
              {"nominated_by_parent", pin(output / "nominated-by-parent.bed")},
              {"union_bases", bases(targets)},
              {"domains", domains},
              {"truth_input", true},
              {"interpretation",
               "Locus-union error exposure only; all native parents at selected loci. Not "
               "attainable gain or calibration. Per-parent target geometry retained separately."},
              {"insertion_policy",
               "Unchanged native pairer requires both flanks in one intersected interval"},
              {"target_selection_frozen_before_masks", true}});
}
}
