#include "context_study/packet.h"
#include <iomanip>
#include <sstream>

namespace context_study {
std::string write_replays(const Packet &packet, const std::filesystem::path &output) {
    std::ostringstream table;
    table << std::setprecision(17)
          << "case_id\tdomain\trole\tcandidate_sha256\tlog_"
             "mass\tpotential\tobjective\tgate\tabstained\n";
    for (const auto &input : packet.cases) {
        const auto result = replay(input);
        verify_replay(input, result);
        for (const auto *role : roles) {
            const auto &choice = result.at(role);
            table << input.id << '\t' << input.domain << '\t' << role << '\t'
                  << sha256(choice.sequence) << '\t' << choice.log_mass << '\t' << choice.potential
                  << '\t' << choice.objective << '\t' << choice.gate << '\t' << choice.abstained
                  << '\n';
        }
    }
    synced_write(output / "historical.tsv", table.str());
    return "{\"schema\":\"context-study-replay/"
           "1\",\"historical_replay\":true,\"truth_available\":false,\"cases\":" +
           std::to_string(packet.cases.size()) + ",\"score_comparison_absolute_tolerance\":1e-11}";
}
}
