#pragma once

#include "context_decoder/guarded.h"
#include "context_decoder/io.h"

namespace context_decoder {

struct GuardedBoundFrame {
    GuardedWindow window;
    BoundFrame base;
    Fields binding;
    std::size_t scalar_comparisons{};
};

GuardedBoundFrame load_guarded_frame(const std::filesystem::path& manifest,
                                     const std::string& expected_hash);

}
