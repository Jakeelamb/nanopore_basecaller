#include "context_decision/decision.h"
#include "context_decision/runtime.h"
#include <iostream>

int main(int argc, char **argv) {
    try {
        const auto invocation = context_decision::begin(argc, argv);
        if (invocation.command == "qualify") {
            const auto count = context_decision::controls();
            context_decision::finish(invocation,
                                     "{\"schema\":\"context-decision-controls/1\",\"controls\":" +
                                         std::to_string(count) + ",\"passed\":true}",
                                     {});
            return 0;
        }
        const auto packet = context_study::read_candidates(invocation.options.at("--cases"),
                                                           invocation.options.at("--cases-sha256"));
        const auto scope =
            invocation.options.contains("--scope") ? invocation.options.at("--scope") : "all";
        const auto selected = context_decision::indices(packet, scope);
        context_study::require(!selected.empty(), "empty decision scope");
        const auto cap = invocation.options.contains("--max-cells")
                             ? context_study::natural(invocation.options.at("--max-cells"))
                             : context_decision::maximum_work_cells;
        std::uint64_t cells = 0;
        for (const auto index : selected) {
            const auto work = context_decision::price(packet.cases[index]);
            context_study::require(work <= cap - cells, "decision slice exceeds work cap");
            cells += work;
        }
        std::uint64_t whole = 0;
        for (const auto &item : packet.cases) {
            const auto work = context_decision::price(item);
            context_study::require(work <= cap - whole, "whole-packet work exceeds cap");
            whole += work;
        }
        context_study::require(whole <= cap / 8 && cells <= (cap - 8 * whole) / 24,
                               "conservative replay and decision work exceeds cap");
        const auto bound = 8 * whole + 24 * cells;
        if (invocation.command == "price") {
            context_decision::finish(invocation,
                                     "{\"schema\":\"context-decision-price/1\",\"cases\":" +
                                         std::to_string(selected.size()) +
                                         ",\"scope\":" + context_study::json_string(scope) +
                                         ",\"union_distance_cells\":" + std::to_string(cells) +
                                         ",\"distance_cells_upper_bound\":" +
                                         std::to_string(bound) + ",\"new_neural_calls\":0}",
                                     {});
        } else {
            context_decision::finish(invocation,
                                     context_decision::evaluate(packet, scope, invocation.output),
                                     {"historical.tsv", "decisions.tsv"});
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
