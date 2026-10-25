#include "context_prefix/prefix.h"
#include "prefix_sources.h"
#include <algorithm>
#include <array>
#include <bit>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <sstream>

namespace cp = context_prefix;
namespace {
std::string pins_json(const std::vector<cp::Pin>& pins) {
    std::string result = "[";
    for (std::size_t i = 0; i < pins.size(); ++i) {
        if (i)
            result += ',';
        result += cp::pin_json(pins[i]);
    }
    return result + "]";
}
void save_scores(const std::filesystem::path& path, const cp::Scores& scores,
                 const cp::Prepared& input) {
    cp::require(std::endian::native == std::endian::little && sizeof(float) == 4 &&
                    std::numeric_limits<float>::is_iec559,
                "Prefix score format requires little-endian IEEE float32");
    const auto header = "PFS1\t" + std::to_string(scores.timesteps) +
                        "\t1024\t4\t6\tcpu\tfloat32\t" + std::to_string(input.horizon) + "\t10\t" +
                        std::to_string(input.valid) + "\t" + std::to_string(input.padded) + "\n";
    const auto payload = std::as_bytes(std::span(scores.values));
    std::vector<std::byte> bytes;
    const auto prefix = std::as_bytes(std::span(header.data(), header.size()));
    bytes.reserve(prefix.size() + payload.size());
    bytes.insert(bytes.end(), prefix.begin(), prefix.end());
    bytes.insert(bytes.end(), payload.begin(), payload.end());
    cp::fresh_bytes(path, bytes);
}
struct Case {
    cp::RawPrefix raw;
    cp::Prepared baseline, poisoned, positive;
};
std::string metadata(const cp::Request& request, const Case& value) {
    std::ostringstream out;
    out << std::setprecision(17) << "{\"uuid\":" << cp::quote(request.uuid)
        << ",\"acquisition_id\":" << cp::quote(value.raw.acquisition_id)
        << ",\"flowcell\":" << cp::quote(value.raw.flowcell)
        << ",\"sample_id\":" << cp::quote(value.raw.sample_id)
        << ",\"acquisition_start_ms\":" << value.raw.acquisition_start_ms
        << ",\"read_start_sample\":" << value.raw.read_start_sample
        << ",\"total_read_samples_metadata_only\":" << value.raw.total_read_samples
        << ",\"batch\":" << value.raw.batch << ",\"row\":" << value.raw.row
        << ",\"calibration_scale\":" << value.raw.admitted.calibration_scale
        << ",\"calibration_offset\":" << value.raw.admitted.calibration_offset
        << ",\"raw_begin\":0,\"raw_end\":" << value.baseline.horizon
        << ",\"lookahead\":0,\"sample_rate\":5000,\"front_trim\":10"
           ",\"normalization\":\"fixed PA mean94 stdev24 via retained native half utility\""
           ",\"open_pore_policy\":\"disabled; metadata availability unqualified\""
           ",\"shift\":"
        << value.baseline.shift << ",\"scale\":" << value.baseline.scale
        << ",\"valid_input_samples\":" << value.baseline.valid
        << ",\"padded_input_samples\":" << value.baseline.padded
        << ",\"padding\":\"repeat from retained prefix start to stride6\""
           ",\"model_input_dtype\":\"float32 converted from native-rounded float16\""
           ",\"prefix_reader_decompressed_samples\":"
        << value.raw.physical_samples
        << ",\"physical_overread_samples\":" << value.raw.physical_samples - value.baseline.horizon
        << ",\"future_samples_poisoned\":" << value.raw.poisoned_samples
        << ",\"offline_full_record_control_samples\":" << value.raw.offline_full_record_samples
        << ",\"future_bytes_exported\":0,\"model_input_sees_only_detached_prefix\":true"
           ",\"signal_rows\":[";
    for (std::size_t i = 0; i < value.raw.rows.size(); ++i) {
        if (i)
            out << ',';
        const auto& row = value.raw.rows[i];
        out << "{\"index\":" << row.signal_index << ",\"samples\":" << row.sample_count
            << ",\"stored_bytes\":" << row.stored_bytes << '}';
    }
    return out.str() + "]}";
}
}
int main(int argc, char** argv) {
    std::optional<std::filesystem::path> output;
    std::size_t forward_calls{};
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            std::cout
                << "context-prefix qualify --output NEWDIR\n"
                   "context-prefix contracts --request FILE --request-sha256 SHA --output NEWDIR\n"
                   "context-prefix forward --request FILE --request-sha256 SHA --horizon "
                   "4096|12288 --output NEWDIR\n"
                   "contracts never loads a model; forward runs the same contracts before CPU "
                   "inference\n";
            return 0;
        }
        cp::require(argc >= 4, "Missing prefix command/output");
        const std::string phase(argv[1]);
        cp::require(phase == "qualify" || phase == "contracts" || phase == "forward",
                    "Unknown prefix command");
        std::map<std::string, std::string> options;
        for (int i = 2; i < argc; i += 2) {
            cp::require(i + 1 < argc && options.emplace(argv[i], argv[i + 1]).second,
                        "Duplicate/incomplete prefix option");
        }
        auto expected = std::set<std::string>{"--output"};
        if (phase != "qualify") {
            expected.insert("--request");
            expected.insert("--request-sha256");
        }
        if (phase == "forward")
            expected.insert("--horizon");
        std::set<std::string> keys;
        for (const auto& [key, value] : options) {
            static_cast<void>(value);
            keys.insert(key);
        }
        cp::require(keys == expected, "Unknown or missing prefix option");
        std::optional<std::size_t> selected_horizon;
        if (phase == "forward") {
            const auto& horizon = options.at("--horizon");
            cp::require(horizon == "4096" || horizon == "12288",
                        "Forward horizon is not predeclared");
            selected_horizon = horizon == "4096" ? std::size_t{4096} : std::size_t{12288};
        }
        const auto target = std::filesystem::weakly_canonical(options.at("--output"));
        const auto owned =
            std::filesystem::path(prefix_compiled::root) / "results/context-feedback";
        const auto relative = target.lexically_relative(owned);
        cp::require(!relative.empty() && relative != "." && *relative.begin() != "..",
                    "Output outside owned prefix results");
        std::filesystem::create_directories(target.parent_path());
        cp::require(std::filesystem::create_directory(target), "Prefix output already exists");
        output = target;
        std::string command = "[";
        for (int i = 0; i < argc; ++i) {
            if (i)
                command += ',';
            command += cp::quote(argv[i]);
        }
        command += ']';
        const auto binary = cp::pin("/proc/self/exe");
        const auto source = cp::compiled_source_json();
        cp::fresh(target / "attempt.json",
                  "{\"schema\":\"context-prefix-attempt/1\",\"phase\":" + cp::quote(phase) +
                      ",\"argv\":" + command + ",\"binary\":" + cp::pin_json(binary) +
                      ",\"started_utc\":" + cp::quote(cp::utc()) + ",\"source\":" + source + "}\n");
        cp::check_compiled_sources();
        cp::initialise_cpu_threads();
        std::vector<cp::Pin> files, inputs;
        std::string result;
        if (phase == "qualify") {
            result = cp::run_controls();
        } else {
            const auto request =
                cp::read_request(options.at("--request"), options.at("--request-sha256"));
            inputs = {request.request, request.pod5, request.allowlist, request.model_manifest,
                      request.native_producer};
            cp::validate_model_metadata(request.model);
            std::vector<Case> cases;
            for (const auto horizon : request.horizons) {
                if (selected_horizon && horizon != *selected_horizon)
                    continue;
                auto raw = cp::read_prefix(request, horizon, phase == "contracts");
                auto baseline = cp::prepare(raw.admitted);
                auto poisoned = cp::prepare(raw.poisoned);
                auto positive = cp::prepare(raw.positive);
                cp::require(raw.poisoned_samples > 0 && baseline.half == poisoned.half &&
                                baseline.input == poisoned.input &&
                                baseline.shift == poisoned.shift &&
                                baseline.scale == poisoned.scale && baseline.half != positive.half,
                            "Genuine CPU prefix causal/sensitivity handoff failed");
                cases.push_back({std::move(raw), std::move(baseline), std::move(poisoned),
                                 std::move(positive)});
            }
            std::unique_ptr<cp::Model> model;
            if (phase == "forward")
                model = std::make_unique<cp::Model>(request.model);
            std::ostringstream observations;
            observations << '[';
            for (std::size_t i = 0; i < cases.size(); ++i) {
                if (i)
                    observations << ',';
                const auto& value = cases[i];
                const auto stem = "horizon-" + std::to_string(value.baseline.horizon);
                cp::fresh_bytes(target / (stem + ".raw.i16"),
                                std::as_bytes(std::span(value.raw.admitted.samples)));
                cp::fresh_bytes(target / (stem + ".normalized.f16"),
                                std::as_bytes(std::span(value.baseline.half)));
                cp::fresh_bytes(target / (stem + ".input.f32"),
                                std::as_bytes(std::span(value.baseline.input)));
                cp::fresh(target / (stem + ".metadata.json"), metadata(request, value) + "\n");
                for (const auto suffix :
                     {".raw.i16", ".normalized.f16", ".input.f32", ".metadata.json"})
                    files.push_back(cp::pin(target / (stem + suffix)));
                observations << "{\"horizon\":" << value.baseline.horizon
                             << ",\"cpu_contracts_passed\":true,\"expected_T\":"
                             << value.baseline.padded / 6;
                if (model) {
                    auto base = model->forward(value.baseline);
                    ++forward_calls;
                    auto repeat = model->forward(value.baseline);
                    ++forward_calls;
                    auto poison = model->forward(value.poisoned);
                    ++forward_calls;
                    auto positive = model->forward(value.positive);
                    ++forward_calls;
                    const auto repeat_delta = cp::difference(base.values, repeat.values);
                    const auto poison_delta = cp::difference(base.values, poison.values);
                    const auto positive_delta = cp::difference(base.values, positive.values);
                    cp::require(
                        repeat_delta <= 1e-6 && poison_delta <= 1e-6 && positive_delta > 0 &&
                            base.sequence == repeat.sequence && base.sequence == poison.sequence &&
                            base.quality == repeat.quality && base.quality == poison.quality &&
                            base.moves == repeat.moves && base.moves == poison.moves,
                        "Native reset/future-tail/sensitivity control failed");
                    const std::array<const cp::Scores*, 4> values{&base, &repeat, &poison,
                                                                  &positive};
                    const std::array<const char*, 4> names{"baseline", "repeat", "future-poison",
                                                           "admitted-positive"};
                    for (std::size_t j = 0; j < values.size(); ++j) {
                        const auto path = target / (stem + "-" + names[j] + ".scores.f32");
                        save_scores(path, *values[j], value.baseline);
                        files.push_back(cp::pin(path));
                    }
                    const auto decoded =
                        "prefix-native/1\nuuid\t" + request.uuid + "\nraw_horizon\t" +
                        std::to_string(value.baseline.horizon) +
                        "\ninitial_state\tuniform_native_cpu\nSEQ\t" + base.sequence + "\nQ\t" +
                        base.quality + "\nMOVES\t" + base.moves + "\n";
                    cp::fresh(target / (stem + ".native.tsv"), decoded);
                    files.push_back(cp::pin(target / (stem + ".native.tsv")));
                    observations << std::setprecision(17) << ",\"shape\":[1," << base.timesteps
                                 << ",1024]"
                                 << ",\"device\":\"cpu\",\"score_dtype\":\"float32\",\"encoder_"
                                    "state\":\"reset each forward\""
                                    ",\"repeat_max_abs\":"
                                 << repeat_delta << ",\"future_tail_max_abs\":" << poison_delta
                                 << ",\"admitted_positive_max_abs\":" << positive_delta
                                 << ",\"sequence_bases\":" << base.sequence.size();
                }
                observations << '}';
            }
            observations << ']';
            result =
                "{\"schema\":\"context-prefix-result/1\",\"phase\":" + cp::quote(phase) +
                ",\"exploratory_development\":true,\"biological_qualification\":false,\"online_"
                "readiness\":false,"
                "\"stock_cuda_parity\":false,\"lookahead\":0,\"model_loaded\":" +
                (model ? "true" : "false") +
                ",\"model_forward_calls\":" + std::to_string(forward_calls) +
                ",\"score_tolerance_absolute\":0.000001,\"observations\":" + observations.str() +
                "}";
            for (const auto& input : inputs)
                cp::check(input);
        }
        cp::fresh(target / "result.json", result + "\n");
        const auto attempt = cp::pin(target / "attempt.json");
        const auto result_pin = cp::pin(target / "result.json");
        files.push_back(attempt);
        files.push_back(result_pin);
        cp::fresh(target / "complete.json",
                  "{\"schema\":\"context-prefix-complete/1\",\"complete\":true,\"phase\":" +
                      cp::quote(phase) + ",\"attempt\":" + cp::pin_json(attempt) +
                      ",\"result\":" + cp::pin_json(result_pin) + ",\"files\":" + pins_json(files) +
                      ",\"inputs\":" + pins_json(inputs) + ",\"finished_utc\":" +
                      cp::quote(cp::utc()) + ",\"source\":" + source + "}\n");
        std::cout << "{\"completion\":" << cp::pin_json(cp::pin(target / "complete.json")) << "}\n";
        return 0;
    } catch (const std::exception& error) {
        if (output) {
            try {
                cp::fresh(*output / "failure.json",
                          "{\"complete\":false,\"error\":" + cp::quote(error.what()) +
                              ",\"finished_utc\":" + cp::quote(cp::utc()) +
                              ",\"model_forward_calls\":" + std::to_string(forward_calls) + "}\n");
            } catch (const std::exception& projection) {
                std::cerr << "Failure receipt projection: " << projection.what() << '\n';
            }
        }
        std::cerr << "context-prefix: " << error.what() << '\n';
        return 2;
    }
}
