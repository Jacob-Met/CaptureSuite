// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/atomic_file.hpp"

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

#include <fstream>
#include <vector>

namespace capture::storage {

bool atomic_write_bytes(const std::filesystem::path& path,
                        std::string_view bytes, std::string& error) {
  const auto tmp = path.wstring() + L".tmp";
  {
    std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
    if (!out) {
      error = "failed to open temp file for atomic write";
      return false;
    }
    out.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
    out.flush();
    if (!out) {
      error = "failed to write temp file";
      return false;
    }
  }
  if (!MoveFileExW(tmp.c_str(), path.wstring().c_str(),
                   MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
    error = "MoveFileEx failed during atomic write";
    DeleteFileW(tmp.c_str());
    return false;
  }
  return true;
}

bool atomic_write_text(const std::filesystem::path& path, std::string_view text,
                       std::string& error) {
  return atomic_write_bytes(path, text, error);
}

std::string read_text_file(const std::filesystem::path& path, std::string& error) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    error = "failed to open file: " + path.string();
    return {};
  }
  return std::string(std::istreambuf_iterator<char>(in),
                     std::istreambuf_iterator<char>());
}

}  // namespace capture::storage
