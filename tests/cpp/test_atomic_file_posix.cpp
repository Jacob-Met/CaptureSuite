// SPDX-License-Identifier: GPL-3.0-only
// Linux linker wrapping injects native write/fsync/close errors without test
// hooks in the production implementation. Other I/O uses disposable real files.
#include "capture/storage/atomic_file.hpp"

#include <algorithm>
#include <cerrno>
#include <cstdlib>
#include <fcntl.h>
#include <filesystem>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unistd.h>
#include <vector>

namespace {
enum class Fault {
  none, file_sync, directory_sync, interrupted_sync, write_error, zero_write,
  short_write, interrupted_write, writer_close, interrupted_close
};
Fault fault = Fault::none;
int sync_calls = 0;
int write_calls = 0;
int writer_close_calls = 0;
int writer_fd = -1;
bool synced_writer = false;

void reset(Fault next = Fault::none) {
  fault = next;
  sync_calls = 0;
  write_calls = 0;
  writer_close_calls = 0;
  writer_fd = -1;
  synced_writer = false;
}

void require(bool condition, const char* message) {
  if (!condition) throw std::runtime_error(message);
}

struct TemporaryDirectory {
  std::filesystem::path path;
  TemporaryDirectory() {
    const auto pattern =
        (std::filesystem::temp_directory_path() / "capturesuite-durability-XXXXXX")
            .string();
    std::vector<char> buffer(pattern.begin(), pattern.end());
    buffer.push_back('\0');
    const auto result = ::mkdtemp(buffer.data());
    if (!result) throw std::runtime_error("mkdtemp failed");
    path = result;
  }
  ~TemporaryDirectory() {
    std::error_code ignored;
    std::filesystem::remove_all(path, ignored);
  }
};
}  // namespace

extern "C" ssize_t __real_write(int fd, const void* buffer, std::size_t count);
extern "C" ssize_t __wrap_write(int fd, const void* buffer, std::size_t count) {
  ++write_calls;
  writer_fd = fd;
  if (fault == Fault::write_error) {
    errno = EIO;
    return -1;
  }
  if (fault == Fault::zero_write) return 0;
  if (fault == Fault::interrupted_write && write_calls == 1) {
    errno = EINTR;
    return -1;
  }
  if (fault == Fault::short_write) count = std::min(count, std::size_t{2});
  return __real_write(fd, buffer, count);
}

extern "C" int __real_close(int fd);
extern "C" int __wrap_close(int fd) {
  // The parent directory has its own descriptor and legitimate cleanup.
  // Count every attempted close of the writer fd, including unsafe retries.
  if (fd == writer_fd) ++writer_close_calls;
  const int flags = ::fcntl(fd, F_GETFL);
  const bool writable = flags >= 0 && (flags & O_ACCMODE) != O_RDONLY;
  const int result = __real_close(fd);
  if (writable && (fault == Fault::writer_close ||
                   fault == Fault::interrupted_close)) {
    // Linux has released the descriptor even when close reports an I/O error.
    errno = fault == Fault::writer_close ? EIO : EINTR;
    return -1;
  }
  return result;
}

extern "C" int __real_fsync(int fd);
extern "C" int __wrap_fsync(int fd) {
  ++sync_calls;
  const int flags = ::fcntl(fd, F_GETFL);
  if (fd == writer_fd && flags >= 0 && (flags & O_ACCMODE) != O_RDONLY) {
    synced_writer = true;
  }
  if ((fault == Fault::file_sync && sync_calls == 1) ||
      (fault == Fault::directory_sync && sync_calls == 2)) {
    errno = EIO;
    return -1;
  }
  if (fault == Fault::interrupted_sync && sync_calls == 1) {
    errno = EINTR;
    return -1;
  }
  return __real_fsync(fd);
}

