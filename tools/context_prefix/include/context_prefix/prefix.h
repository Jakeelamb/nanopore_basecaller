#pragma once
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <span>
#include <string>
#include <vector>

namespace context_prefix {
struct Pin {
    std::filesystem::path path;
    std::uintmax_t size{};
    std::string sha256;
};
struct Request {
    Pin request, pod5, allowlist, model_manifest, native_producer;
    std::filesystem::path model;
    std::string uuid, acquisition_id;
    std::vector<std::size_t> horizons;
};
struct DetachedPrefix {
    std::vector<std::int16_t> samples;
    std::size_t horizon{};
    float calibration_scale{}, calibration_offset{};
};
struct RowReceipt {
    std::uint64_t signal_index{};
    std::size_t sample_count{}, stored_bytes{};
};
struct RawPrefix {
    DetachedPrefix admitted, poisoned, positive;
    std::vector<RowReceipt> rows;
    std::uint64_t read_start_sample{}, total_read_samples{};
    std::int64_t acquisition_start_ms{};
    std::size_t physical_samples{}, poisoned_samples{}, batch{}, row{};
    std::size_t offline_full_record_samples{};
    std::string acquisition_id, flowcell, sample_id;
};
struct Prepared {
    std::vector<std::uint16_t> half;
    std::vector<float> input;
    std::size_t horizon{}, valid{}, padded{};
    float shift{}, scale{};
};
struct Scores {
    std::vector<float> values;
    std::size_t timesteps{}, channels{};
    std::string sequence, quality, moves;
};
void require(bool condition, const std::string& message);
std::string quote(const std::string& value);
std::string utc();
std::string bytes_sha(std::span<const std::byte> bytes);
Pin pin(const std::filesystem::path& path);
void check(const Pin& value);
std::string pin_json(const Pin& value);
void fresh(const std::filesystem::path& path, const std::string& text);
void fresh_bytes(const std::filesystem::path& path, std::span<const std::byte> bytes);
std::string compiled_source_json();
void check_compiled_sources();
Request read_request(const std::filesystem::path& path, const std::string& sha);
void initialise_cpu_threads();
void validate_model_metadata(const std::filesystem::path& path);
DetachedPrefix detach(std::span<const std::int16_t> source, std::size_t horizon,
                      float calibration_scale, float calibration_offset);
void validate_acquisition(const Request& request, const std::string& uuid,
                          const std::string& acquisition, const std::string& flowcell,
                          std::uint16_t sample_rate);
RawPrefix read_prefix(const Request& request, std::size_t horizon,
                      bool offline_full_record_control);
Prepared prepare(const DetachedPrefix& prefix);
double difference(std::span<const float> a, std::span<const float> b);
std::string run_controls();
class Model {
  public:
    explicit Model(const std::filesystem::path& path);
    ~Model();
    Model(const Model&) = delete;
    Model& operator=(const Model&) = delete;
    Scores forward(const Prepared& input);

  private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
}
