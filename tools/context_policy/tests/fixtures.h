#pragma once

#include "context_policy/protocol.h"

namespace context_policy::test {
inline void reseal(Json& request) {
    const auto bytes = request.at("batch").dump();
    request["batch_pin"] = {{"path", "/frozen/candidate-batch.json"}, {"size", bytes.size()},
                             {"sha256", digest(bytes)}};
    request["expected_batch_sha256"] = digest(bytes);
}
inline Json run(Json request) {
    const auto bytes = request.at("batch").dump();
    request.erase("batch");
    return decide_request(request, bytes);
}
inline Json fixture() {
    const std::string hash(64, 'a');
    const Json binding{{"source_sha256", hash}, {"plan_sha256", hash},
                       {"input_tensor", {{"path", "/frozen/fixture.tensor"}, {"size", 8}, {"sha256", hash}}},
                       {"read_id", "synthetic-read"}, {"parent_index", 0}, {"chunk_index", 0},
                       {"block_index", 0},
                       {"availability", {{"kind", "released-score-block"}, {"row_begin", 0},
                                         {"row_end", 8}, {"available_row_end", 8},
                                         {"chunk_lookahead", "whole_chunk"}, {"signal_geometry", nullptr}}},
                       {"previous_state_sha256", hash}, {"prefix_sha256", hash}, {"prefix_length", 4},
                       {"orientation", "forward"},
                       {"location_producer", {{"path", "/frozen/location.json"}, {"size", 8}, {"sha256", hash}}},
                       {"reference_free_producer", {{"path", "/frozen/free.json"}, {"size", 8}, {"sha256", hash}}},
                       {"identity_input", {{"path", "/frozen/identity.json"}, {"size", 8}, {"sha256", hash}}}};
    Json batch{{"schema", "feedback-next/1"}, {"kind", "candidate-batch"}, {"binding", binding},
               {"native", {{"sequence", "AAAA"}, {"quality", "IIII"}, {"scope", "available_input_segment"}}},
               {"reference_free_candidate_id", "free"}, {"union_nn_candidate_id", "free"},
               {"locations", Json::array({{{"id", "L0"}, {"contig", "chr1"}, {"strand", "+"},
                   {"query_begin", 0}, {"query_end", 4}, {"reference_begin", 100}, {"reference_end", 104},
                   {"confidence", {{"feature", "declared-location-support"}, {"value", 1.0},
                                   {"meaning", "bounded_support_not_probability"}}}}})},
               {"candidates", Json::array({
                   {{"id", "native"}, {"sequence", "AAAA"}, {"neural_log_likelihood", -2.0},
                    {"context_cost", 4.0}, {"location_ids", {"L0"}}, {"edits", Json::array()},
                    {"eligibility_reasons", Json::array()}},
                   {{"id", "free"}, {"sequence", "AAAC"}, {"neural_log_likelihood", 0.0},
                    {"context_cost", 4.0}, {"location_ids", {"L0"}},
                    {"edits", Json::array({{{"operation", "SNV"}, {"query_position", 3},
                                           {"reference", "A"}, {"alternate", "C"}}})},
                    {"eligibility_reasons", Json::array()}},
                   {{"id", "ref"}, {"sequence", "AAAT"}, {"neural_log_likelihood", -0.25},
                    {"context_cost", 0.0}, {"location_ids", {"L0"}},
                    {"edits", Json::array({{{"operation", "SNV"}, {"query_position", 3},
                                           {"reference", "A"}, {"alternate", "T"}}})},
                    {"eligibility_reasons", Json::array()}}})}};
    Json request{{"schema", "feedback-next/1"}, {"batch", batch}, {"expected_binding", binding},
            {"policy", {{"mode", "adaptive"}, {"maximum_context_weight", 0.5},
                        {"maximum_neural_deficit", 0.5}, {"minimum_objective_margin", 0.0},
                        {"parameter_status", "predeclared_unfitted"}, {"quality_status", "uncalibrated"}}}};
    reseal(request);
    return request;
}
}
