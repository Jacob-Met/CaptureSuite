// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/hash.hpp"

#include <blake3.h>

#include <fstream>
#include <iomanip>
#include <sstream>
#include <vector>

namespace capture::storage {
namespace {

std::string to_hex(const uint8_t* data, size_t len) {
  std::ostringstream oss;
  oss << std::hex << std::setfill('0');
  for (size_t i = 0; i < len; ++i) {
    oss << std::setw(2) << static_cast<unsigned>(data[i]);
  }
  return oss.str();
}

}  // namespace

std::string blake3_hex(std::string_view data) {
  uint8_t out[BLAKE3_OUT_LEN];
  blake3_hasher hasher;
  blake3_hasher_init(&hasher);
  blake3_hasher_update(&hasher, data.data(), data.size());
  blake3_hasher_finalize(&hasher, out, BLAKE3_OUT_LEN);
  return to_hex(out, BLAKE3_OUT_LEN);
}

std::string blake3_file_hex(const std::filesystem::path& path, std::string& error) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    error = "cannot open for hash: " + path.string();
    return {};
  }
  blake3_hasher hasher;
  blake3_hasher_init(&hasher);
  std::vector<char> buf(1 << 20);
  while (in) {
    in.read(buf.data(), static_cast<std::streamsize>(buf.size()));
    const auto n = in.gcount();
    if (n > 0) {
      blake3_hasher_update(&hasher, buf.data(), static_cast<size_t>(n));
    }
  }
  uint8_t out[BLAKE3_OUT_LEN];
  blake3_hasher_finalize(&hasher, out, BLAKE3_OUT_LEN);
  return to_hex(out, BLAKE3_OUT_LEN);
}

}  // namespace capture::storage
