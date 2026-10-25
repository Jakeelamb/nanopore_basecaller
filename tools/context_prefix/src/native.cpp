#include "basecall/crf_utils.h"
#include "config/BasecallModelConfig.h"
#include "context_prefix/prefix.h"
#include "decode/Decoder.h"
#include "torch_utils/tensor_utils.h"
#include <ATen/ATen.h>
#include <ATen/Parallel.h>
#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <cmath>
#include <cstring>
#include <limits>
#include <numeric>
#include <pod5_format/c_api.h>

namespace context_prefix {
namespace {
void pod5_ok(pod5_error_t status) {
    if (status != POD5_OK) {
        const auto* error = pod5_get_error_string();
        require(false, std::string("POD5: ") + (error ? error : "unknown error"));
    }
}
struct Pod5Session {
    Pod5Session() { pod5_ok(pod5_init()); }
    ~Pod5Session() { static_cast<void>(pod5_terminate()); }
};
struct RowInfo {
    SignalRowInfo_t* value{};
    ~RowInfo() {
        if (value)
            static_cast<void>(pod5_free_signal_row_info(1, &value));
    }
};
std::array<std::uint8_t, 16> uuid_bytes(const std::string& uuid) {
    require(uuid.size() == 36, "Malformed UUID length");
    std::array<std::uint8_t, 16> result{};
    std::size_t index{};
    for (std::size_t i = 0; i < uuid.size();) {
        if (i == 8 || i == 13 || i == 18 || i == 23) {
            require(uuid[i] == '-', "Malformed UUID separator");
            ++i;
            continue;
        }
        unsigned value{};
        const auto [end, error] = std::from_chars(uuid.data() + i, uuid.data() + i + 2, value, 16);
        require(error == std::errc{} && end == uuid.data() + i + 2 && value <= 255 &&
                    index < result.size(),
                "Malformed UUID hex");
        result[index++] = static_cast<std::uint8_t>(value);
        i += 2;
    }
    require(index == result.size(), "Malformed UUID byte count");
    return result;
}
void validate_config(const dorado::config::BasecallModelConfig& config) {
    const auto& norm = config.signal_norm_params;
    require(config.is_flstm_model() && config.state_len == 4 && config.stride == 6 &&
                config.num_features == 1 && config.outsize == 1024 && config.sample_rate == 5000 &&
                norm.strategy == dorado::config::ScalingStrategy::PA &&
                norm.standardisation.standardise && norm.standardisation.mean == 94.0F &&
                norm.standardisation.stdev == 24.0F,
            "Pinned HAC v6 model geometry/normalization differs");
}
}
void initialise_cpu_threads() {
    at::set_num_threads(2);
    at::set_num_interop_threads(1);
}
void validate_model_metadata(const std::filesystem::path& path) {
    validate_config(dorado::config::load_model_config(path));
}
RawPrefix read_prefix(const Request& request, std::size_t horizon,
                      bool offline_full_record_control) {
    Pod5Session session;
    using Reader = std::unique_ptr<Pod5FileReader_t, decltype(&pod5_close_and_free_reader)>;
    using Batch = std::unique_ptr<Pod5ReadRecordBatch_t, decltype(&pod5_free_read_batch)>;
    using Run = std::unique_ptr<RunInfoDictData_t, decltype(&pod5_free_run_info)>;
    Reader reader(pod5_open_file(request.pod5.path.c_str()), pod5_close_and_free_reader);
    require(static_cast<bool>(reader), "Cannot open POD5");
    const auto uuid = uuid_bytes(request.uuid);
    std::size_t read_count{};
    pod5_ok(pod5_get_read_count(reader.get(), &read_count));
    require(read_count > 0 && read_count <= 1000000, "POD5 read metadata bound exceeded");
    std::vector<std::array<std::uint8_t, 16>> ids(read_count);
    static_assert(sizeof(std::array<std::uint8_t, 16>) == sizeof(read_id_t));
    pod5_ok(pod5_get_read_ids(reader.get(), read_count, reinterpret_cast<read_id_t*>(ids.data())));
    require(std::count(ids.begin(), ids.end(), uuid) == 1, "POD5 UUID is missing or duplicated");
    std::size_t batch_count{}, found{};
    pod5_ok(pod5_get_read_batch_count(&batch_count, reader.get()));
    require(batch_count > 0 && batch_count <= 1000000, "POD5 batch metadata bound exceeded");
    std::vector<std::uint32_t> counts(batch_count), positions(1);
    pod5_ok(
        pod5_plan_traversal(reader.get(), uuid.data(), 1, counts.data(), positions.data(), &found));
    require(found == 1 && std::accumulate(counts.begin(), counts.end(), std::size_t{}) == 1,
            "POD5 traversal did not find exactly one UUID");
    const auto index = static_cast<std::size_t>(
        std::distance(counts.begin(), std::find(counts.begin(), counts.end(), 1)));
    require(index < batch_count, "POD5 traversal batch absent");
    Pod5ReadRecordBatch_t* batch_raw{};
    pod5_ok(pod5_get_read_batch(&batch_raw, reader.get(), index));
    Batch batch(batch_raw, pod5_free_read_batch);
    require(static_cast<bool>(batch), "POD5 returned null batch");
    ReadBatchRowInfo_t row{};
    std::uint16_t table_version{};
    pod5_ok(pod5_get_read_batch_row_info_data(batch.get(), positions[0],
                                              READ_BATCH_ROW_INFO_VERSION, &row, &table_version));
    std::array<char, 37> formatted{};
    pod5_ok(pod5_format_read_id(row.read_id, formatted.data()));
    require(horizon <= row.num_samples && row.signal_row_count > 0 &&
                row.signal_row_count <= 1000000,
            "POD5 returned foreign UUID, horizon or signal metadata");
    RunInfoDictData_t* run_raw{};
    pod5_ok(pod5_get_run_info(batch.get(), row.run_info, &run_raw));
    Run run(run_raw, pod5_free_run_info);
    require(run && run->acquisition_id && run->flow_cell_id && run->sample_id,
            "POD5 acquisition metadata absent");
    validate_acquisition(request, formatted.data(), run->acquisition_id, run->flow_cell_id,
                         run->sample_rate);
    RawPrefix result;
    result.batch = index;
    result.row = positions[0];
    result.acquisition_id = run->acquisition_id;
    result.flowcell = run->flow_cell_id;
    result.sample_id = run->sample_id;
    result.acquisition_start_ms = run->acquisition_start_time_ms;
    result.read_start_sample = row.start_sample;
    result.total_read_samples = row.num_samples;
    std::vector<std::uint64_t> signal_indices(static_cast<std::size_t>(row.signal_row_count));
    pod5_ok(pod5_get_signal_row_indices(batch.get(), positions[0], row.signal_row_count,
                                        signal_indices.data()));
    std::vector<std::int16_t> physical;
    for (const auto signal_index : signal_indices) {
        if (physical.size() >= horizon)
            break;
        RowInfo info;
        pod5_ok(pod5_get_signal_row_info(reader.get(), 1, &signal_index, &info.value));
        require(info.value && info.value->stored_sample_count > 0 &&
                    info.value->stored_sample_count <= 1024 * 1024,
                "POD5 signal row sample bound exceeded");
        const auto begin = physical.size();
        physical.resize(begin + info.value->stored_sample_count);
        pod5_ok(pod5_get_signal(reader.get(), info.value, info.value->stored_sample_count,
                                physical.data() + begin));
        result.rows.push_back(
            {signal_index, info.value->stored_sample_count, info.value->stored_byte_count});
    }
    result.physical_samples = physical.size();
    result.admitted = detach(physical, horizon, row.calibration_scale, row.calibration_offset);
    if (offline_full_record_control) {
        require(row.num_samples <= 10000000, "Offline full-record fixture exceeds sample bound");
        std::vector<std::int16_t> full(static_cast<std::size_t>(row.num_samples));
        pod5_ok(pod5_get_read_complete_signal(reader.get(), batch.get(), positions[0], full.size(),
                                              full.data()));
        require(std::equal(result.admitted.samples.begin(), result.admitted.samples.end(),
                           full.begin()),
                "Independent complete-record CPU fixture disagrees with row-prefix extraction");
        result.offline_full_record_samples = full.size();
    }
    for (std::size_t i = horizon; i < physical.size(); ++i) {
        physical[i] = std::bit_cast<std::int16_t>(
            static_cast<std::uint16_t>(std::bit_cast<std::uint16_t>(physical[i]) ^ 0x5a5aU));
        ++result.poisoned_samples;
    }
    result.poisoned = detach(physical, horizon, row.calibration_scale, row.calibration_offset);
    result.positive = result.admitted;
    const auto original = result.positive.samples[10];
    result.positive.samples[10] = original < 0 ? std::numeric_limits<std::int16_t>::max()
                                               : std::numeric_limits<std::int16_t>::min();
    require(result.positive.samples[10] != original,
            "Positive control did not alter admitted sample");
    return result;
}
Prepared prepare(const DetachedPrefix& prefix) {
    require(prefix.samples.size() == prefix.horizon && prefix.horizon > 10 &&
                prefix.horizon <= 12288,
            "Detached prefix size differs from visible horizon");
    require(std::isfinite(prefix.calibration_scale) && prefix.calibration_scale > 0 &&
                std::isfinite(prefix.calibration_offset),
            "Invalid calibration");
    const float scale = 24.0F / prefix.calibration_scale;
    const float shift = 94.0F / prefix.calibration_scale - prefix.calibration_offset;
    require(std::isfinite(scale) && scale > 0 && std::isfinite(shift),
            "Nonfinite normalization parameters");
    at::InferenceMode guard;
    auto tensor = at::empty({static_cast<std::int64_t>(prefix.horizon)},
                            at::TensorOptions().dtype(at::kShort).device(at::kCPU));
    std::memcpy(tensor.data_ptr<std::int16_t>(), prefix.samples.data(),
                prefix.samples.size() * sizeof(std::int16_t));
    dorado::utils::shift_scale_tensor_i16_to_f16_inplace(tensor, shift, scale);
    require(tensor.scalar_type() == at::kHalf && tensor.is_contiguous() && !tensor.is_cuda(),
            "Native scaler output contract differs");
    const auto valid = prefix.horizon - 10;
    const auto padded = ((valid + 5) / 6) * 6;
    Prepared result;
    result.horizon = prefix.horizon;
    result.valid = valid;
    result.padded = padded;
    result.shift = shift;
    result.scale = scale;
    result.half.resize(padded);
    result.input.resize(padded);
    const auto* data = tensor.data_ptr<at::Half>();
    for (std::size_t i = 0; i < padded; ++i) {
        const auto value = data[10 + i % valid];
        result.half[i] = std::bit_cast<std::uint16_t>(value);
        result.input[i] = static_cast<float>(value);
        require(std::isfinite(result.input[i]), "Nonfinite native-half normalized input");
    }
    return result;
}
struct Model::Impl {
    dorado::config::BasecallModelConfig config;
    torch::nn::ModuleHolder<torch::nn::AnyModule> module;
    std::unique_ptr<dorado::basecall::decode::Decoder> decoder;
    explicit Impl(const std::filesystem::path& path)
        : config(dorado::config::load_model_config(path)), module(nullptr) {
        validate_config(config);
        at::InferenceMode guard;
        module = dorado::basecall::load_crf_model(
            config, at::TensorOptions().dtype(at::kFloat).device(at::kCPU));
        decoder =
            dorado::basecall::decode::create_decoder(c10::Device(c10::DeviceType::CPU), config);
        require(decoder && decoder->dtype() == at::kFloat, "Native CPU decoder dtype differs");
    }
};
Model::Model(const std::filesystem::path& path) : impl_(std::make_unique<Impl>(path)) {}
Model::~Model() = default;
Scores Model::forward(const Prepared& input) {
    require(input.horizon > 10 && input.horizon <= 12288 && input.valid == input.horizon - 10 &&
                input.padded == ((input.valid + 5) / 6) * 6 && input.padded <= 12288 &&
                input.half.size() == input.padded && input.input.size() == input.padded,
            "Invalid forward input shape");
    at::InferenceMode guard;
    auto tensor = at::empty({1, 1, static_cast<std::int64_t>(input.padded)},
                            at::TensorOptions().dtype(at::kFloat).device(at::kCPU));
    std::memcpy(tensor.data_ptr<float>(), input.input.data(), input.input.size() * sizeof(float));
    auto scores = impl_->module->forward(tensor).contiguous();
    require(scores.dim() == 3 && scores.size(0) == 1 &&
                scores.size(1) == static_cast<std::int64_t>(input.padded / 6) &&
                scores.size(2) == 1024 && scores.scalar_type() == at::kFloat && !scores.is_cuda() &&
                scores.is_contiguous(),
            "Native CPU model output shape/dtype/device differs");
    Scores result;
    result.timesteps = input.padded / 6;
    result.channels = 1024;
    const auto count = result.timesteps * result.channels;
    result.values.assign(scores.data_ptr<float>(), scores.data_ptr<float>() + count);
    static_cast<void>(difference(result.values, result.values));
    dorado::basecall::decode::DecoderOptions options;
    options.q_shift = impl_->config.qbias;
    options.q_scale = impl_->config.qscale;
    options.blank_score = impl_->config.blank_score;
    auto decoded = impl_->decoder->beam_search_part_2(
        impl_->decoder->beam_search_part_1({scores.transpose(0, 1).contiguous(), 1, options}));
    require(decoded.size() == 1 && decoded[0].sequence.size() == decoded[0].qstring.size() &&
                decoded[0].moves.size() == result.timesteps &&
                std::accumulate(decoded[0].moves.begin(), decoded[0].moves.end(), std::size_t{}) ==
                    decoded[0].sequence.size(),
            "Native CPU prefix decode output contract differs");
    result.sequence = decoded[0].sequence;
    result.quality = decoded[0].qstring;
    for (const auto move : decoded[0].moves) {
        require(move <= 1, "Native CPU move exceeds one");
        result.moves.push_back(static_cast<char>('0' + move));
    }
    return result;
}
}
