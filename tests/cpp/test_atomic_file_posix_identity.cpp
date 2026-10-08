// SPDX-License-Identifier: GPL-3.0-only
// Native receiving controls: real disposable files, with I/O faults injected
// only at the atomic writer's descriptor and directory-relative syscalls.
#include "capture/storage/atomic_file.hpp"

#include <algorithm>
#include <cerrno>
#include <cstdarg>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace {
namespace fs = std::filesystem;
enum class Fault { none, short_write, interrupted_write, failed_write,
                   zero_write, failed_close, failed_rename, interrupted_dir_sync,
                   name_collision };
Fault fault = Fault::none;
int temp_fd = -1;
int writes = 0;
int syncs = 0;
int creations = 0;
int creation_flags = 0;

void reset(Fault value = Fault::none) {
  fault = value;
  temp_fd = -1;
  writes = syncs = creations = creation_flags = 0;
}
void require(bool value, const char* text) {
  if (!value) throw std::runtime_error(text);
}
struct Fixture {
  fs::path root;
  Fixture() {
    const auto pattern = (fs::temp_directory_path() /
        "capturesuite-identity-XXXXXX").string();
    std::vector<char> storage(pattern.begin(), pattern.end());
    storage.push_back('\0');
    const auto made = ::mkdtemp(storage.data());
    if (!made) throw std::runtime_error("mkdtemp failed");
    root = made;
  }
  ~Fixture() { std::error_code ignored; fs::remove_all(root, ignored); }
  fs::path file(const std::string& name, const std::string& data) const {
    const auto path = root / name;
    std::ofstream out(path, std::ios::binary);
    out << data;
    out.close();
    require(static_cast<bool>(out), "fixture write failed");
    return path;
  }
};
std::string read(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  require(static_cast<bool>(in), "fixture read failed");
  return {std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
}
void no_owned_temp(const fs::path& dir) {
  for (const auto& item : fs::directory_iterator(dir)) {
    require(!item.path().filename().string().starts_with(".capturesuite-atomic-"),
            "owned temporary file leaked");
  }
}
void alias_case(bool hard, bool self) {
  Fixture fixture;
  const auto target = fixture.file("manifest.json", "old-manifest");
  const auto raw = self ? target : fixture.file("sealed-raw.mcap", "sealed-raw-bytes");
  const fs::path retained = target.string() + ".tmp";
  if (hard) fs::create_hard_link(raw, retained);
  else fs::create_symlink(raw, retained);
  std::string error;
  require(capture::storage::atomic_write_text(target, "new-manifest", error),
          "replacement failed");
  require(read(target) == "new-manifest", "manifest bytes differ");
  require(!fs::is_symlink(target), "replacement retained a symlink");
  require(fs::exists(retained), "pre-existing temporary alias was removed");
  if (!self) require(read(raw) == "sealed-raw-bytes", "sealed file was overwritten");
  if (self && hard) require(read(retained) == "old-manifest", "old inode was overwritten");
  if (!hard) require(fs::is_symlink(retained), "pre-existing symlink changed type");
  no_owned_temp(fixture.root);
}
}  // namespace

extern "C" int __real_openat(int, const char*, int, ...);
extern "C" ssize_t __real_write(int, const void*, size_t);
extern "C" int __real_fsync(int);
extern "C" int __real_close(int);
extern "C" int __real_renameat(int, const char*, int, const char*);

extern "C" int __wrap_openat(int dirfd, const char* path, int flags, ...) {
  mode_t mode = 0;
  if ((flags & O_CREAT) != 0) {
    va_list args;
    va_start(args, flags);
    mode = static_cast<mode_t>(va_arg(args, int));
    va_end(args);
  }
  if ((flags & O_CREAT) != 0) {
    ++creations;
    creation_flags = flags;
    if (fault == Fault::name_collision && creations == 1) {
      errno = EEXIST;
      return -1;
    }
  }
  const int fd = __real_openat(dirfd, path, flags, mode);
  if ((flags & O_CREAT) != 0 && fd >= 0) temp_fd = fd;
  return fd;
}
extern "C" ssize_t __wrap_write(int fd, const void* bytes, size_t count) {
  if (fd == temp_fd) {
    ++writes;
    if (fault == Fault::interrupted_write && writes == 1) { errno = EINTR; return -1; }
    if (fault == Fault::failed_write) { errno = ENOSPC; return -1; }
    if (fault == Fault::zero_write) return 0;
    if (fault == Fault::short_write) count = std::min(count, size_t{3});
  }
  return __real_write(fd, bytes, count);
}
extern "C" int __wrap_fsync(int fd) {
  ++syncs;
  if (fault == Fault::interrupted_dir_sync && syncs == 2) { errno = EINTR; return -1; }
  return __real_fsync(fd);
}
extern "C" int __wrap_close(int fd) {
  const bool selected = fd == temp_fd;
  if (selected) temp_fd = -1;
  const int result = __real_close(fd);
  if (selected && fault == Fault::failed_close) { errno = EIO; return -1; }
  return result;
}
extern "C" int __wrap_renameat(int oldfd, const char* oldpath,
                                int newfd, const char* newpath) {
  if (fault == Fault::failed_rename) { errno = EACCES; return -1; }
  return __real_renameat(oldfd, oldpath, newfd, newpath);
}

