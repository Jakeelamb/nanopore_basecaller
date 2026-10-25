#include "context_study/packet.h"
#include <iostream>

int main(int argc, char **argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            std::cout << "context-infer replay --cases FILE --cases-sha256 SHA --output NEWDIR\n";
            return 0;
        }
        const auto invocation = context_study::begin_invocation(argc, argv, true);
        const auto cases = context_study::read_candidates(invocation.options.at("--cases"),
                                                          invocation.options.at("--cases-sha256"));
        context_study::finish_invocation(
            invocation, context_study::write_replays(cases, invocation.output), {"historical.tsv"});
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
