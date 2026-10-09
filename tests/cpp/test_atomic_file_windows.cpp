// SPDX-License-Identifier: GPL-3.0-only
// Real Windows file identities and sharing rules exercise the linked storage API.
#include <catch2/catch_test_macros.hpp>

#include "capture/storage/atomic_file.hpp"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

#include <array>
#include <atomic>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>

namespace {

namespace fs = std::filesystem;

class OwnedDirectory {
 public:
  OwnedDirectory() {
    const auto parent = fs::temp_directory_path();
    static std::atomic<unsigned long long> sequence{0};
    for (int attempt = 0; attempt < 128; ++attempt) {
      const auto name = L"capturesuite-windows-atomic-" +
          std::to_wstring(GetCurrentProcessId()) + L"-" +
          std::to_wstring(sequence.fetch_add(1, std::memory_order_relaxed));
      const auto candidate = parent / name;
      if (CreateDirectoryW(candidate.c_str(), nullptr) != 0) {
        path_ = candidate;
        return;
      }
      const auto code = GetLastError();
      if (code != ERROR_ALREADY_EXISTS && code != ERROR_FILE_EXISTS) {
        throw std::system_error(static_cast<int>(code), std::system_category(),
                                "CreateDirectoryW for isolated atomic test");
      }
    }
    throw std::runtime_error("could not reserve an isolated atomic test directory");
  }

  ~OwnedDirectory() {
    std::error_code ignored;
    fs::remove_all(path_, ignored);
  }

  OwnedDirectory(const OwnedDirectory&) = delete;
  OwnedDirectory& operator=(const OwnedDirectory&) = delete;
  const fs::path& path() const { return path_; }

 private:
  fs::path path_;
};

class FileHandle {
 public:
  explicit FileHandle(HANDLE value) : value_(value) {}
  ~FileHandle() {
    if (value_ != INVALID_HANDLE_VALUE) CloseHandle(value_);
  }

  FileHandle(const FileHandle&) = delete;
  FileHandle& operator=(const FileHandle&) = delete;
  HANDLE get() const { return value_; }

