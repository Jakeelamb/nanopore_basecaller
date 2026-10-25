#pragma once
#include "context_study/packet.h"
#include <map>
#include <string>
#include <vector>

namespace context_model {
std::map<std::string, std::string> parse_options(const std::string &,
                                                 const std::vector<std::string> &);
void verify_sources();
std::string source_json();
context_study::Invocation begin(int, char **);
void finish(const context_study::Invocation &, const std::string &,
            const std::vector<std::string> &);
}
