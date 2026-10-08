// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/atomic_file.hpp"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <system_error>
#include <unistd.h>
#endif

#include <fstream>
#include <vector>

namespace capture::storage {

bool atomic_write_bytes(const std::filesystem::path& path,
                        std::string_view bytes, std::string& error) {
#ifdef _WIN32
  const auto tmp = path.wstring() + L".tmp";
#else
  const auto tmp = path.string() + ".tmp";
#endif
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
#ifdef _WIN32
  if (!MoveFileExW(tmp.c_str(), path.wstring().c_str(),
                   MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
    error = "MoveFileEx failed during atomic write";
    DeleteFileW(tmp.c_str());
    return false;
  }
#else
  const auto remove_temp = [&] {
    std::error_code ignored;
    std::filesystem::remove(tmp, ignored);
  };
  const auto sync_fd = [](int fd) {
    int result;
    do {
      result = ::fsync(fd);
    } while (result != 0 && errno == EINTR);
    return result == 0;
  };
  const auto io_error = [](const char* context) {
    const int code = errno;
    return std::string(context) +
           std::error_code(code, std::generic_category()).message();
  };

  // A failed temp sync must not replace the last durable target.
  const int fd = ::open(tmp.c_str(), O_RDONLY | O_CLOEXEC);
  if (fd < 0) {
    error = io_error("failed to open temp file for sync: ");
    remove_temp();
    return false;
  }
  if (!sync_fd(fd)) {
    error = io_error("failed to sync temp file: ");
    ::close(fd);
    remove_temp();
    return false;
  }
  if (::close(fd) != 0) {
    error = io_error("failed to close synced temp file: ");
    remove_temp();
    return false;
  }

  const auto dir = path.has_parent_path() ? path.parent_path()
                                         : std::filesystem::path(".");
  const int dfd = ::open(dir.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  if (dfd < 0) {
    error = io_error("failed to open parent directory for sync: ");
    remove_temp();
    return false;
  }
  std::error_code ec;
  std::filesystem::rename(tmp, path, ec);
  if (ec) {
    error = "rename failed during atomic write: " + ec.message();
    ::close(dfd);
    remove_temp();
    return false;
  }
  // Rename has happened. Report uncertainty explicitly instead of claiming
  // durable success if the containing directory cannot be synced.
  if (!sync_fd(dfd)) {
    error = io_error("target replaced but failed to sync parent directory: ");
    ::close(dfd);
    return false;
  }
  if (::close(dfd) != 0) {
    error = io_error("target replaced but failed to close synced directory: ");
    return false;
  }
#endif
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
