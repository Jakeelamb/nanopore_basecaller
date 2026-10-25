#include "context_decoder/io.h"
#include "prefix_feedback/feedback.h"

#include <unistd.h>

#include <filesystem>
#include <fstream>
#include <functional>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace prefix_feedback {
namespace {
void rejects(const std::function<void()>& run) {
    bool rejected{};
    try {
        run();
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    require(rejected, "negative control unexpectedly accepted");
}
}
std::string controls() {
    Session session;
    rejects([&] { session.admit(12288, true); });
    rejects([&] { session.admit(4096, false); });
    session.admit(4096, true);
    session.revise("ACGT", 0);
    rejects([&] { session.admit(4096, true); });
    rejects([&] { session.revise("ACGA", 1); });
    session.admit(12288, true);
    session.revise("TTTT", 0);
    rejects([&] { session.admit(4096, true); });
    rejects([&] { preserve_committed("ACG", "ACTT"); });
    preserve_committed("ACG", "ACGT");
    Session committed;
    committed.admit(4096, true);
    committed.committed_prefix = "ACG";
    rejects([&] { committed.revise("ACTT", 0); });
    committed.revise("ACGT", 0);
    const auto directory = std::filesystem::temp_directory_path() /
                           ("prefix-feedback-controls-" + std::to_string(getpid()));
    require(std::filesystem::create_directory(directory), "fresh test directory required");
    try {
        const auto binding = directory / "prior-binding.json";
        {
            std::ofstream out(binding);
            out << "{}\n";
        }
        const auto session_path = directory / "session.tsv";
        const auto session_fixture = [&](const std::string& parent, std::size_t horizon) {
            std::ofstream out(session_path);
            out << "prefix-feedback-session-input/1\nparent\t" << parent
                << "\nprevious_horizon\t0\nprevious_revision\t\ncommitted_prefix\t\ncurrent_"
                   "horizon\t"
                << horizon << "\nencoder_reset\t1\npolicy\tbounded_reset_zero_commits\n";
            for (const std::string key : {"prior_complete", "prior_result"}) {
                out << key << "_path\tnone\n"
                    << key << "_size\t0\n"
                    << key << "_sha256\t" << std::string(64, '0') << '\n';
            }
            out << "prior_binding_path\t" << binding.string() << "\nprior_binding_size\t"
                << std::filesystem::file_size(binding) << "\nprior_binding_sha256\t"
                << context_decoder::sha256(binding) << '\n';
        };
        Window window;
        window.parent = "7214d805-8331-49aa-af61-478be074d7a6";
        window.horizon = 4096;
        session_fixture(window.parent, 4096);
        const auto actual =
                load_session(session_path, context_decoder::sha256(session_path), window);
        require(actual.horizon == 4096 && actual.encoder_reset && actual.revision.empty(),
                "actual session input restore/admit differs");
        session_fixture(window.parent, 12288);
        rejects([&] {
            static_cast<void>(
                    load_session(session_path, context_decoder::sha256(session_path), window));
        });
        session_fixture("00000000-0000-0000-0000-000000000000", 4096);
        rejects([&] {
            static_cast<void>(
                    load_session(session_path, context_decoder::sha256(session_path), window));
        });
        const auto path = directory / "bad.pfs";
        {
            std::ofstream out(path);
            out << "DGS1\t681\t1024\t4\t6\tcpu\tfloat32\t4096\t10\t4086\t4086\n";
        }
        rejects([&] { static_cast<void>(read_pfs(path, 4096)); });
        const auto fixture = [&](float first, bool extra) {
            std::ofstream out(path, std::ios::binary);
            out << "PFS1\t681\t1024\t4\t6\tcpu\tfloat32\t4096\t10\t4086\t4086\n";
            std::vector<float> values(681 * 1024, 0.0F);
            values[0] = first;
            values.back() = -5.0F;
            out.write(reinterpret_cast<const char*>(values.data()),
                      static_cast<std::streamsize>(values.size() * sizeof(float)));
            if (extra) {
                out << 'x';
            }
        };
        fixture(5.0F, false);
        const auto payload = read_pfs(path, 4096);
        require(payload.size() == 681 * 1024 && payload.front() == 5.0 && payload.back() == -5.0,
                "PFS1 finite positive fixture differs");
        fixture(std::numeric_limits<float>::quiet_NaN(), false);
        rejects([&] { static_cast<void>(read_pfs(path, 4096)); });
        fixture(6.0F, false);
        rejects([&] { static_cast<void>(read_pfs(path, 4096)); });
        fixture(0.0F, true);
        rejects([&] { static_cast<void>(read_pfs(path, 4096)); });
        rejects([&] { static_cast<void>(read_pfs(path, 12288)); });
        {
            std::ofstream out(path);
            out << "PFS1\t681\t1024\t4\t6\tcpu\tfloat32\t4096\t10\t4086\t4086\n";
        }
        rejects([&] { static_cast<void>(read_pfs(path, 4096)); });
        std::filesystem::remove_all(directory);
    } catch (...) {
        std::filesystem::remove_all(directory);
        throw;
    }
    return "{\"reset_monotonic_commit_controls\":true,\"actual_session_input_controls\":true,\"pfs_"
           "format_rejections\":true,\"guarded\":" +
           context_decoder::run_guarded_controls() + "}";
}
}
