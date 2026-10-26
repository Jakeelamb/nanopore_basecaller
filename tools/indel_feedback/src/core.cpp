#include "indel_feedback/core.h"
#include "source_witness.h"

#include <fcntl.h>
#include <openssl/evp.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <charconv>
#include <fstream>
#include <iomanip>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>

namespace indel_feedback {
void require(bool condition, const std::string &message) {
  if (!condition) {
    throw std::invalid_argument(message);
  }
}
void dna(const std::string &sequence, bool allow_n) {
  require(
      std::all_of(sequence.begin(), sequence.end(),
                  [allow_n](char base) {
                    return std::string(allow_n ? "ACGTN" : "ACGT").find(base) !=
                           std::string::npos;
                  }),
      "noncanonical sequence");
}
std::size_t natural(const std::string &value) {
  std::size_t result{};
  const auto parsed =
      std::from_chars(value.data(), value.data() + value.size(), result);
  require(!value.empty() && parsed.ec == std::errc{} &&
              parsed.ptr == value.data() + value.size(),
          "invalid unsigned integer");
  return result;
}
std::vector<std::string> split(const std::string &line, char delimiter) {
  std::vector<std::string> values;
  std::size_t cursor{};
  do {
    const auto end = line.find(delimiter, cursor);
    values.push_back(
        line.substr(cursor, end == std::string::npos ? end : end - cursor));
    if (end == std::string::npos) {
      break;
    }
    cursor = end + 1;
  } while (true);
  return values;
}
std::vector<std::pair<std::size_t, char>> cigar(const std::string &text) {
  std::vector<std::pair<std::size_t, char>> result;
  std::size_t cursor{};
  while (cursor < text.size()) {
    const auto begin = cursor;
    while (cursor < text.size() && text[cursor] >= '0' && text[cursor] <= '9') {
      ++cursor;
    }
    require(begin < cursor && cursor < text.size(), "malformed CIGAR");
    const auto length = natural(text.substr(begin, cursor - begin));
    const auto op = text[cursor++];
    require(length > 0 && length <= 100000000 &&
                std::string("=XIDS").find(op) != std::string::npos,
            "unsupported EQX CIGAR operation");
    result.emplace_back(length, op);
  }
  require(!result.empty(), "empty CIGAR");
  return result;
}
std::string reverse_complement(const std::string &sequence) {
  dna(sequence, true);
  std::string result;
  result.reserve(sequence.size());
  for (auto it = sequence.rbegin(); it != sequence.rend(); ++it) {
    result += *it == 'A'   ? 'T'
              : *it == 'C' ? 'G'
              : *it == 'G' ? 'C'
              : *it == 'T' ? 'A'
                           : 'N';
  }
  return result;
}
namespace {
std::string finish(EVP_MD_CTX *context) {
  std::array<unsigned char, EVP_MAX_MD_SIZE> bytes{};
  unsigned int count{};
  require(EVP_DigestFinal_ex(context, bytes.data(), &count) == 1 && count == 32,
          "SHA256 final");
  std::ostringstream output;
  output << std::hex << std::setfill('0');
  for (unsigned int i = 0; i < count; ++i) {
    output << std::setw(2) << static_cast<unsigned int>(bytes[i]);
  }
  return output.str();
}
using Hash = std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)>;
Hash hash_context() {
  Hash result(EVP_MD_CTX_new(), EVP_MD_CTX_free);
  require(result && EVP_DigestInit_ex(result.get(), EVP_sha256(), nullptr) == 1,
          "SHA256 init");
  return result;
}
} // namespace
std::string digest(const std::string &bytes) {
  auto context = hash_context();
  require(EVP_DigestUpdate(context.get(), bytes.data(), bytes.size()) == 1,
          "SHA256 update");
  return finish(context.get());
}
std::string file_digest(const fs::path &path) {
  require(path.is_absolute() && !fs::is_symlink(path) &&
              fs::is_regular_file(path),
          "absolute nonsymlink input required");
  std::ifstream input(path, std::ios::binary);
  require(input.good(), "cannot open hashed input");
  auto context = hash_context();
  std::array<char, 65536> buffer{};
  while (input) {
    input.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
    require(input.gcount() >= 0 &&
                EVP_DigestUpdate(context.get(), buffer.data(),
                                 static_cast<std::size_t>(input.gcount())) == 1,
            "SHA256 input update");
  }
  require(input.eof(), "hashed input read failed");
  return finish(context.get());
}
Json pin(const fs::path &path) {
  return {{"path", path.string()},
          {"size", fs::file_size(path)},
          {"sha256", file_digest(path)}};
}
void check_pin(const Json &value) {
  require(value.is_object() && value.size() == 3 && value.contains("path") &&
              value.contains("size") && value.contains("sha256"),
          "FilePin fields differ");
  const fs::path path(value.at("path").get<std::string>());
  require(path.is_absolute() && !fs::is_symlink(path) &&
              fs::is_regular_file(path) &&
              fs::file_size(path) == value.at("size").get<std::uintmax_t>() &&
              file_digest(path) == value.at("sha256"),
          "consumed FilePin differs");
}
Json read_json(const fs::path &path, std::uintmax_t maximum) {
  require(path.is_absolute() && !fs::is_symlink(path) &&
              fs::is_regular_file(path) && fs::file_size(path) <= maximum,
          "JSON input bound/path");
  std::ifstream input(path);
  require(input.good(), "cannot open JSON input");
  std::vector<std::set<std::string>> keys;
  const auto reject_duplicates = [&](int, Json::parse_event_t event,
                                     Json &parsed) {
    if (event == Json::parse_event_t::object_start) {
      keys.emplace_back();
    }
    if (event == Json::parse_event_t::key) {
      require(!keys.empty() &&
                  keys.back().insert(parsed.get<std::string>()).second,
              "duplicate JSON key");
    }
    if (event == Json::parse_event_t::object_end) {
      keys.pop_back();
    }
    return true;
  };
  return Json::parse(input, reject_duplicates);
}
void fresh(const fs::path &path, const std::string &bytes) {
  const int fd =
      ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
  require(fd >= 0, "output already exists or cannot be created");
  std::size_t written{};
  while (written < bytes.size()) {
    const auto count =
        ::write(fd, bytes.data() + written, bytes.size() - written);
    if (count <= 0) {
      ::close(fd);
      throw std::runtime_error("output write failed");
    }
    written += static_cast<std::size_t>(count);
  }
  const int synced = ::fsync(fd);
  const int closed = ::close(fd);
  require(synced == 0 && closed == 0, "output sync/close failed");
}
void verify_sources() {
  require(fs::current_path() == fs::path(source_root_path),
          "compiled source cwd differs");
  for (const auto &item : compiled_sources) {
    check_pin(
        {{"path", item.path}, {"size", item.size}, {"sha256", item.sha256}});
  }
}
Json source_witness() {
  Json result = Json::array();
  for (const auto &item : compiled_sources) {
    result.push_back(
        {{"path", item.path}, {"size", item.size}, {"sha256", item.sha256}});
  }
  return result;
}
Counts &Counts::operator+=(const Counts &other) {
  m += other.m;
  x += other.x;
  i += other.i;
  d += other.d;
  return *this;
}
Json counts_json(const Counts &counts) {
  return {{"m", counts.m}, {"x", counts.x}, {"i", counts.i}, {"d", counts.d}};
}
} // namespace indel_feedback
