#pragma once
#include "context_study/candidate.h"
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace context_study {
struct Packet {
    std::string manifest;
    std::vector<CandidateCase> cases;
};
using Record = std::vector<std::string>;
struct RawPacket {
    std::string manifest;
    std::vector<Record> records;
};
std::string sha256(const std::string &bytes);
std::string file_sha256(const std::filesystem::path &path);
bool digest(const std::string &value);
std::size_t natural(const std::string &text);
double finite_number(const std::string &text);
bool boolean(const std::string &text);
RawPacket read_records(const std::filesystem::path &path, const std::string &expected,
                       const std::string &schema);
Packet read_candidates(const std::filesystem::path &path, const std::string &expected);
Packet parse_candidates(const RawPacket &raw);
std::string write_replays(const Packet &packet, const std::filesystem::path &output);
std::string json_string(const std::string &value);
std::string pin_json(const std::filesystem::path &path);
void synced_write(const std::filesystem::path &path, const std::string &bytes);
void verify_compiled_sources();
std::string source_json();
struct Invocation {
    std::string command;
    std::map<std::string, std::string> options;
    std::filesystem::path output;
};
Invocation begin_invocation(int argc, char **argv, bool inference);
void finish_invocation(const Invocation &invocation, const std::string &result,
                       const std::vector<std::string> &files);
}
