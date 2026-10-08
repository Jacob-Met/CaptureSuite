// SPDX-License-Identifier: GPL-3.0-only
// Linux linker wrapping injects errors at real fsync calls without test hooks
// in the production implementation. All other I/O uses disposable real files.
#include "capture/storage/atomic_file.hpp"

#include <cerrno>
#include <cstdlib>
#include <filesystem>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
enum class Fault { none, file_sync, directory_sync, interrupted_sync };
Fault fault = Fault::none;
int sync_calls = 0;

void reset(Fault next = Fault::none) {
  fault = next;
  sync_calls = 0;
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

extern "C" int __real_fsync(int fd);
extern "C" int __wrap_fsync(int fd) {
  ++sync_calls;
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
  int failures = 0;
  const auto run = [&](const char* name, const std::function<void()>& check) {
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

  std::cout << "durability_cases=4 failures=" << failures << '\n';
  return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
