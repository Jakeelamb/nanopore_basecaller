#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <filesystem>
#include <htslib/cram.h>
#include <htslib/hfile.h>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
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
struct Gap : std::runtime_error { Gap() : std::runtime_error("virtual metadata gap") {} };
struct View {
    std::vector<Chunk> spans;
    explicit View(std::vector<Chunk> values) : spans(std::move(values)) {
        std::sort(spans.begin(), spans.end(), [](const Chunk &a, const Chunk &b){ return a.begin < b.begin; });
        need(!spans.empty() && spans.size() <= 10000U, "virtual span census outside bound");
        for (std::size_t i = 0; i < spans.size(); ++i) {
            need(spans[i].end > spans[i].begin && std::filesystem::file_size(spans[i].path)==spans[i].end-spans[i].begin,
                 "virtual span/file extent differs");
            need(i==0U || spans[i-1].end<=spans[i].begin, "virtual span overlap");
        }
    }
    std::vector<unsigned char> read(std::uint64_t position, std::size_t limit, bool exact=false) const {
        need(limit<=65572U, "virtual metadata read exceeds hard bound");
        std::vector<unsigned char> result;
        while (result.size()<limit) {
            const auto *span=locate(spans,position);
            if (!span) break;
            const auto count=static_cast<std::size_t>(std::min<std::uint64_t>(limit-result.size(),span->end-position));
            const auto data=prefix(span->path,position-span->begin,count);
            need(data.size()==count,"retained virtual span truncated");
            result.insert(result.end(),data.begin(),data.end()); position+=count;
        }
        if (exact && result.size()!=limit) throw Gap();
        return result;
    }
    bool covers(std::uint64_t begin, std::uint64_t end) const {
        while (begin<end) {
            const auto *span=locate(spans,begin);
            if (!span) return false;
            begin=std::min(end,span->end);
        }
        return true;
    }
};
void fixture(const std::string &path, const std::string &bytes) {
    need(!std::filesystem::exists(path),"fresh fixture output required");
    std::ofstream out(path,std::ios::binary); out.write(bytes.data(),static_cast<std::streamsize>(bytes.size()));
    need(out.good(),"fixture write failed");
}
void view_controls(const std::string &directory) {
    const auto left=directory+"/adjacent-left", right=directory+"/adjacent-right";
    fixture(left,"AB"); fixture(right,"CD");
    const View joined({{10,12,left},{12,14,right}});
    need(joined.read(11,3,true)==std::vector<unsigned char>({'B','C','D'}),"adjacent span fixture differs");
    const View gap({{10,12,left},{13,15,right}});
    bool rejected{};
    try { static_cast<void>(gap.read(11,3,true)); } catch (const Gap &) { rejected=true; }
    need(rejected && !gap.covers(10,15),"virtual gap fixture accepted");
    rejected=false;
    try { static_cast<void>(View({{10,12,left},{11,13,right}})); }
    catch (const std::runtime_error &error) { rejected=std::string(error.what())=="virtual span overlap"; }
    need(rejected,"virtual overlap fixture accepted");
}
struct Native {
    cram_fd *fd{}; hFILE *original{}; std::string scratch;
    Native(const char *path, const std::string &directory) : scratch(directory+"/native-metadata-scratch") {
        fd = cram_open(path, "r"); need(fd != nullptr, "native header open failed"); original = cram_fd_get_fp(fd);
        need(cram_major_vers(fd) == 3 && cram_minor_vers(fd) == 0, "native CRAM version differs");
    }
    ~Native() { if (fd) { cram_fd_set_fp(fd, original); static_cast<void>(cram_close(fd)); } }
    template<class F> void metadata(const std::vector<unsigned char> &data, F action) {
        need(data.size()<=65572U,"native metadata snapshot exceeds bound");
        { std::ofstream out(scratch,std::ios::binary|std::ios::trunc);
          out.write(reinterpret_cast<const char *>(data.data()),static_cast<std::streamsize>(data.size()));
          need(out.good(),"native metadata snapshot failed"); }
        hFILE *fp = hopen(scratch.c_str(), "r"); need(fp != nullptr, "native metadata open failed");
        cram_fd_set_fp(fd, fp);
        try {
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
        need(argc==6,"usage: framing HEADER_CRAM CRAI SPANS_TSV TARGETS_TSV OWNED_SCRATCH_DIR");
        view_controls(argv[5]);
        Native native(argv[1],argv[5]);
        const auto actual_first=htell(native.original); need(actual_first>=26,"native header boundary invalid");
        const auto first=header(prefix(argv[1],26,4096)); need(first.valid,"independent header-container CRC failed");
        need(static_cast<std::uint64_t>(actual_first)==26U+first.bytes+first.length,"native/independent header boundary differs");
        auto mutation=prefix(argv[1],26,4096); mutation.at(first.bytes-1U)^=1U;
        need(!header(mutation).valid,"header CRC mutation was accepted");
        std::vector<Chunk> chunks;
        { std::ifstream input(argv[3]); need(input.good(),"span manifest open failed"); std::string line;
          while (std::getline(input,line)) { std::istringstream row(line); Chunk c;
              need(static_cast<bool>(row>>c.begin>>c.end>>c.path),"span manifest invalid"); chunks.push_back(c); }
        }
        const View view(std::move(chunks));
        std::map<std::uint64_t,std::vector<Row>> indexed;
        gzFile index=gzopen(argv[2],"rb"); need(index!=nullptr,"CRAI metadata open failed");
        char buffer[4096]; std::size_t index_bytes{};
        while (gzgets(index,buffer,static_cast<int>(sizeof(buffer)))) {
            const std::string line(buffer); index_bytes+=line.size(); need(index_bytes<=16U*1024U*1024U,"CRAI metadata bound exceeded");
            std::istringstream fields(line); Row r;
            need(static_cast<bool>(fields>>r.ref>>r.start>>r.span>>r.container>>r.slice>>r.size),"CRAI fields malformed");
            indexed[r.container].push_back(r);
        }
        need(gzclose(index)==Z_OK && !indexed.empty(),"CRAI metadata read failed");
        const auto indexed_first=indexed.begin()->first;
        const auto delta=actual_first-static_cast<std::int64_t>(indexed_first);
        need(delta==-63,"derived header displacement differs from the priced hypothesis");
        struct Target { std::string role; std::uint64_t offset{},end{}; };
        std::vector<Target> targets;
        { std::ifstream input(argv[4]); need(input.good(),"target manifest open failed"); std::string line;
          while (std::getline(input,line)) { std::istringstream row(line); Target t;
              need(static_cast<bool>(row>>t.role>>t.offset>>t.end) && indexed.contains(t.offset)
                   && (t.role=="selected" ? t.end>t.offset : t.role=="successor" && t.end==0U),"target manifest invalid");
              targets.push_back(t); }
        }
        need(targets.size()==126U,"exact selected/successor target census differs");
        std::sort(targets.begin(),targets.end(),[](const Target &a,const Target &b){return a.offset<b.offset;});
        for (std::size_t i=1;i<targets.size();++i) need(targets[i-1].offset<targets[i].offset,"duplicate target boundary");
        std::uint64_t selected{},successors{},rows{},exact{},multi{},nonraw{};
        std::cout<<"{\"schema\":\"sample-cram-framing/3\",\"source_DNA_decoded\":false,\"native_header_end\":"<<actual_first
                 <<",\"crai_first_container\":"<<indexed_first<<",\"derived_header_delta\":"<<delta
                 <<",\"independent_header_crc\":true,\"crc_mutation_rejected\":true,\"adjacency_control\":true,\"gap_control\":true,\"overlap_control\":true"
                 <<",\"slice_metadata_raw_only\":true,\"observations\":[";
        bool comma{};
        for (const auto &target:targets) {
            need(target.offset>=63U,"candidate physical start underflow");
            const auto position=target.offset-63U;
            const auto h=header(view.read(position,4096));
            need(h.valid && h.records>0U,"candidate positive-record container header/CRC failed");
            const auto actual_end=position+h.bytes+h.length;
            const bool selected_role=target.role=="selected";
            if (selected_role) {
                need(actual_end==target.end-63U && view.covers(position,actual_end),"selected container extent/virtual coverage differs");
                ++selected;
            } else { ++successors; }
            int rid{}; hts_pos_t cstart{},cspan{};
            const auto native_header=view.read(position,h.bytes,true);
            native.metadata(native_header,[&](hFILE *fp){
                cram_container *c=cram_read_container(native.fd); need(c!=nullptr,"native CRC-valid container failed");
                cram_container_get_coords(c,&rid,&cstart,&cspan);
                need(cram_container_get_length(c)==static_cast<std::int32_t>(h.length)
                     && htell(fp)==static_cast<off_t>(h.bytes) && rid==h.ref
                     && cstart==h.start && cspan==h.span,"native/independent container framing differs");
                cram_free_container(c);
            });
            if (comma) std::cout<<',';
            comma=true;
            std::cout<<"{\"role\":\""<<target.role<<"\",\"crai_offset\":"<<target.offset<<",\"physical_start\":"<<position
                     <<",\"physical_end\":"<<actual_end<<",\"header_bytes\":"<<h.bytes<<",\"body_bytes\":"<<h.length
                     <<",\"records_declared\":"<<h.records<<",\"header_crc_valid\":true,\"native_container_crc_valid\":true"
                     <<",\"container_ref_id\":"<<rid<<",\"container_start\":"<<cstart<<",\"container_span\":"<<cspan
                     <<",\"complete_selected_span_available\":"<<(selected_role?"true":"false")<<",\"slice_headers\":[";
            bool slice_comma{};
            if (selected_role) for (const auto &row:indexed.at(target.offset)) {
                need(std::find(h.landmarks.begin(),h.landmarks.end(),row.slice)!=h.landmarks.end()
                     && row.slice<=h.length && row.size<=h.length-row.slice,"CRAI slice landmark/extent differs from native container");
                const auto slice_position=position+h.bytes+row.slice;
                const auto data=view.read(slice_position,32);
                Reader b{data}; const auto method=b.byte(),type=b.byte(); static_cast<void>(b.itf());
                const auto compressed=b.itf(),uncompressed=b.itf();
                need(type==2U,"CRAI landmark is not a mapped-slice metadata block");
                if (slice_comma) std::cout<<',';
                slice_comma=true; ++rows;
                std::cout<<"{\"expected_ref_id\":"<<row.ref<<",\"expected_start\":"<<row.start<<",\"expected_span\":"<<row.span
                         <<",\"slice_start_offset\":"<<row.slice<<",\"slice_size\":"<<row.size<<",\"physical_slice_position\":"<<slice_position;
                if (method!=0U) {
                    ++nonraw;
                    std::cout<<",\"method_code\":"<<method<<",\"coordinate_status\":\"nonraw_not_attempted\"}";
                    continue;
                }
                need(compressed==uncompressed && compressed<=65536U && uncompressed<=65536U
                     && slice_position+b.at+compressed+4U<=actual_end,"RAW metadata size/extent outside hard bound");
                const auto block_bytes=view.read(slice_position,b.at+compressed+4U,true);
                int srid{}; hts_pos_t sstart{},sspan{};
                native.metadata(block_bytes,[&](hFILE *fp){
                    cram_block *block=cram_read_block(native.fd); need(block!=nullptr,"native RAW slice read failed");
                    need(cram_block_get_method(block)==CRAM_COMP_RAW && cram_block_get_content_type(block)==MAPPED_SLICE
                         && cram_block_get_comp_size(block)==static_cast<std::int32_t>(compressed)
                         && cram_block_get_uncomp_size(block)==static_cast<std::int32_t>(uncompressed)
                         && htell(fp)==static_cast<off_t>(block_bytes.size()),"native RAW actual metadata size differs");
                    need(cram_uncompress_block(block)==0,"native RAW slice metadata CRC failed");
                    cram_block_slice_hdr *slice=cram_decode_slice_header(native.fd,block); need(slice!=nullptr,"native slice metadata failed");
                    cram_slice_hdr_get_coords(slice,&srid,&sstart,&sspan);
                    cram_free_slice_header(slice); cram_free_block(block);
                });
                const bool match=srid==row.ref && sstart==row.start && sspan==row.span;
                need(srid==-2 || match,"single-reference CRAI/native slice coordinates differ");
                if (srid==-2) ++multi; else ++exact;
                std::cout<<",\"method\":\"RAW\",\"metadata_bytes\":"<<uncompressed<<",\"native_slice_crc_valid\":true"
                         <<",\"actual_ref_id\":"<<srid<<",\"actual_start\":"<<sstart<<",\"actual_span\":"<<sspan
                         <<",\"coordinate_status\":\""<<(srid==-2?"multi_reference_not_row_comparable":"exact_match")<<"\"}";
            }
            std::cout<<"]}";
        }
        need(selected==81U && successors==45U,"actual selected/successor proof census differs");
        std::cout<<"],\"selected_headers_proven\":"<<selected<<",\"successor_headers_proven\":"<<successors
                 <<",\"selected_rows_examined\":"<<rows<<",\"single_reference_exact_matches\":"<<exact
                 <<",\"multi_reference_not_row_comparable\":"<<multi<<",\"nonraw_not_attempted\":"<<nonraw
                 <<",\"all_selected_header_framing_proven\":true,\"global_displacement_qualified\":false,\"source_qualification\":false}\n";
        return 0;
    } catch (const std::exception &error) { std::cerr<<error.what()<<'\n'; return 2; }
}
