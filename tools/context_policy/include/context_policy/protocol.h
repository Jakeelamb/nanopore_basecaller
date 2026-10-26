#pragma once

#include "context_policy/policy.h"
#include "json.hpp"

#include <cstdint>
#include <string>

namespace context_policy {
using Json = nlohmann::json;
Json parse(const std::string &bytes);
std::string digest(const std::string &bytes);
Json decide_request(const Json &request, const std::string &batch_bytes);
void verify_compiled_sources();
void verify_source_file(const std::string &path, std::uintmax_t size, const std::string &sha256);
}
