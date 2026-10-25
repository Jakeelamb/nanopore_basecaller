#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <htslib/cram.h>
#include <htslib/hfile.h>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <zlib.h>

namespace {
void need(bool value, const char *message) {
    if (!value) throw std::runtime_error(message);
}
struct Reader {
    const std::vector<unsigned char> &bytes;
    std::size_t at{};
    unsigned byte() { need(at < bytes.size(), "bounded metadata truncated"); return bytes[at++]; }
    std::uint32_t little() {
        std::uint32_t result{};
        for (unsigned i = 0; i < 4; ++i) result |= static_cast<std::uint32_t>(byte()) << (8U*i);
        return result;
    }
    std::uint32_t itf() {
        const auto first = byte();
        const unsigned n = first < 128U ? 0U : first < 192U ? 1U : first < 224U ? 2U : first < 240U ? 3U : 4U;
        std::uint32_t value = first & (n == 0U ? 127U : n == 1U ? 63U : n == 2U ? 31U : 15U);
        for (unsigned i = 0; i < n; ++i) value = i == 3U ? (value << 4U) | (byte() & 15U) : (value << 8U) | byte();
        return value;
    }
    std::uint64_t ltf() {
        const auto first = byte();
        unsigned n{};
        while (n < 8U && (first & (128U >> n)) != 0U) ++n;
        std::uint64_t value = n >= 7U ? 0U : first & ((1U << (7U-n))-1U);
        for (unsigned i = 0; i < n; ++i) value = (value << 8U) | byte();
        return value;
    }
};
struct Header {
    bool valid{};
    std::string status{"truncated_or_malformed"};
    std::uint32_t length{}, records{}, blocks{};
    std::int32_t ref{};
    std::uint32_t start{}, span{};
    std::size_t bytes{};
    std::vector<std::uint32_t> landmarks;
};
Header header(const std::vector<unsigned char> &bytes) {
    try {
        Reader r{bytes}; Header h;
        h.length = r.little();
        if (h.length == 0U || h.length > 512U*1024U*1024U) { h.status="length_outside_bound"; return h; }
        h.ref = static_cast<std::int32_t>(r.itf()); h.start = r.itf(); h.span = r.itf(); h.records = r.itf();
        static_cast<void>(r.ltf()); static_cast<void>(r.ltf());
        h.blocks = r.itf(); const auto count = r.itf();
        if (count > 256U || h.blocks == 0U || h.blocks > 1000000U || h.ref < -2 || h.ref > 10000) {
            h.status="fields_outside_bound"; return h;
        }
        for (std::uint32_t i = 0; i < count; ++i) h.landmarks.push_back(r.itf());
        const auto crc_at = r.at;
        const auto stored = r.little(); h.bytes = r.at;
        h.valid = crc32(0L, bytes.data(), static_cast<uInt>(crc_at)) == stored;
        h.status = h.valid ? "valid" : "crc_mismatch";
        return h;
    } catch (const std::exception &) { return {}; }
}
std::vector<unsigned char> prefix(const std::string &path, std::uint64_t offset, std::size_t limit) {
    std::ifstream input(path, std::ios::binary); need(input.good(), "metadata input open failed");
    input.seekg(static_cast<std::streamoff>(offset));
    std::vector<unsigned char> data(limit);
    input.read(reinterpret_cast<char *>(data.data()), static_cast<std::streamsize>(data.size()));
    data.resize(static_cast<std::size_t>(input.gcount())); return data;
}
struct Chunk { std::uint64_t begin{}, end{}; std::string path; };
struct Row { std::int64_t ref{}, start{}, span{}; std::uint64_t container{}, slice{}, size{}; };
const Chunk *locate(const std::vector<Chunk> &chunks, std::uint64_t position) {
    const auto it = std::upper_bound(chunks.begin(), chunks.end(), position,
                                    [](auto value, const Chunk &chunk){ return value < chunk.begin; });
    if (it == chunks.begin()) return nullptr;
    const auto &chunk = *std::prev(it);
    return position < chunk.end ? &chunk : nullptr;
}
struct Native {
    cram_fd *fd{}; hFILE *original{};
    explicit Native(const char *path) {
        fd = cram_open(path, "r"); need(fd != nullptr, "native header open failed"); original = cram_fd_get_fp(fd);
        need(cram_major_vers(fd) == 3 && cram_minor_vers(fd) == 0, "native CRAM version differs");
    }
    ~Native() { if (fd) { cram_fd_set_fp(fd, original); static_cast<void>(cram_close(fd)); } }
    template<class F> void file(const Chunk &chunk, std::uint64_t position, F action) {
        hFILE *fp = hopen(chunk.path.c_str(), "r"); need(fp != nullptr, "native chunk open failed");
        cram_fd_set_fp(fd, fp);
        try {
            need(hseek(fp, static_cast<off_t>(position-chunk.begin), SEEK_SET) >= 0, "native metadata seek failed");
            action(fp);
        } catch (...) {
            cram_fd_set_fp(fd, original); const auto closed=hclose(fp); static_cast<void>(closed); throw;
        }
        cram_fd_set_fp(fd, original); need(hclose(fp) == 0, "native metadata close failed");
    }
};
}

