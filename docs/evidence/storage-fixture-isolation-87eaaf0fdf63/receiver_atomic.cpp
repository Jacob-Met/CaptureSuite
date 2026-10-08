// SPDX-License-Identifier: GPL-3.0-only
// Independent real-filesystem receiver for CaptureSuite PR #36.
// Only direct POSIX boundaries of the unmodified translation unit are wrapped.
#include "capture/storage/atomic_file.hpp"

#include <cerrno>
#include <cstdarg>
#include <cstdlib>
#include <filesystem>
#include <fcntl.h>
#include <fstream>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

namespace {
enum class Fault {
  none, temp_open, temp_close, parent_open, directory_interrupt,
  directory_sync, directory_close
};
Fault fault = Fault::none;
std::vector<std::string> calls;
unsigned interruptions = 0;

bool directory_fd(int fd) {
  struct stat st {};
  return ::fstat(fd, &st) == 0 && S_ISDIR(st.st_mode);
}

void reset(Fault next = Fault::none) {
  fault = next;
  calls.clear();
  interruptions = 0;
}

void require(bool condition, const std::string& message) {
  if (!condition) throw std::runtime_error(message);
}

std::string bytes_at(const std::filesystem::path& path) {
  std::ifstream in(path, std::ios::binary);
  require(bool(in), "cannot inspect " + path.string());
  return {std::istreambuf_iterator<char>(in), {}};
}

void write_fixture(const std::filesystem::path& path, const std::string& text) {
  std::ofstream out(path, std::ios::binary);
  out.write(text.data(), static_cast<std::streamsize>(text.size()));
  out.close();
  require(bool(out), "fixture write failed");
}

struct Temp {
  std::filesystem::path path;
  Temp() {
    auto pattern = (std::filesystem::temp_directory_path() /
                    "capturesuite-receiver-87ea-XXXXXX").string();
    std::vector<char> buffer(pattern.begin(), pattern.end());
    buffer.push_back('\0');
    const auto result = ::mkdtemp(buffer.data());
    require(result != nullptr, "mkdtemp failed");
    path = result;
  }
  ~Temp() {
    std::error_code error;
    std::filesystem::remove_all(path, error);
  }
};

void expect_before_rename(Fault injected, const char* label) {
  Temp t;
  const auto target = t.path / "manifest.json";
  write_fixture(target, "retained durable original");
  reset(injected);
  std::string error;
  const bool ok = capture::storage::atomic_write_text(target, "proposed", error);
  require(!ok, std::string(label) + " reported success");
  require(!error.empty(), std::string(label) + " omitted its diagnostic");
  require(bytes_at(target) == "retained durable original",
          std::string(label) + " changed the previous target");
  require(!std::filesystem::exists(target.string() + ".tmp"),
          std::string(label) + " left the owned temporary file");
}

void expect_after_rename(Fault injected, const char* label) {
  Temp t;
  const auto target = t.path / "manifest.json";
  write_fixture(target, "before");
  reset(injected);
  std::string error;
  const bool ok = capture::storage::atomic_write_text(target, "complete after", error);
  require(!ok, std::string(label) + " reported durable success");
  require(error.find("replaced") != std::string::npos,
          std::string(label) + " omitted completed replacement");
  require(bytes_at(target) == "complete after",
          std::string(label) + " did not retain complete replacement");
  require(!std::filesystem::exists(target.string() + ".tmp"),
          std::string(label) + " left an unexpected temporary file");
}
}  // namespace

extern "C" int __real_open(const char*, int, ...);
extern "C" int __wrap_open(const char* path, int flags, ...) {
  const bool directory = (flags & O_DIRECTORY) != 0;
  calls.emplace_back(directory ? "open-parent" : "open-temp");
  if ((fault == Fault::temp_open && !directory) ||
      (fault == Fault::parent_open && directory)) {
    errno = EACCES;
    return -1;
  }
  if ((flags & O_CREAT) != 0) {
    va_list args;
    va_start(args, flags);
    const mode_t mode = static_cast<mode_t>(va_arg(args, int));
    va_end(args);
    return __real_open(path, flags, mode);
  }
  return __real_open(path, flags);
}