int main() {
  int total = 0;
  int failures = 0;
  const auto run = [&](const char* name, const std::function<void()>& check) {
    ++total;
    reset();
    try { check(); std::cout << "PASS " << name << '\n'; }
    catch (const std::exception& error) {
      ++failures;
      std::cerr << "FAIL " << name << ": " << error.what() << '\n';
    }
  };
  run("retained temp symlink does not overwrite sealed file", [] { alias_case(false, false); });
  run("retained temp hardlink does not overwrite sealed file", [] { alias_case(true, false); });
  run("temp symlink to destination cannot become published manifest", [] { alias_case(false, true); });
  run("temp hardlink to destination preserves its old inode", [] { alias_case(true, true); });
  run("ordinary retained temp file remains untouched", [] {
    Fixture f;
    const auto target = f.file("manifest.json", "old");
    const auto retained = f.file("manifest.json.tmp", "interrupted-evidence");
    std::string error;
    require(capture::storage::atomic_write_text(target, "new", error), "write failed");
    require(read(target) == "new", "new bytes differ");
    require(read(retained) == "interrupted-evidence", "retained bytes lost");
    no_owned_temp(f.root);
  });
  run("exclusive writable close-on-exec inode and ordinary umask", [] {
    Fixture f;
    const mode_t previous = ::umask(0027);
    std::string error;
    const auto path = f.root / "manifest.json";
    const bool ok = capture::storage::atomic_write_text(path, "new", error);
    ::umask(previous);
    require(ok, "write failed");
    require(creations == 1 && (creation_flags & O_EXCL) != 0 &&
            (creation_flags & O_CLOEXEC) != 0 && (creation_flags & O_ACCMODE) == O_WRONLY,
            "temporary descriptor lacks required flags");
    struct stat st{};
    require(::stat(path.c_str(), &st) == 0 && (st.st_mode & 0777) == 0640,
            "ordinary file-creation mode changed");
    no_owned_temp(f.root);
  });
  for (const auto& item : {std::pair{Fault::short_write, "partial writes complete"},
                          std::pair{Fault::interrupted_write, "interrupted write retries"},
                          std::pair{Fault::interrupted_dir_sync, "interrupted directory sync retries"},
                          std::pair{Fault::name_collision, "exclusive-name collision retries"}}) {
    run(item.second, [=] {
      Fixture f;
      const auto target = f.file("manifest.json", "old");
      reset(item.first);
      const std::string data("new\0binary-bytes", 16);
      std::string error;
      require(capture::storage::atomic_write_bytes(target, data, error), "write did not complete");
      require(read(target) == data, "bytes differ after retried I/O");
      if (item.first == Fault::short_write) require(writes > 1, "partial write was not exercised");
      if (item.first == Fault::interrupted_write) require(writes == 2, "EINTR was not exercised");
      if (item.first == Fault::interrupted_dir_sync) require(syncs == 3, "directory EINTR was not exercised");
      if (item.first == Fault::name_collision) require(creations == 2, "collision was not exercised");
      no_owned_temp(f.root);
    });
  }
  for (const auto& item : {std::pair{Fault::failed_write, "ENOSPC preserves old manifest"},
                          std::pair{Fault::zero_write, "zero-byte write refuses and preserves old manifest"},
                          std::pair{Fault::failed_close, "close error preserves old manifest"},
                          std::pair{Fault::failed_rename, "rename error preserves old manifest"}}) {
    run(item.second, [=] {
      Fixture f;
      const auto target = f.file("manifest.json", "old");
      reset(item.first);
      std::string error;
      require(!capture::storage::atomic_write_text(target, "new", error), "I/O failure reported success");
      require(!error.empty(), "missing failure diagnostic");
      require(read(target) == "old", "old manifest changed before replacement");
      no_owned_temp(f.root);
    });
  }
  run("empty payload and long Unicode basename", [] {
    Fixture f;
    const auto target = f.root / (std::string(225, 'x') + "-\u00e9\u5b57.json");
    std::string error;
    require(capture::storage::atomic_write_bytes(target, "", error), "empty write failed");
    require(read(target).empty(), "empty file differs");
    no_owned_temp(f.root);
  });
  std::cout << "identity_cases=" << total << " failures=" << failures << '\n';
  return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
