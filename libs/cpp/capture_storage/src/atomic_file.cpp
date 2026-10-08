// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/atomic_file.hpp"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#else
#include <algorithm>
#include <atomic>
#include <cerrno>
#include <fcntl.h>
#include <limits>
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
#else
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

  const auto dir = path.has_parent_path() ? path.parent_path()
                                         : std::filesystem::path(".");
  const auto name = path.filename().string();
  if (name.empty() || name == "." || name == "..") {
    error = "atomic write requires a file name";
    return false;
  }
  const int dfd = ::open(dir.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  if (dfd < 0) {
    error = io_error("failed to open parent directory for sync: ");
    return false;
  }

  // Never open/truncate path.tmp: a retained file or alias at that name may
  // belong to the package. O_EXCL gives this operation its own new inode,
  // while 0666 preserves the ordinary file-creation/umask policy. Both write
  // and sync use its original writable descriptor. Directory-relative calls
  // keep creation, cleanup and replacement in the same opened directory.
  static std::atomic<unsigned long long> next_temp{0};
  std::string tmp;
  int fd = -1;
  for (int attempt = 0; attempt < 128; ++attempt) {
    tmp = ".capturesuite-atomic-" + std::to_string(::getpid()) + "-" +
          std::to_string(next_temp.fetch_add(1, std::memory_order_relaxed));
    if (tmp == name) continue;
    fd = ::openat(dfd, tmp.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC,
                  0666);
    if (fd >= 0 || errno != EEXIST) break;
  }
  if (fd < 0) {
    error = io_error("failed to create exclusive temp file: ");
    ::close(dfd);
    return false;
  }
  const auto discard_temp = [&] {
    if (fd >= 0) ::close(fd);
    ::unlinkat(dfd, tmp.c_str(), 0);
    ::close(dfd);
  };
  std::size_t offset = 0;
  while (offset < bytes.size()) {
    const auto amount = std::min(bytes.size() - offset,
        static_cast<std::size_t>(std::numeric_limits<ssize_t>::max()));
    const auto written = ::write(fd, bytes.data() + offset, amount);
    if (written < 0 && errno == EINTR) continue;
    if (written <= 0) {
      error = written == 0 ? "failed to write temp file: no progress"
                           : io_error("failed to write temp file: ");
      discard_temp();
      return false;
    }
    offset += static_cast<std::size_t>(written);
  }
  // A failed write/sync/close must not replace the last durable target.
  if (!sync_fd(fd)) {
    error = io_error("failed to sync temp file: ");
    discard_temp();
    return false;
  }
  const int closed = ::close(fd);
  fd = -1;  // A failed close must not be retried on a potentially reused fd.
  if (closed != 0) {
    error = io_error("failed to close synced temp file: ");
    discard_temp();
    return false;
  }
  if (::renameat(dfd, tmp.c_str(), dfd, name.c_str()) != 0) {
    error = io_error("rename failed during atomic write: ");
    discard_temp();
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