extern "C" int __real_fsync(int);
extern "C" int __wrap_fsync(int fd) {
  const bool directory = directory_fd(fd);
  calls.emplace_back(directory ? "sync-parent" : "sync-temp");
  if (directory && fault == Fault::directory_interrupt && interruptions++ < 2) {
    errno = EINTR;
    return -1;
  }
  if (directory && fault == Fault::directory_sync) {
    errno = EIO;
    return -1;
  }
  return __real_fsync(fd);
}

extern "C" int __real_close(int);
extern "C" int __wrap_close(int fd) {
  const bool directory = directory_fd(fd);
  calls.emplace_back(directory ? "close-parent" : "close-temp");
  const int result = __real_close(fd);
  if ((fault == Fault::temp_close && !directory) ||
      (fault == Fault::directory_close && directory)) {
    errno = EIO;
    return -1;
  }
  return result;
}

int main() {
  unsigned cases = 0, failures = 0;
  const auto run = [&](const char* name, const std::function<void()>& check) {
    ++cases;
    try {
      reset();
      check();
      std::cout << "PASS " << name << '\n';
    } catch (const std::exception& error) {
      ++failures;
      std::cout << "FAIL " << name << ": " << error.what() << '\n';
    }
  };

  run("absolute path preserves binary payload and truncates old bytes", [] {
    Temp t;
    auto target = t.path / "payload.bin";
    write_fixture(target, std::string(200000, 'z'));
    std::string wanted;
    for (unsigned i = 0; i < 131071; ++i)
      wanted.push_back(static_cast<char>(i % 256));
    std::string error;
    require(capture::storage::atomic_write_bytes(target, wanted, error), error);
    require(bytes_at(target) == wanted, "complete binary content differs");
    const std::vector<std::string> expected {
      "open-temp", "sync-temp", "close-temp",
      "open-parent", "sync-parent", "close-parent"
    };
    require(calls == expected, "successful write did not sync file then parent");
    require(capture::storage::atomic_write_bytes(target, "", error), error);
    require(bytes_at(target).empty(), "zero-byte replacement retained old bytes");
  });
  run("temp reopen refusal preserves original", [] {
    expect_before_rename(Fault::temp_open, "temp reopen");
  });
  run("temp close refusal preserves original", [] {
    expect_before_rename(Fault::temp_close, "temp close");
  });
  run("parent open refusal preserves original", [] {
    expect_before_rename(Fault::parent_open, "parent open");
  });
  run("real rename refusal preserves existing directory", [] {
    Temp t;
    const auto target = t.path / "manifest.json";
    std::filesystem::create_directory(target);
    write_fixture(target / "retain", "untouched");
    std::string error;
    require(!capture::storage::atomic_write_text(target, "candidate", error),
            "directory replacement was accepted");
    require(error.find("rename") != std::string::npos,
            "rename refusal was not identified");
    require(bytes_at(target / "retain") == "untouched",
            "unrelated directory content changed");
    require(!std::filesystem::exists(target.string() + ".tmp"),
            "refused rename left temporary data");
  });
  run("two directory interruptions are retried", [] {
    Temp t;
    reset(Fault::directory_interrupt);
    std::string error;
    const auto target = t.path / "manifest.json";
    require(capture::storage::atomic_write_text(target, "after", error), error);
    require(interruptions == 3, "directory fsync was not retried twice");
    require(bytes_at(target) == "after", "replacement content differs");
  });
  run("directory sync error retains disclosed replacement", [] {
    expect_after_rename(Fault::directory_sync, "directory sync");
  });
  run("directory close error retains disclosed replacement", [] {
    expect_after_rename(Fault::directory_close, "directory close");
  });
  run("relative target syncs current directory", [] {
    Temp t;
    const auto previous = std::filesystem::current_path();
    std::filesystem::current_path(t.path);
    try {
      std::string error;
      require(capture::storage::atomic_write_text("manifest.json", "relative", error),
              error);
      require(bytes_at("manifest.json") == "relative", "relative payload differs");
      std::filesystem::current_path(previous);
    } catch (...) {
      std::filesystem::current_path(previous);
      throw;
    }
  });
  run("missing parent refuses without creating target", [] {
    Temp t;
    const auto target = t.path / "absent" / "manifest.json";
    std::string error;
    require(!capture::storage::atomic_write_text(target, "candidate", error),
            "missing directory was accepted");
    require(!std::filesystem::exists(t.path / "absent"),
            "missing parent path was created");
    require(calls.empty(), "sync stage ran after stream open refusal");
  });

  std::cout << "independent_cases=" << cases << " failures=" << failures << '\n';
  return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
