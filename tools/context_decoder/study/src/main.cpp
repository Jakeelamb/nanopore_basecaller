#include "context_study/oracle.h"
#include <iostream>

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            std::cout
                << "context-atlas qualify --output NEWDIR\ncontext-atlas evaluate --cases FILE "
                   "--cases-sha256 SHA --truth FILE --truth-sha256 SHA --output NEWDIR\n";
            return 0;
        }
        const auto invocation = context_study::begin_invocation(argc, argv, false);
        if (invocation.command == "qualify") {
            context_study::finish_invocation(invocation, context_study::run_controls(), {});
        } else {
            const auto cases = context_study::read_candidates(
                invocation.options.at("--cases"), invocation.options.at("--cases-sha256"));
            const auto truth = context_study::read_truth(
                invocation.options.at("--truth"), invocation.options.at("--truth-sha256"), cases);
            static_cast<void>(context_study::write_replays(cases, invocation.output));
            const auto result = context_study::evaluate_packet(cases, truth, invocation.output);
            context_study::finish_invocation(invocation, result,
                                             {"historical.tsv", "candidates.tsv", "private.tsv",
                                              "support.tsv", "decisions.tsv"});
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
