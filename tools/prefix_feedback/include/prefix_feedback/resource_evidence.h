#pragma once
#include "prefix_feedback/session.h"

namespace prefix_feedback {
namespace resource_evidence {
// The production boundary supplies the frozen F4 trust tuple. Tiny controls
// supply literal fixture pins to exercise the same parser without real inputs.
struct Trust {
    std::string root;
    Json verifier;
    Json supervisor;
    Json spec;
    Json required_sources;
};
Trust frozen_trust();
void validate(const Json& resources, const Json& evidence, const Trust& trust);
}
std::size_t resource_controls();
}