int main(int argc, char **argv) {
    try {
        need(argc == 4, "usage: framing HEADER_CRAM CRAI CHUNKS_TSV");
        Native native(argv[1]);
        const auto actual_first = htell(native.original); need(actual_first >= 26, "native header boundary invalid");
        const auto first = header(prefix(argv[1], 26, 4096)); need(first.valid, "independent header-container CRC failed");
        need(static_cast<std::uint64_t>(actual_first) == 26U + first.bytes + first.length, "native/independent header boundary differs");
        auto mutation = prefix(argv[1], 26, 4096); mutation.at(first.bytes-1U) ^= 1U;
        need(!header(mutation).valid, "header CRC mutation was accepted");
        std::vector<Chunk> chunks;
        { std::ifstream input(argv[3]); need(input.good(), "chunk manifest open failed"); std::string line;
          while (std::getline(input,line)) { std::istringstream row(line); Chunk c;
              need(static_cast<bool>(row >> c.begin >> c.end >> c.path) && c.begin < c.end, "chunk manifest invalid"); chunks.push_back(c); }
        }
        std::sort(chunks.begin(), chunks.end(), [](const Chunk &a, const Chunk &b){ return a.begin < b.begin; });
        need(!chunks.empty() && chunks.size() <= 10000U, "chunk census bound exceeded");
        for (std::size_t i = 1; i < chunks.size(); ++i) need(chunks[i-1].end <= chunks[i].begin, "chunk overlap");
        std::map<std::uint64_t, std::vector<Row>> indexed;
        gzFile index = gzopen(argv[2], "rb"); need(index != nullptr, "CRAI metadata open failed");
        char buffer[4096]; std::size_t index_bytes{};
        while (gzgets(index, buffer, static_cast<int>(sizeof(buffer)))) {
            const std::string line(buffer); index_bytes += line.size(); need(index_bytes <= 16U*1024U*1024U, "CRAI metadata bound exceeded");
            std::istringstream fields(line); Row r;
            need(static_cast<bool>(fields >> r.ref >> r.start >> r.span >> r.container >> r.slice >> r.size), "CRAI fields malformed");
            indexed[r.container].push_back(r);
        }
        need(gzclose(index) == Z_OK && !indexed.empty(), "CRAI metadata read failed");
        const auto indexed_first = indexed.begin()->first;
        const auto delta = actual_first-static_cast<std::int64_t>(indexed_first);
        need(delta >= -65536 && delta <= 65536, "derived header displacement outside probe bound");
        std::uint64_t attempts{}, missing{}, nominal_valid{}, displaced_valid{}, slices{}, matches{}, nonraw{};
        std::cout << "{\"schema\":\"sample-cram-framing/1\",\"source_DNA_decoded\":false,\"native_header_end\":" << actual_first
                  << ",\"independent_header_crc\":true,\"crc_mutation_rejected\":true,\"slice_metadata_raw_only\":true,\"crai_first_container\":" << indexed_first
                  << ",\"derived_header_delta\":" << delta << ",\"observations\":[";
        bool comma{};
        for (const auto &[offset, rows] : indexed) for (const auto shift : {std::int64_t{0}, delta}) {
            const auto signed_position = static_cast<std::int64_t>(offset)+shift;
            if (signed_position < 0) continue;
            const auto position = static_cast<std::uint64_t>(signed_position);
            const auto *chunk = locate(chunks, position);
            if (!chunk) { if (shift == delta && locate(chunks, offset)) ++missing; continue; }
            ++attempts;
            const auto limit = static_cast<std::size_t>(std::min<std::uint64_t>(4096U, chunk->end-position));
            const auto h = header(prefix(chunk->path, position-chunk->begin, limit));
            if (comma) std::cout << ',';
            comma = true;
            std::cout << "{\"crai_offset\":" << offset << ",\"shift\":" << shift << ",\"source_position\":" << position
                      << ",\"prefix_bytes_available\":" << limit << ",\"header_check_status\":\"" << h.status
                      << "\",\"header_crc_valid\":" << (h.valid ? "true" : "false");
            if (h.valid) {
                if (shift == 0) ++nominal_valid; else ++displaced_valid;
                int rid{}; hts_pos_t start{}, span{};
                native.file(*chunk, position, [&](hFILE *fp){
                    cram_container *c = cram_read_container(native.fd); need(c != nullptr, "native CRC-valid container failed");
                    cram_container_get_coords(c, &rid, &start, &span);
                    need(cram_container_get_length(c) == static_cast<std::int32_t>(h.length)
                          && htell(fp) == static_cast<off_t>(position-chunk->begin+h.bytes), "native/independent container framing differs");
                    cram_free_container(c);
                });
                std::cout << ",\"native_container_crc_valid\":true,\"length\":" << h.length << ",\"header_bytes\":" << h.bytes
                          << ",\"ref_id\":" << rid << ",\"start\":" << start << ",\"span\":" << span << ",\"slice_headers\":[";
                bool slice_comma{};
                for (const auto &row : rows) {
                    if (std::find(h.landmarks.begin(), h.landmarks.end(), row.slice) == h.landmarks.end()) continue;
                    const auto slice_position = position+h.bytes+row.slice;
                    const auto *slice_chunk = locate(chunks, slice_position); if (!slice_chunk) continue;
                    const auto data = prefix(slice_chunk->path, slice_position-slice_chunk->begin,
                                             static_cast<std::size_t>(std::min<std::uint64_t>(32U, slice_chunk->end-slice_position)));
                    Reader b{data}; const auto method=b.byte(), type=b.byte(); static_cast<void>(b.itf());
                    const auto compressed=b.itf(), uncompressed=b.itf();
                    if (type!=2U) continue;
                    if (method!=0U) { ++nonraw; continue; }
                    if (compressed!=uncompressed || compressed>65536U || uncompressed>65536U
                        || b.at+compressed+4U > slice_chunk->end-slice_position) continue;
                    int srid{}; hts_pos_t sstart{}, sspan{};
                    native.file(*slice_chunk, slice_position, [&](hFILE *fp){
                        cram_block *block=cram_read_block(native.fd); need(block != nullptr, "native slice block read failed");
                        need(cram_block_get_method(block)==CRAM_COMP_RAW
                             && cram_block_get_comp_size(block)==static_cast<std::int32_t>(compressed)
                             && cram_block_get_uncomp_size(block)==static_cast<std::int32_t>(uncompressed)
                             && htell(fp)==static_cast<off_t>(slice_position-slice_chunk->begin+b.at+compressed+4U),
                             "native RAW slice actual size differs from bounded metadata");
                        need(cram_block_get_content_type(block)==MAPPED_SLICE && cram_uncompress_block(block)==0, "native slice metadata CRC failed");
                        cram_block_slice_hdr *slice=cram_decode_slice_header(native.fd, block); need(slice != nullptr, "native slice metadata failed");
                        cram_slice_hdr_get_coords(slice, &srid, &sstart, &sspan);
                        cram_free_slice_header(slice); cram_free_block(block);
                    });
                    const bool match = srid==row.ref && sstart==row.start && sspan==row.span;
                    ++slices; if (match) ++matches;
                    if (slice_comma) std::cout << ',';
                    slice_comma=true;
                    std::cout << "{\"native_slice_crc_valid\":true,\"method\":\"RAW\",\"metadata_bytes\":" << uncompressed
                              << ",\"ref_id\":" << srid << ",\"start\":" << sstart
                              << ",\"span\":" << sspan << ",\"crai_match\":" << (match ? "true" : "false") << '}';
                }
                std::cout << ']';
            }
            std::cout << '}';
        }
        std::cout << "],\"attempted_cached_headers\":" << attempts << ",\"nominal_crc_valid\":" << nominal_valid
                  << ",\"displaced_crc_valid\":" << displaced_valid << ",\"missing_displaced_prefixes\":" << missing
                  << ",\"native_slice_headers\":" << slices << ",\"matching_crai_slices\":" << matches
                  << ",\"nonraw_slice_headers_not_attempted\":" << nonraw << "}\n";
        return 0;
    } catch (const std::exception &error) { std::cerr << error.what() << '\n'; return 2; }
}
