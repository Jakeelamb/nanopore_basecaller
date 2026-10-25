#include "context_prefix/prefix.h"
#include <algorithm>
#include <bit>
#include <c10/util/Half.h>
#include <cmath>
#include <limits>

namespace context_prefix {
std::string run_controls() {
    std::size_t assertions{}, shapes{}, tail_cases{}, rejected{};
    auto expect = [&](bool value, const std::string& name) {
        ++assertions;
        require(value, "Prefix control failed: " + name);
    };
    auto reject = [&](auto function, const std::string& name) {
        bool failed{};
        try {
            function();
        } catch (const std::exception&) {
            failed = true;
        }
        expect(failed, name);
        ++rejected;
    };
    for (std::size_t horizon = 11; horizon <= 103; ++horizon) {
        for (const auto calibration : {0.125F, 0.25F, 1.0F}) {
            std::vector<std::int16_t> source(horizon + 37);
            for (std::size_t i = 0; i < source.size(); ++i)
                source[i] =
                    std::bit_cast<std::int16_t>(static_cast<std::uint16_t>((i * 7919) % 65536));
            source[10] = std::numeric_limits<std::int16_t>::min();
            const auto clean = detach(source, horizon, calibration, -17.25F);
            auto normalized = prepare(clean);
            ++shapes;
            expect(normalized.valid == horizon - 10 && normalized.padded % 6 == 0 &&
                       normalized.padded >= normalized.valid &&
                       normalized.padded - normalized.valid < 6,
                   "trim and stride ownership");
            expect(normalized.half.size() == normalized.padded &&
                       normalized.input.size() == normalized.padded,
                   "normalized shape");
            for (std::size_t i = 0; i < normalized.padded; ++i) {
                const auto raw = clean.samples[10 + i % normalized.valid];
                const float reference =
                    (static_cast<float>(raw) - normalized.shift) / normalized.scale;
                const auto half = c10::Half(reference);
                expect(normalized.half[i] == std::bit_cast<std::uint16_t>(half) &&
                           normalized.input[i] == static_cast<float>(half),
                       "native half bits and FP32 conversion");
            }
            for (std::size_t i = horizon; i < source.size(); ++i)
                source[i] = std::bit_cast<std::int16_t>(
                    static_cast<std::uint16_t>(std::bit_cast<std::uint16_t>(source[i]) ^ 0xffffU));
            const auto poison = prepare(detach(source, horizon, calibration, -17.25F));
            expect(poison.half == normalized.half && poison.input == normalized.input &&
                       poison.shift == normalized.shift && poison.scale == normalized.scale,
                   "future tail has no path to model input");
            ++tail_cases;
            for (std::size_t i = 0; i < 10; ++i)
                source[i] = std::numeric_limits<std::int16_t>::max();
            expect(prepare(detach(source, horizon, calibration, -17.25F)).half == normalized.half,
                   "trimmed samples do not influence PA statistics");
            source[10] = std::numeric_limits<std::int16_t>::max();
            expect(prepare(detach(source, horizon, calibration, -17.25F)).half != normalized.half,
                   "admitted sample sensitivity");
            reject([&] { static_cast<void>(prepare({source, horizon, calibration, -17.25F})); },
                   "whole backing row rejected at normalization boundary");
        }
    }
    const std::vector<std::int16_t> source(40, 123);
    for (const auto horizon :
         {std::size_t{0}, std::size_t{10}, std::size_t{41}, std::size_t{12289}})
        reject([&] { static_cast<void>(detach(source, horizon, 0.25F, 0.0F)); }, "invalid horizon");
    for (const auto calibration : {0.0F, -1.0F, std::numeric_limits<float>::infinity(),
                                   std::numeric_limits<float>::quiet_NaN()})
        reject([&] { static_cast<void>(detach(source, 20, calibration, 0.0F)); },
               "invalid calibration");
    reject(
        [&] {
            static_cast<void>(detach(source, 20, 0.25F, std::numeric_limits<float>::quiet_NaN()));
        },
        "nonfinite offset");
    reject(
        [&] {
            static_cast<void>(
                prepare({source, source.size(), std::numeric_limits<float>::denorm_min(), 0.0F}));
        },
        "overflowed normalization parameters");
    reject([&] { static_cast<void>(difference(std::vector<float>{0.0F}, std::vector<float>{})); },
           "comparison shape mismatch");
    reject(
        [&] {
            static_cast<void>(difference(std::vector<float>{std::numeric_limits<float>::infinity()},
                                         std::vector<float>{0.0F}));
        },
        "comparison nonfinite rejection");
    expect(difference(std::vector<float>{0.0F, 2.0F}, std::vector<float>{0.0F, 1.0F}) == 1.0,
           "score sensitivity comparator");
    Request request;
    request.uuid = "7214d805-8331-49aa-af61-478be074d7a6";
    request.acquisition_id = "de8117b1abf27d6d4ac91526772636b9a5ca7fde";
    validate_acquisition(request, request.uuid, request.acquisition_id, "PAW70337", 5000);
    expect(true, "exact acquisition tuple");
    reject(
        [&] { validate_acquisition(request, "foreign", request.acquisition_id, "PAW70337", 5000); },
        "foreign UUID");
    reject([&] { validate_acquisition(request, request.uuid, "foreign", "PAW70337", 5000); },
           "foreign acquisition");
    reject(
        [&] {
            validate_acquisition(request, request.uuid, request.acquisition_id, "PAW71238", 5000);
        },
        "foreign flowcell");
    reject(
        [&] {
            validate_acquisition(request, request.uuid, request.acquisition_id, "PAW70337", 4000);
        },
        "wrong sample rate");
    return "{\"schema\":\"context-prefix-controls/"
           "1\",\"synthetic_only\":true,\"model_loaded\":false,"
           "\"model_forward_calls\":0,\"assertions\":" +
           std::to_string(assertions) + ",\"normalization_shapes\":" + std::to_string(shapes) +
           ",\"poisoned_tail_cases\":" + std::to_string(tail_cases) +
           ",\"rejections\":" + std::to_string(rejected) + "}";
}
}
