#pragma once

#include "context_decoder/decoder.h"

#include <filesystem>
#include <map>
#include <string>

namespace context_decoder {
using Fields = std::map<std::string, std::string>;
struct BoundFrame {
    Frame scores;
    RetrievedContext context;
    std::string native;
    Fields binding;
    std::filesystem::path scalar_controls;
};
std::string sha256(const std::filesystem::path& path);
Fields fields(const std::filesystem::path& path, const std::string& schema);
BoundFrame load_frame(const std::filesystem::path& manifest, const std::string& expected_hash);
std::size_t check_retained_scalar(const BoundFrame& frame);
std::string quote(const std::string& text);
void fresh(const std::filesystem::path& path, const std::string& text);
}
