#include "archive_consumer/core.h"

#include <algorithm>

namespace archive_consumer {
std::pair<std::string, std::string> apply_edits(const std::string& original,
                                                const std::string& quality,
                                                std::vector<Edit> changes) {
    require(original.size() == quality.size(), "Actual native SEQ/Q length differs");
    std::sort(changes.begin(), changes.end(),
              [](const auto& a, const auto& b) { return a.a < b.a; });
    std::string sequence, qualities;
    std::size_t cursor{};
    for (const auto& change : changes) {
        require(cursor <= change.a && change.a <= change.b && change.b <= original.size(),
                "Owned edits overlap or exceed native parent");
        dna(change.replacement);
        sequence += original.substr(cursor, change.a - cursor) + change.replacement;
        qualities += quality.substr(cursor, change.a - cursor) +
                     std::string(change.replacement.size(), '!');
        cursor = change.b;
    }
    sequence += original.substr(cursor);
    qualities += quality.substr(cursor);
    auto reverse_sequence = original, reverse_quality = quality;
    for (auto it = changes.rbegin(); it != changes.rend(); ++it) {
        reverse_sequence.replace(it->a, it->b - it->a, it->replacement);
        reverse_quality.replace(it->a, it->b - it->a, std::string(it->replacement.size(), '!'));
    }
    require(sequence == reverse_sequence && qualities == reverse_quality,
            "Independent complete SEQ/Q edit reconstruction differs");
    return {sequence, qualities};
}
}
