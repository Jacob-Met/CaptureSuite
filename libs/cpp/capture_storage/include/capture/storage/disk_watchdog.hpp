// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <filesystem>
#include <functional>
#include <mutex>
#include <optional>
#include <string>

namespace capture::storage {

inline constexpr int64_t kDiskReserveBytes = 10LL * 1024 * 1024 * 1024;  // 10 GiB

class DiskWatchdog {
 public:
  using AlertFn = std::function<void(const std::string& level, const std::string& msg)>;

  explicit DiskWatchdog(std::filesystem::path volume_path);

  // Returns free bytes on the volume containing path. -1 on error.
  int64_t free_bytes() const;

  // true when free space is at or below the reserve (writers must block).
  bool at_hard_floor() const;

  // For tests: override free-bytes measurement.
  void set_free_bytes_override(std::optional<int64_t> bytes);

  void set_alert_callback(AlertFn fn);

  // Call periodically; emits level transitions.
  void poll();

 private:
  std::filesystem::path path_;
  AlertFn alert_;
  mutable std::mutex mu_;
  std::optional<int64_t> override_;
  std::string last_level_ = "info";
};

}  // namespace capture::storage
