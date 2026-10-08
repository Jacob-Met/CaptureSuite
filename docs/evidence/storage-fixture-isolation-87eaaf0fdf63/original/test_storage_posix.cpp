// SPDX-License-Identifier: GPL-3.0-only
// Portable (non-Windows-specific) checks of the capture_storage primitives
// that have per-platform implementations.
#include <catch2/catch_test_macros.hpp>

#include "capture/storage/atomic_file.hpp"
#include "capture/storage/disk_watchdog.hpp"

#include <filesystem>
#include <string>

TEST_CASE("atomic_write_text replaces existing file and leaves no temp",
          "[storage][atomic]") {
  const auto root =
      std::filesystem::temp_directory_path() / "capturesuite_atomic_test";
  std::filesystem::remove_all(root);
  std::filesystem::create_directories(root);
  const auto path = root / "manifest.json";
  std::string err;
  REQUIRE(capture::storage::atomic_write_text(path, "first", err));
  REQUIRE(capture::storage::atomic_write_text(path, "second-longer", err));
  REQUIRE(capture::storage::read_text_file(path, err) == "second-longer");
  REQUIRE_FALSE(std::filesystem::exists(root / "manifest.json.tmp"));
  REQUIRE_FALSE(capture::storage::atomic_write_text(
      root / "missing-dir" / "x.json", "x", err));
  REQUIRE_FALSE(err.empty());
  std::filesystem::remove_all(root);
}

TEST_CASE("disk watchdog reports free bytes and honours override",
          "[storage][disk]") {
  capture::storage::DiskWatchdog wd(std::filesystem::temp_directory_path());
  REQUIRE(wd.free_bytes() > 0);
  wd.set_free_bytes_override(1024);
  REQUIRE(wd.free_bytes() == 1024);
  REQUIRE(wd.at_hard_floor());
  std::string level;
  wd.set_alert_callback([&](const std::string& l, const std::string&) { level = l; });
  wd.poll();
  REQUIRE(level == "hard_floor");
  wd.set_free_bytes_override(std::nullopt);
  REQUIRE_FALSE(wd.free_bytes() < 0);
}
