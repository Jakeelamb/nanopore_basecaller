#include "context_uncertainty/uncertainty.h"
#include <iostream>

int main(int argc, char **argv) {
    namespace u = context_uncertainty;
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            std::cout << "context-uncertainty qualify --output NEWDIR\n"
                         "context-uncertainty scan --manifest FILE --manifest-sha256 SHA --begin "
                         "INDEX --count N --output NEWDIR\n"
                         "context-uncertainty merge --manifest FILE --manifest-sha256 SHA --parts "
                         "FILE --parts-sha256 SHA --output NEWDIR\n";
            return 0;
        }
        const auto invocation = u::begin(argc, argv);
        if (invocation.command == "qualify") {
            u::finish(invocation, u::controls(), {}, {});
            return 0;
        }
        const auto input = u::read_inputs(invocation.options.at("--manifest"),
                                          invocation.options.at("--manifest-sha256"));
        auto consumed = input.sources;
        consumed.push_back(input.manifest);
        if (invocation.command == "scan") {
            const auto first = u::natural(invocation.options.at("--begin")),
                       count = u::natural(invocation.options.at("--count"));
            const auto result = u::scan(input, first, count, invocation.output);
            for (std::size_t i = first; i < first + count; ++i)
                consumed.push_back(input.chunks[i].scores);
            u::finish(invocation, result, {"chunks.tsv", "proposals.tsv"}, consumed);
        } else {
            const auto parts = u::pin(invocation.options.at("--parts"));
            u::require(parts.sha256 == invocation.options.at("--parts-sha256"),
                       "Parts hash differs");
            const auto result = u::merge(input, parts, invocation.output, consumed);
            consumed.push_back(parts);
            u::finish(invocation, result, {"nominations.tsv"}, consumed);
        }
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
