// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/atomic_file.hpp"
#include "capture/storage/disk_watchdog.hpp"

#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace {

std::filesystem::path storage_test_dir() {
  return std::filesystem::temp_directory_path() /
         "capturesuite_storage_portability_test";
}

std::filesystem::path temp_sibling(const std::filesystem::path& path) {
  auto tmp = path;
  tmp += ".tmp";
  return tmp;
}

}  // namespace

TEST_CASE("atomic_write_text replaces an existing file without leaving temp state",
          "[storage][atomic]") {
  const auto dir = storage_test_dir();
  const auto path = dir / "manifest.json";
  std::error_code ec;
  std::filesystem::remove_all(dir, ec);
  std::filesystem::create_directories(dir);
  {
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    out << "old";
  }

  std::string error;
  REQUIRE(capture::storage::atomic_write_text(path, "new-bytes", error));
  REQUIRE(error.empty());
  REQUIRE_FALSE(std::filesystem::exists(temp_sibling(path)));

  std::string read_error;
  REQUIRE(capture::storage::read_text_file(path, read_error) == "new-bytes");
  REQUIRE(read_error.empty());

  std::filesystem::remove_all(dir, ec);
}

TEST_CASE("atomic_write_text fails closed when the destination parent is absent",
          "[storage][atomic]") {
  const auto dir = storage_test_dir();
  const auto path = dir / "missing" / "manifest.json";
  std::error_code ec;
  std::filesystem::remove_all(dir, ec);

  std::string error;
  REQUIRE_FALSE(capture::storage::atomic_write_text(path, "data", error));
  REQUIRE_FALSE(error.empty());
  REQUIRE_FALSE(std::filesystem::exists(path));
  REQUIRE_FALSE(std::filesystem::exists(temp_sibling(path)));
}

TEST_CASE("DiskWatchdog reports real free space for an existing volume",
          "[storage][disk]") {
  const auto dir = storage_test_dir();
  std::error_code ec;
  std::filesystem::create_directories(dir, ec);
  REQUIRE_FALSE(ec);

  capture::storage::DiskWatchdog watchdog(dir);
  REQUIRE(watchdog.free_bytes() >= 0);

  std::filesystem::remove_all(dir, ec);
}

TEST_CASE("DiskWatchdog threshold transitions remain deterministic",
          "[storage][disk]") {
  capture::storage::DiskWatchdog watchdog(storage_test_dir());
  std::vector<std::string> levels;
  watchdog.set_alert_callback(
      [&](const std::string& level, const std::string&) { levels.push_back(level); });

  watchdog.set_free_bytes_override(30LL * 1024 * 1024 * 1024);
  watchdog.poll();
  watchdog.set_free_bytes_override(15LL * 1024 * 1024 * 1024);
  watchdog.poll();
  watchdog.set_free_bytes_override(5LL * 1024 * 1024 * 1024);
  watchdog.poll();
  watchdog.poll();

  const std::vector<std::string> expected{"warning", "critical", "hard_floor"};
  REQUIRE(levels == expected);
  REQUIRE(watchdog.at_hard_floor());

  watchdog.set_free_bytes_override(capture::storage::kDiskReserveBytes + 1);
  REQUIRE_FALSE(watchdog.at_hard_floor());
}
