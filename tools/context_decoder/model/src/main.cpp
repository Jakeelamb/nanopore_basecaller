#include "context_model/model.h"
#include "context_model/runtime.h"
#include <iostream>

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            std::cout
                << "context-model qualify --output NEWDIR\n"
                   "context-model price|replay --cases FILE --cases-sha256 SHA --output NEWDIR "
                   "[--begin INDEX --count COUNT --max-cells CELLS]\n";
            return 0;
        }
        const auto invocation = context_model::begin(argc, argv);
        if (invocation.command == "qualify") {
            context_model::finish(invocation, context_model::qualify(), {});
            return 0;
        }
        const auto packet = context_study::read_candidates(invocation.options.at("--cases"),
                                                           invocation.options.at("--cases-sha256"));
        const auto begin = invocation.options.contains("--begin")
                               ? context_study::natural(invocation.options.at("--begin"))
                               : 0;
        context_study::require(begin < packet.cases.size(), "model slice begins beyond packet");
        const auto count = invocation.options.contains("--count")
                               ? context_study::natural(invocation.options.at("--count"))
                               : packet.cases.size() - begin;
        const auto cap = invocation.options.contains("--max-cells")
                             ? context_study::natural(invocation.options.at("--max-cells"))
                             : context_model::maximum_work_cells;
        const bool price = invocation.command == "price";
        const auto result =
            context_model::score_packet(packet, invocation.output, begin, count, cap, price);
        std::vector<std::string> files{"work.tsv", "contexts.tsv", "policies.json"};
        if (!price) {
            files.push_back("candidates.tsv");
            files.push_back("decisions.tsv");
        }
        context_model::finish(invocation, result, files);
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
