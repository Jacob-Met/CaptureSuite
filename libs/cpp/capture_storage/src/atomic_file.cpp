// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/atomic_file.hpp"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#else
#include <cerrno>
#include <cstdio>
#include <cstring>
#endif

#include <fstream>

namespace capture::storage {
namespace {

std::filesystem::path temp_path_for(const std::filesystem::path& path) {
  auto tmp = path;
  tmp += ".tmp";
  return tmp;
}

void remove_temp_best_effort(const std::filesystem::path& path) {
#ifdef _WIN32
  DeleteFileW(path.wstring().c_str());
#else
  std::error_code ec;
  std::filesystem::remove(path, ec);
#endif
}

bool replace_temp_file(const std::filesystem::path& tmp,
                       const std::filesystem::path& path,
                       std::string& error) {
#ifdef _WIN32
  if (!MoveFileExW(tmp.wstring().c_str(), path.wstring().c_str(),
                   MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
    error = "MoveFileEx failed during atomic write";
    return false;
  }
#else
  // POSIX rename replaces an existing non-directory destination atomically
  // when source and destination are on the same filesystem. The temp file is
  // deliberately a sibling of the destination to preserve that requirement.
  if (std::rename(tmp.c_str(), path.c_str()) != 0) {
    error = "rename failed during atomic write: " + std::string(std::strerror(errno));
    return false;
  }
#endif
  return true;
}

}  // namespace

bool atomic_write_bytes(const std::filesystem::path& path,
                        std::string_view bytes, std::string& error) {
  const auto tmp = temp_path_for(path);
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
  if (!replace_temp_file(tmp, path, error)) {
    remove_temp_best_effort(tmp);
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
