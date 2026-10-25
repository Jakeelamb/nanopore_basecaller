#include "context_decoder/guarded_io.h"

#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <limits>
#include <set>
#include <stdexcept>
#include <utility>
#include <vector>

namespace context_decoder {
namespace {
void require(bool condition, const char* message) {
    if (!condition) {
        throw std::invalid_argument(message);
    }
}
std::size_t number(const std::string& text) {
    std::size_t value{};
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    require(!text.empty() && result.ec == std::errc{} && result.ptr == text.data() + text.size(),
            "guarded input: invalid unsigned field");
    return value;
}
double real(const std::string& text) {
    std::size_t used{};
    const auto value = std::stod(text, &used);
    require(used == text.size() && std::isfinite(value), "guarded input: invalid finite score");
    return value;
}
std::vector<std::string> split(const std::string& text) {
    std::vector<std::string> out;
    std::size_t start{};
    while (true) {
        const auto end = text.find('\t', start);
        out.push_back(text.substr(start, end == std::string::npos ? end : end - start));
        if (end == std::string::npos) {
            return out;
        }
        start = end + 1;
    }
}
void exact_keys(const Fields& input, const std::set<std::string>& expected) {
    std::set<std::string> supplied;
    for (const auto& [key, value] : input) {
        static_cast<void>(value);
        supplied.insert(key);
    }
    require(supplied == expected, "guarded input: unknown or missing inference field");
}
void file_pin(const Fields& input, const std::string& prefix) {
    const std::filesystem::path path(input.at(prefix + "_path"));
    const auto& hash = input.at(prefix + "_sha256");
    require(hash.size() == 64 && hash.find_first_not_of("0123456789abcdef") == std::string::npos,
            "guarded input: malformed SHA256 pin");
    require(path.is_absolute() && std::filesystem::is_regular_file(path),
            "guarded input: absolute regular input required");
    require(std::filesystem::file_size(path) == number(input.at(prefix + "_size")),
            "guarded input: input byte size changed");
    require(sha256(path) == hash, "guarded input: input hash changed");
}
void dna(const std::string& sequence) {
    require(sequence.find_first_not_of("ACGT") == std::string::npos,
            "guarded input: noncanonical DNA");
}
std::string reverse_complement(std::string sequence) {
    for (auto& base : sequence) {
        switch (base) {
        case 'A':
            base = 'T';
            break;
        case 'C':
            base = 'G';
            break;
        case 'G':
            base = 'C';
            break;
        case 'T':
            base = 'A';
            break;
        case 'N':
            break;
        default:
            throw std::invalid_argument("guarded input: invalid SAM DNA");
        }
    }
    std::reverse(sequence.begin(), sequence.end());
    return sequence;
}
std::vector<std::size_t> emissions(const Fields& meta) {
    const auto& seq = meta.at("SEQ");
    const auto& quality = meta.at("Q");
    dna(seq);
    require(seq.size() == quality.size() && std::all_of(quality.begin(), quality.end(),
                                                        [](char c) {
                                                            const auto byte =
                                                                    static_cast<unsigned char>(c);
                                                            return byte >= 33 && byte <= 126;
                                                        }),
            "guarded input: native SEQ/Q mismatch");
    std::vector<std::size_t> out;
    const auto& moves = meta.at("MOVES");
    for (std::size_t i = 0; i < moves.size(); ++i) {
        require(moves[i] == '0' || moves[i] == '1', "guarded input: invalid native MOVES");
        if (moves[i] == '1') {
            out.push_back(i);
        }
    }
    require(out.size() == seq.size(), "guarded input: native MOVES/SEQ mismatch");
    return out;
}

// Bind molecule offsets independently of matching repeat sequence in the parent.
void bind_sam(const BoundFrame& base,
              const Fields& parent,
              std::size_t read_start,
              std::size_t read_end) {
    std::ifstream input(base.binding.at("location_sam_path"));
    require(input.good(), "guarded input: cannot open parent SAM");
    std::vector<std::string> selected;
    std::string line;
    while (std::getline(input, line)) {
        if (line.starts_with('@')) {
            continue;
        }
        const auto row = split(line);
        require(row.size() >= 11, "guarded input: malformed SAM row");
        if (row[0] == base.binding.at("parent") && (number(row[1]) & 0x900U) == 0) {
            require(selected.empty(), "guarded input: duplicate primary parent SAM");
            selected = row;
        }
    }
    require(input.eof() && !selected.empty(), "guarded input: missing primary parent SAM");
    const auto& row = selected;
    const auto flag = number(row[1]);
    const bool reverse = (flag & 16U) != 0;
    require((flag & 4U) == 0 && row[2] == base.binding.at("contig") &&
                    reverse == (base.binding.at("reverse") == "1") && number(row[3]) > 0,
            "guarded input: parent SAM location/orientation mismatch");
    auto quality = row[10];
    if (reverse) {
        std::reverse(quality.begin(), quality.end());
    }
    require((reverse ? reverse_complement(row[9]) : row[9]) == parent.at("SEQ") &&
                    quality == parent.at("Q"),
            "guarded input: parent SAM SEQ/Q mismatch");
    constexpr auto absent = std::numeric_limits<std::size_t>::max();
    std::vector<std::size_t> mapping(row[9].size(), absent);
    std::size_t query{}, reference = number(row[3]) - 1, cursor{};
    while (cursor < row[5].size()) {
        const auto start = cursor;
        while (cursor < row[5].size() && row[5][cursor] >= '0' && row[5][cursor] <= '9') {
            ++cursor;
        }
        require(cursor > start && cursor < row[5].size(), "guarded input: malformed SAM CIGAR");
        const auto length = number(row[5].substr(start, cursor - start));
        const char op = row[5][cursor++];
        require(length > 0 && length <= 10000000, "guarded input: CIGAR operation bound");
        if (op == 'M' || op == '=' || op == 'X') {
            require(query <= mapping.size() && length <= mapping.size() - query &&
                            reference <= absent - length,
                    "guarded input: CIGAR span overflow");
            for (std::size_t i = 0; i < length; ++i) {
                mapping[query + i] = reference + i;
            }
            query += length;
            reference += length;
        } else if (op == 'I' || op == 'S') {
            require(query <= mapping.size() && length <= mapping.size() - query,
                    "guarded input: CIGAR query overflow");
            query += length;
        } else if (op == 'D' || op == 'N') {
            require(reference <= absent - length, "guarded input: CIGAR reference overflow");
            reference += length;
        } else {
            require(op == 'P', "guarded input: hardclipped/unsupported parent CIGAR");
        }
    }
    require(query == mapping.size(), "guarded input: parent CIGAR/SEQ span mismatch");
    const auto first =
            std::find(mapping.begin(), mapping.end(), number(base.binding.at("ref_start")));
    const auto ref_end = number(base.binding.at("ref_end"));
    require(ref_end > 0, "guarded input: invalid reference interval");
    const auto last = std::find(mapping.begin(), mapping.end(), ref_end - 1);
    require(first != mapping.end() && last != mapping.end() && first <= last,
            "guarded input: native reference anchors absent");
    const auto a = static_cast<std::size_t>(first - mapping.begin());
    const auto b = static_cast<std::size_t>(last - mapping.begin()) + 1;
    require(read_start == (reverse ? mapping.size() - b : a) &&
                    read_end == (reverse ? mapping.size() - a : b),
            "guarded input: original read span differs from SAM anchors");
    for (const auto& span :
         {std::pair{read_start, read_start + 10}, std::pair{read_end - 10, read_end + 10}}) {
        const auto begin = reverse ? mapping.size() - span.second : span.first;
        const auto end = reverse ? mapping.size() - span.first : span.second;
        require(begin < end && end <= mapping.size(), "guarded input: native guard SAM bounds");
        for (std::size_t i = begin; i < end; ++i) {
            require(mapping[i] != absent && (i == begin || mapping[i] == mapping[i - 1] + 1),
                    "guarded input: native guard is gapped or clipped in SAM");
        }
    }
}

double half(std::uint16_t bits) {
    const double sign = (bits & 0x8000U) == 0 ? 1.0 : -1.0;
    const auto exponent = static_cast<int>((bits >> 10U) & 31U);
    const auto fraction = static_cast<double>(bits & 1023U);
    require(exponent != 31, "guarded input: nonfinite DGS1 half payload");
    return exponent == 0 ? sign * fraction * std::pow(2.0, -24)
                         : sign * (1.0 + fraction / 1024.0) * std::pow(2.0, exponent - 15);
}
Frame expanded_scores(const BoundFrame& base,
                      const Fields& meta,
                      std::size_t start,
                      std::size_t end) {
    std::ifstream tensor(base.binding.at("tensor_path"), std::ios::binary);
    std::string header;
    require(static_cast<bool>(std::getline(tensor, header)), "guarded input: missing DGS1 header");
    const auto h = split(header);
    require(h.size() == 15 && h[0] == "DGS1" && h[2] == "1024" && h[3] == "4" && h[4] == "6",
            "guarded input: unsupported DGS1 geometry");
    require(h[1] == meta.at("T") && h[2] == meta.at("C") && h[12] == meta.at("time_offset") &&
                    h[13] == meta.at("token") &&
                    std::filesystem::path(base.binding.at("tensor_path")).filename().string() ==
                            h[13] + "_s" + h[14] + ".scores",
            "guarded input: DGS1 metadata/token/slot mismatch");
    const auto total = number(h[1]);
    require(total > 0 && total <= 1000000 && meta.at("MOVES").size() == total && start < end &&
                    end <= total && end - start <= 256,
            "guarded input: expanded score interval bounds");
    require(std::filesystem::file_size(base.binding.at("tensor_path")) ==
                    header.size() + 1 + total * 2048,
            "guarded input: DGS1 payload size mismatch");
    const auto clamp = real(h[11]);
    require(clamp == 0.0 || clamp == 5.0, "guarded input: unsupported DGS1 clamp");
    Frame frame{end - start, base.scores.state_length, base.scores.initial_state, real(h[5]), {}};
    require(std::bit_cast<std::uint64_t>(frame.stay_score) ==
                    std::bit_cast<std::uint64_t>(base.scores.stay_score),
            "guarded input: DGS1 stay score changed");
    // time_offset identifies a batch slot, never an offset into this tensor's rows.
    tensor.seekg(static_cast<std::streamoff>(header.size() + 1 + start * 2048));
    frame.scores.reserve(frame.timesteps * 1024);
    for (std::size_t i = 0; i < frame.timesteps * 1024; ++i) {
        std::array<unsigned char, 2> bytes{};
        tensor.read(reinterpret_cast<char*>(bytes.data()), 2);
        require(tensor.gcount() == 2, "guarded input: truncated extended tensor rows");
        const auto bits = static_cast<std::uint16_t>(static_cast<unsigned int>(bytes[0]) |
                                                     (static_cast<unsigned int>(bytes[1]) << 8U));
        const auto value = half(bits);
        frame.scores.push_back(clamp == 0.0 ? value : std::clamp(value, -clamp, clamp));
    }
    const auto old_start = number(base.binding.at("t_start"));
    const auto old_end = number(base.binding.at("t_end"));
    require(start == old_start && old_end <= end &&
                    base.scores.scores.size() == (old_end - old_start) * 1024,
            "guarded input: original score overlap bounds mismatch");
    for (std::size_t i = 0; i < base.scores.scores.size(); ++i) {
        require(std::bit_cast<std::uint64_t>(frame.scores[i]) ==
                        std::bit_cast<std::uint64_t>(base.scores.scores[i]),
                "guarded input: reread score overlap differs");
    }
    return frame;
}
}

GuardedBoundFrame load_guarded_frame(const std::filesystem::path& manifest,
                                     const std::string& expected_hash) {
    require(manifest.is_absolute() && std::filesystem::is_regular_file(manifest) &&
                    expected_hash.size() == 64 &&
                    expected_hash.find_first_not_of("0123456789abcdef") == std::string::npos &&
                    sha256(manifest) == expected_hash,
            "guarded input: manifest pin mismatch");
    const auto manifest_size = std::filesystem::file_size(manifest);
    auto binding = fields(manifest, "guarded-frame/2");
    exact_keys(binding, {"base_frame_path",   "base_frame_size", "base_frame_sha256",
                         "parent_path",       "parent_size",     "parent_sha256",
                         "context_path",      "context_size",    "context_sha256",
                         "read_start",        "read_end",        "owned_start",
                         "owned_end",         "anchor_bases",    "future_bases",
                         "expanded_t_start",  "expanded_t_end",  "left_guard",
                         "right_guard",       "native_center",   "retained_chunk_start",
                         "retained_chunk_end"});
    for (const auto& prefix : {"base_frame", "parent", "context"}) {
        file_pin(binding, prefix);
    }
    auto base = load_frame(binding.at("base_frame_path"), binding.at("base_frame_sha256"));
    const auto scalar_comparisons = check_retained_scalar(base);
    const auto meta = fields(base.binding.at("metadata_path"), "DGM1");
    const auto parent = fields(binding.at("parent_path"), "DGP1");
    require(parent.at("read_id") == base.binding.at("parent") &&
                    meta.at("read_id") == parent.at("read_id") &&
                    meta.at("chunk_index") == base.binding.at("chunk_index") &&
                    meta.at("chunk_count") == parent.at("chunk_count") &&
                    parent.at("stride") == "6",
            "guarded input: native parent/chunk association mismatch");
    const auto emitted = emissions(meta);
    static_cast<void>(emissions(parent));
    const auto t_start = number(base.binding.at("t_start"));
    const auto t_end = number(base.binding.at("t_end"));
    const auto first = std::find(emitted.begin(), emitted.end(), t_start);
    const auto last = std::find(emitted.begin(), emitted.end(), t_end);
    require(first != emitted.end() && last != emitted.end() && first < last,
            "guarded input: original interval is not emission anchored");
    const auto a = static_cast<std::size_t>(first - emitted.begin());
    const auto b = static_cast<std::size_t>(last - emitted.begin());
    require(a >= 4 && b - a >= 20 && emitted.size() - b > 10,
            "guarded input: unavailable native guards/future emissions");
    const auto& sequence = meta.at("SEQ");
    require(sequence.substr(a, b - a) == base.native &&
                    sequence.substr(a - 4, 4) == base.binding.at("initial_context"),
            "guarded input: native original interval/state mismatch");
    require(binding.at("anchor_bases") == "10" && binding.at("future_bases") == "10" &&
                    binding.at("left_guard") == sequence.substr(a, 10) &&
                    binding.at("right_guard") == sequence.substr(b - 10, 20) &&
                    binding.at("native_center") == sequence.substr(a + 10, b - a - 20),
            "guarded input: declared guards/center differ from native emissions");
    const auto retained_start = number(binding.at("retained_chunk_start"));
    const auto retained_end = number(binding.at("retained_chunk_end"));
    require(retained_start <= a && b + 10 <= retained_end && retained_end <= sequence.size(),
            "guarded input: guards leave retained native chunk");
    const auto read_start = number(binding.at("read_start"));
    const auto read_end = number(binding.at("read_end"));
    const auto& parent_seq = parent.at("SEQ");
    require(read_start <= read_end && read_end <= parent_seq.size() &&
                    parent_seq.size() - read_end >= 10 && read_end - read_start == b - a &&
                    parent_seq.substr(read_start, b - a + 10) == sequence.substr(a, b - a + 10) &&
                    parent.at("Q").substr(read_start, b - a + 10) ==
                            meta.at("Q").substr(a, b - a + 10) &&
                    number(binding.at("owned_start")) == read_start + 10 &&
                    number(binding.at("owned_end")) == read_end - 10,
            "guarded input: native parent span/owned center mismatch");
    bind_sam(base, parent, read_start, read_end);
    const auto start = number(binding.at("expanded_t_start"));
    const auto end = number(binding.at("expanded_t_end"));
    require(start == emitted[a] && end == emitted[b + 10],
            "guarded input: expanded interval differs from native emissions");
    auto scores = expanded_scores(base, meta, start, end);
    auto context_fields = fields(binding.at("context_path"), "context-centers/2");
    for (const auto& key :
         {"base_frame_sha256", "expanded_t_start", "expanded_t_end", "owned_start", "owned_end"}) {
        require(context_fields.at(key) == binding.at(key),
                "guarded input: center/guard linkage mismatch");
        context_fields.erase(key);
    }
    for (const auto& key :
         {"plan_sha256", "query_index", "parent", "chunk_index", "tensor_sha256", "graph_sha256"}) {
        require(context_fields.at(key) == base.binding.at(key),
                "guarded input: center/base linkage mismatch");
        context_fields.erase(key);
    }
    const auto availability = context_fields.at("availability");
    context_fields.erase("availability");
    RetrievedContext context;
    if (availability == "usable") {
        require(base.context.availability == Availability::usable,
                "guarded input: unavailable base context upgraded");
        context.availability = Availability::usable;
    } else if (availability == "missing") {
        context.availability = Availability::missing;
    } else {
        require(availability == "ambiguous" && base.context.availability != Availability::missing,
                "guarded input: invalid or upgraded context availability");
        context.availability = Availability::ambiguous;
    }
    const auto count = context_fields.size();
    require(count <= 32, "guarded input: projected context path cap exceeded");
    for (std::size_t i = 0; i < count; ++i) {
        const auto key = "sequence_" + std::to_string(i);
        const auto found = context_fields.find(key);
        require(found != context_fields.end(),
                "guarded input: unknown or noncontiguous center field");
        dna(found->second);
        require(found->second.size() <= GuardedPolicy{}.max_center,
                "guarded input: projected center exceeds policy");
        context.sequences.push_back(found->second);
    }
    require((context.availability == Availability::usable) == !context.sequences.empty(),
            "guarded input: unavailable paths differ from empty deletion center");
    context.sequences = canonical_center_context(context);
    GuardedWindow window{std::move(scores), binding.at("left_guard"), binding.at("right_guard"),
                         binding.at("native_center"), std::move(context)};
    validate_guarded(window, GuardedPolicy{});
    for (const auto& prefix : {"base_frame", "parent", "context"}) {
        file_pin(binding, prefix);
    }
    for (const auto& prefix :
         {"tensor", "metadata", "location_receipt", "location_sam", "context", "scalar_controls"}) {
        file_pin(base.binding, prefix);
    }
    require(std::filesystem::file_size(manifest) == manifest_size &&
                    sha256(manifest) == expected_hash,
            "guarded input: manifest changed during consumption");
    return GuardedBoundFrame{std::move(window), std::move(base), std::move(binding),
                             scalar_comparisons};
}
}
