#pragma once

#include "context_decoder/guarded.h"

#include <filesystem>
#include <string>
#include <vector>

namespace prefix_feedback {

struct Window {
    context_decoder::GuardedWindow guarded;
    std::size_t horizon{};
    std::size_t row_begin{};
    std::size_t row_end{};
    std::size_t core_begin{};
    std::size_t core_end{};
    std::string parent;
    std::string qname;
    std::string native_prefix;
};

struct Session {
    std::size_t horizon{};
    std::string revision;
    std::string committed_prefix;
    bool encoder_reset{};
    void admit(std::size_t next_horizon, bool reset_encoder);
    void revise(const std::string& sequence, std::size_t irreversible_bases);
};

void require(bool condition, const char* message);
void preserve_committed(const std::string& committed, const std::string& revision);
std::vector<double> read_pfs(const std::filesystem::path& path, std::size_t horizon);
Window load_window(const std::filesystem::path& packet, const std::string& expected_sha256);
Session load_session(const std::filesystem::path& path,
                     const std::string& expected_sha256,
                     const Window& window);
std::string decode(const Window& window, Session& session);
std::string source_json();
std::string controls();

}