int main() {
  int cases = 0;
  int failures = 0;
  const auto run = [&](const char* name, const std::function<void()>& check) {
    ++cases;
    try {
      reset();
      check();
      std::cout << "PASS " << name << '\n';
    } catch (const std::exception& error) {
      ++failures;
      std::cerr << "FAIL " << name << ": " << error.what() << '\n';
    }
  };

  run("replacement syncs file and parent directory", [] {
    TemporaryDirectory directory;
    const auto path = directory.path / "manifest.json";
    std::string error;
    require(capture::storage::atomic_write_text(path, "before", error),
            "initial write failed");
    reset();
    require(capture::storage::atomic_write_text(path, "after", error),
            "replacement failed");
    require(sync_calls == 2, "file and directory must both be synced");
    require(synced_writer, "fsync must use the original writable descriptor");
    require(capture::storage::read_text_file(path, error) == "after",
            "replacement bytes differ");
    require(!std::filesystem::exists(path.string() + ".tmp"),
            "temporary file survived replacement");
  });

  run("file sync failure preserves previous target", [] {
    TemporaryDirectory directory;
    const auto path = directory.path / "manifest.json";
    std::string error;
    require(capture::storage::atomic_write_text(path, "before", error),
            "initial write failed");
    reset(Fault::file_sync);
    require(!capture::storage::atomic_write_text(path, "after", error),
            "fsync EIO incorrectly reported success");
    require(!error.empty(), "sync failure needs a diagnostic");
    require(capture::storage::read_text_file(path, error) == "before",
            "failed temp sync replaced the previous target");
    require(!std::filesystem::exists(path.string() + ".tmp"),
            "failed temp sync left a temporary file");
  });

  run("directory sync failure reports uncertain durability", [] {
    TemporaryDirectory directory;
    const auto path = directory.path / "manifest.json";
    std::string error;
    require(capture::storage::atomic_write_text(path, "before", error),
            "initial write failed");
    reset(Fault::directory_sync);
    require(!capture::storage::atomic_write_text(path, "after", error),
            "directory fsync EIO incorrectly reported success");
    require(error.find("replaced") != std::string::npos,
            "diagnostic must disclose completed replacement");
    require(capture::storage::read_text_file(path, error) == "after",
            "replacement bytes must remain complete after directory sync error");
  });

  run("interrupted file sync is retried", [] {
    TemporaryDirectory directory;
    const auto path = directory.path / "manifest.json";
    std::string error;
    reset(Fault::interrupted_sync);
    require(capture::storage::atomic_write_text(path, "after", error),
            "EINTR should be retried");
    require(sync_calls == 3, "interrupted fsync was not retried");
  });

  const auto check_writer_failure = [](Fault injected, const char* diagnostic) {
    TemporaryDirectory directory;
    const auto path = directory.path / "manifest.json";
    std::string error;
    require(capture::storage::atomic_write_text(path, "before", error),
            "initial write failed");
    reset(injected);
    require(!capture::storage::atomic_write_text(path, "after", error),
            "writer error incorrectly reported success");
    require(error.find(diagnostic) != std::string::npos,
            "writer failure diagnostic is missing");
    require(writer_close_calls == 1, "writer close was skipped or retried");
    require(capture::storage::read_text_file(path, error) == "before",
            "writer failure replaced previous target");
    require(!std::filesystem::exists(path.string() + ".tmp"),
            "writer failure left a temporary file");
  };
  run("write failure preserves previous target", [&] {
    check_writer_failure(Fault::write_error, "failed to write");
    require(sync_calls == 0, "failed write must not reach fsync");
  });
  run("zero-progress write fails without looping", [&] {
    check_writer_failure(Fault::zero_write, "no progress");
    require(write_calls == 1, "zero-progress write must not be retried");
  });
  run("writer close failure preserves previous target", [&] {
    check_writer_failure(Fault::writer_close, "failed to close");
    require(sync_calls == 1, "writer must sync before close");
  });
  run("interrupted writer close is not retried", [&] {
    check_writer_failure(Fault::interrupted_close, "failed to close");
  });
  const auto check_write_retry = [](Fault injected) {
    TemporaryDirectory directory;
    const auto path = directory.path / "manifest.json";
    std::string error;
    reset(injected);
    require(capture::storage::atomic_write_text(path, "after", error),
            "retryable write did not succeed");
    require(write_calls >= 2, "short or interrupted write was not retried");
    require(capture::storage::read_text_file(path, error) == "after",
            "retry lost or duplicated bytes");
    require(synced_writer, "retried writer must be synced before replacement");
  };
  run("short writes retain every byte", [&] {
    check_write_retry(Fault::short_write);
  });
  run("interrupted write is retried", [&] {
    check_write_retry(Fault::interrupted_write);
  });

  std::cout << "durability_cases=" << cases << " failures=" << failures << '\n';
  return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
