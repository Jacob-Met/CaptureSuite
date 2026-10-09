// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/atomic_file.hpp"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <atomic>
#include <system_error>
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
  const auto io_error = [](const char* context, DWORD code) {
    return std::string(context) +
           std::error_code(static_cast<int>(code), std::system_category()).message();
  };
  const auto original_name = path.filename().wstring();
  if (original_name.empty() || original_name == L"." || original_name == L"..") {
    error = "atomic write requires a file name";
    return false;
  }

  // Consume an ordinary relative path once, before constructing either name.
  // The extended namespace does not normalize slashes or dot components.
  auto absolute = path;
  const auto original = path.native();
  const auto has_prefix = [](const std::wstring& value, const wchar_t* prefix) {
    return value.rfind(prefix, 0) == 0;
  };
  if (!has_prefix(original, L"\\\\?\\") &&
      !has_prefix(original, L"\\\\.\\")) {
    std::vector<wchar_t> buffer(32768);
    const DWORD length = ::GetFullPathNameW(
        path.c_str(), static_cast<DWORD>(buffer.size()), buffer.data(), nullptr);
    if (length == 0 || length >= buffer.size()) {
      error = io_error("failed to resolve atomic write path: ",
                       length == 0 ? ::GetLastError() : ERROR_FILENAME_EXCED_RANGE);
      return false;
    }
    const std::wstring full(buffer.data(), length);
    // Preserve the prior handling of DOS device names; do not turn them into
    // literal filenames by applying the extended filesystem prefix.
    if (!has_prefix(full, L"\\\\.\\")) absolute = full;
  }

  const auto io_path = [&](const std::filesystem::path& value,
                           std::filesystem::path& result) {
    const auto native = value.native();
    if (native.size() < MAX_PATH || has_prefix(native, L"\\\\?\\") ||
        has_prefix(native, L"\\\\.\\")) {
      result = value;
      return true;
    }
    // Keep ambiguous ordinary spellings from acquiring literal extended-path
    // meaning. Explicit extended paths retain their caller-chosen spelling.
    for (const auto& component : value.relative_path()) {
      const auto part = component.native();
      if (!part.empty() && (part.back() == L'.' || part.back() == L' ')) {
        error = "long atomic write path requires components without trailing dots or spaces";
        return false;
      }
    }
    if (has_prefix(native, L"\\\\")) {
      result = L"\\\\?\\UNC\\" + native.substr(2);
    } else {
      result = L"\\\\?\\" + native;
    }
    return true;
  };
  std::filesystem::path destination;
  if (!io_path(absolute, destination)) return false;
  const auto dir = absolute.has_parent_path() ? absolute.parent_path()
                                              : std::filesystem::path(L".");
  const auto name = absolute.filename().wstring();

  // A pre-existing path.tmp may alias retained data. CREATE_NEW gives this
  // operation its own file; never open, truncate, or clean up a prior name.
  static std::atomic<unsigned long long> next_temp{0};
  std::filesystem::path tmp;
  HANDLE file = INVALID_HANDLE_VALUE;
  DWORD create_error = ERROR_FILE_EXISTS;
  for (int attempt = 0; attempt < 128; ++attempt) {
    const auto temp_name = L".capturesuite-atomic-" +
        std::to_wstring(::GetCurrentProcessId()) + L"-" +
        std::to_wstring(next_temp.fetch_add(1, std::memory_order_relaxed));
    if (::CompareStringOrdinal(temp_name.c_str(), -1, name.c_str(), -1, TRUE) ==
        CSTR_EQUAL) {
      continue;
    }
    if (!io_path(dir / temp_name, tmp)) return false;
    file = ::CreateFileW(tmp.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW,
                         FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file != INVALID_HANDLE_VALUE) break;
    create_error = ::GetLastError();
    if (create_error != ERROR_FILE_EXISTS && create_error != ERROR_ALREADY_EXISTS) break;
  }
  if (file == INVALID_HANDLE_VALUE) {
    error = io_error("failed to create exclusive temp file: ", create_error);
    return false;
  }
  const auto discard_temp = [&] {
    if (file != INVALID_HANDLE_VALUE) {
      ::CloseHandle(file);
      file = INVALID_HANDLE_VALUE;
    }
    ::DeleteFileW(tmp.c_str());
  };

  std::size_t offset = 0;
  while (offset < bytes.size()) {
    const auto remaining = bytes.size() - offset;
    const auto amount = static_cast<DWORD>(
        remaining > static_cast<std::size_t>(MAXDWORD) ? MAXDWORD : remaining);
    DWORD written = 0;
    if (!::WriteFile(file, bytes.data() + offset, amount, &written, nullptr)) {
      error = io_error("failed to write temp file: ", ::GetLastError());
      discard_temp();
      return false;
    }
    if (written == 0) {
      error = "failed to write temp file: no progress";
      discard_temp();
      return false;
    }
    offset += static_cast<std::size_t>(written);
  }
  if (!::FlushFileBuffers(file)) {
    error = io_error("failed to sync temp file: ", ::GetLastError());
    discard_temp();
    return false;
  }
  const BOOL closed = ::CloseHandle(file);
  file = INVALID_HANDLE_VALUE;
  if (!closed) {
    error = io_error("failed to close synced temp file: ", ::GetLastError());
    discard_temp();
    return false;
  }

  // Keep the existing same-directory, write-through replacement boundary.
  if (!::MoveFileExW(tmp.c_str(), destination.c_str(),
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
    error = io_error("MoveFileEx failed during atomic write: ", ::GetLastError());
    discard_temp();
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
