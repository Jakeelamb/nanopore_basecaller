#pragma once
#include "context_sample_feedback/sample.h"
namespace context_sample_feedback {
context_study::Invocation begin(int, char **);
void finish(const context_study::Invocation &, const std::string &,
            const std::vector<std::string> &);
void verify_sources();
std::string source_json();
}
