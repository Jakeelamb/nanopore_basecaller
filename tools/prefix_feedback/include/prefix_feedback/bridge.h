#pragma once
#include "prefix_feedback/session.h"

namespace prefix_feedback {
struct PanelCost {
    double value{};
    Json coverage = Json::array();
};
PanelCost panel_cost(const Session& session, const std::string& sequence);
Json wire_edits(const std::string& identity, const std::string& sequence);
Json scoring_descriptor(const Session& session, const Json& binding);
Json normalize_candidates(const Session& session, const Json& snapshot,
                          const Json& identity, const Json& binding, Json& coverage);
Json merge_candidates(const Session& session, const Json& original, const Json& proposals,
                      const Json& descriptor, Json& report);
void bridge_command(const std::string& command, const Json& request, const fs::path& output);
int bridge_controls();
}