 private:
  HANDLE value_;
};

using FileIdentity = std::array<DWORD, 3>;

FileIdentity file_identity(const fs::path& path) {
  const FileHandle file(CreateFileW(
      path.c_str(), FILE_READ_ATTRIBUTES,
      FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
      nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr));
  const auto open_error = GetLastError();
  INFO("identity open error=" << open_error);
  REQUIRE(file.get() != INVALID_HANDLE_VALUE);
  BY_HANDLE_FILE_INFORMATION info{};
  const auto ok = GetFileInformationByHandle(file.get(), &info);
  const auto info_error = GetLastError();
  INFO("identity query error=" << info_error);
  REQUIRE(ok != 0);
  return {info.dwVolumeSerialNumber, info.nFileIndexHigh, info.nFileIndexLow};
}

void write_fixture(const fs::path& path, std::string_view bytes) {
  REQUIRE_FALSE(fs::exists(path));
  std::ofstream out(path, std::ios::binary | std::ios::trunc);
  REQUIRE(out.is_open());
  out.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
  out.close();
  REQUIRE_FALSE(out.fail());
}

std::string contents(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  REQUIRE(in.is_open());
  std::string bytes{std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
  REQUIRE_FALSE(in.bad());
  return bytes;
}

std::set<fs::path> directory_entries(const fs::path& path) {
  std::set<fs::path> names;
  for (const auto& entry : fs::directory_iterator(path)) {
    names.insert(entry.path().filename());
  }
  return names;
}

void check_published_manifest(const fs::path& path, std::string_view expected) {
  REQUIRE(fs::is_regular_file(path));
  CHECK_FALSE(fs::is_symlink(path));
  CHECK(contents(path) == expected);
}

}  // namespace

TEST_CASE("Windows atomic write preserves a raw-file hardlink at the old temp name",
          "[storage][atomic][windows][alias]") {
  const OwnedDirectory directory;
  const auto raw = directory.path() / "raw.bin";
  const auto manifest = directory.path() / "manifest.json";
  const auto alias = directory.path() / "manifest.json.tmp";
  const std::string raw_bytes = "authored sealed raw sentinel\n";
  const std::string replacement = "{\"state\":\"finalized\",\"new\":true}\n";
  write_fixture(raw, raw_bytes);
  write_fixture(manifest, "{\"state\":\"recording\"}\n");
  REQUIRE(CreateHardLinkW(alias.c_str(), raw.c_str(), nullptr) != 0);
  const auto raw_id = file_identity(raw);
  REQUIRE(file_identity(alias) == raw_id);

  std::string error;
  const auto published = capture::storage::atomic_write_text(manifest, replacement, error);
  INFO("atomic write error=" << error);
  CHECK(published);
  CHECK(contents(raw) == raw_bytes);
  CHECK(file_identity(raw) == raw_id);
  check_published_manifest(manifest, replacement);
  CHECK(file_identity(manifest) != raw_id);
  CHECK(fs::exists(alias));
  if (fs::exists(alias)) {
    CHECK(contents(alias) == raw_bytes);
    CHECK(file_identity(alias) == raw_id);
  }
  const std::set<fs::path> expected{"raw.bin", "manifest.json", "manifest.json.tmp"};
  CHECK(directory_entries(directory.path()) == expected);
}

TEST_CASE("Windows atomic publication failure preserves a prior-target temp hardlink",
          "[storage][atomic][windows][alias]") {
  const OwnedDirectory directory;
  const auto manifest = directory.path() / "manifest.json";
  const auto alias = directory.path() / "manifest.json.tmp";
  const std::string prior = "{\"state\":\"finalized\",\"revision\":1}\n";
  write_fixture(manifest, prior);
  REQUIRE(CreateHardLinkW(alias.c_str(), manifest.c_str(), nullptr) != 0);
  const auto prior_id = file_identity(manifest);
  REQUIRE(file_identity(alias) == prior_id);

  // Reads and writes remain possible, but a live handle denies rename/delete.
  // The current truncating temp writer can therefore damage the prior file
  // before MoveFileExW reports the real publication error.
  const FileHandle held(CreateFileW(
      manifest.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
      nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr));
  const auto hold_error = GetLastError();
  INFO("held-target open error=" << hold_error);
  REQUIRE(held.get() != INVALID_HANDLE_VALUE);

  std::string error;
  const auto published = capture::storage::atomic_write_text(
      manifest, "{\"state\":\"finalized\",\"revision\":2,\"changed\":true}\n", error);
  INFO("atomic write error=" << error);
  CHECK_FALSE(published);
  CHECK_FALSE(error.empty());
  CHECK(contents(manifest) == prior);
  CHECK(file_identity(manifest) == prior_id);
  CHECK(fs::exists(alias));
  if (fs::exists(alias)) {
    CHECK(contents(alias) == prior);
    CHECK(file_identity(alias) == prior_id);
  }
  const std::set<fs::path> expected{"manifest.json", "manifest.json.tmp"};
  CHECK(directory_entries(directory.path()) == expected);
}

TEST_CASE("Windows atomic write preserves an ordinary file at the old temp name",
          "[storage][atomic][windows][alias]") {
  const OwnedDirectory directory;
  const auto manifest = directory.path() / "manifest.json";
  const auto sentinel = directory.path() / "manifest.json.tmp";
  const std::string retained = "unrelated existing temporary-name receipt\n";
  const std::string replacement = "{\"state\":\"finalized\"}\n";
  write_fixture(manifest, "{\"state\":\"recording\"}\n");
  write_fixture(sentinel, retained);
  const auto sentinel_id = file_identity(sentinel);

  std::string error;
  const auto published = capture::storage::atomic_write_text(manifest, replacement, error);
  INFO("atomic write error=" << error);
  CHECK(published);
  check_published_manifest(manifest, replacement);
  CHECK(file_identity(manifest) != sentinel_id);
  CHECK(fs::exists(sentinel));
  if (fs::exists(sentinel)) {
    CHECK(contents(sentinel) == retained);
    CHECK(file_identity(sentinel) == sentinel_id);
  }
  const std::set<fs::path> expected{"manifest.json", "manifest.json.tmp"};
  CHECK(directory_entries(directory.path()) == expected);
}

TEST_CASE("Windows atomic write preserves a raw-file symlink at the old temp name",
          "[storage][atomic][windows][alias]") {
  const OwnedDirectory directory;
  const auto raw = directory.path() / "raw.bin";
  const auto manifest = directory.path() / "manifest.json";
  const auto alias = directory.path() / "manifest.json.tmp";
  const std::string raw_bytes = "authored sealed raw sentinel for symlink\n";
  const std::string replacement = "{\"state\":\"finalized\",\"symlink_case\":true}\n";
  write_fixture(raw, raw_bytes);
  write_fixture(manifest, "{\"state\":\"recording\"}\n");

  const auto linked = CreateSymbolicLinkW(
      alias.c_str(), raw.c_str(), SYMBOLIC_LINK_FLAG_ALLOW_UNPRIVILEGED_CREATE);
  const auto link_error = GetLastError();
  if (linked == 0 && link_error == ERROR_PRIVILEGE_NOT_HELD) {
    SKIP("Windows symlink privilege/developer-mode capability is unavailable");
  }
  INFO("CreateSymbolicLinkW error=" << link_error);
  REQUIRE(linked != 0);
  REQUIRE(fs::is_symlink(alias));
  const auto link_target = fs::read_symlink(alias);
  const auto raw_id = file_identity(raw);
  REQUIRE(file_identity(alias) == raw_id);

  std::string error;
  const auto published = capture::storage::atomic_write_text(manifest, replacement, error);
  INFO("atomic write error=" << error);
  CHECK(published);
  CHECK(contents(raw) == raw_bytes);
  CHECK(file_identity(raw) == raw_id);
  check_published_manifest(manifest, replacement);
  CHECK(file_identity(manifest) != raw_id);
  CHECK(fs::is_symlink(alias));
  if (fs::is_symlink(alias)) {
    CHECK(fs::read_symlink(alias) == link_target);
    CHECK(file_identity(alias) == raw_id);
  }
  const std::set<fs::path> expected{"raw.bin", "manifest.json", "manifest.json.tmp"};
  CHECK(directory_entries(directory.path()) == expected);
}


TEST_CASE("Windows atomic write publishes exact bytes beyond legacy MAX_PATH",
          "[storage][atomic][windows][long-path]") {
  const OwnedDirectory directory;
  const auto deep = directory.path() / std::wstring(90, L'd') /
                    std::wstring(90, L'e') / std::wstring(90, L'f');
  const auto extended = fs::path(L"\\\\?\\" + deep.native());
  REQUIRE(fs::create_directories(extended));
  const auto target = deep / "manifest.json";
  const auto retained = extended / "ordinary-neighbour.bin";
  const std::string sentinel = "retained ordinary bytes\n";
  const std::string replacement("a\0b\n", 4);
  write_fixture(retained, sentinel);
  REQUIRE(target.native().size() > MAX_PATH);

  std::string error;
  CHECK(capture::storage::atomic_write_bytes(target, replacement, error));
  INFO("atomic write error=" << error);
  CHECK(contents(extended / "manifest.json") == replacement);
  CHECK(contents(retained) == sentinel);
  CHECK(directory_entries(extended) ==
        std::set<fs::path>{"manifest.json", "ordinary-neighbour.bin"});
  CHECK(fs::remove_all(extended) == 3);
}

TEST_CASE("Windows atomic long-path refusal cleans only its created sibling",
          "[storage][atomic][windows][long-path]") {
  const OwnedDirectory directory;
  const auto deep = directory.path() / std::wstring(90, L'g') /
                    std::wstring(90, L'h') / std::wstring(90, L'i');
  const auto extended = fs::path(L"\\\\?\\" + deep.native());
  REQUIRE(fs::create_directories(extended));
  const auto target = deep / "manifest.json";
  const auto extended_target = extended / "manifest.json";
  const std::string prior = "retained target bytes\n";
  write_fixture(extended_target, prior);
  const auto before = directory_entries(extended);
  {
    const FileHandle held(CreateFileW(
        extended_target.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr));
    REQUIRE(held.get() != INVALID_HANDLE_VALUE);
    std::string error;
    CHECK_FALSE(capture::storage::atomic_write_text(target, "replacement\n", error));
    CHECK_FALSE(error.empty());
    CHECK(contents(extended_target) == prior);
    CHECK(directory_entries(extended) == before);
  }
  CHECK(fs::remove_all(extended) == 2);
}
