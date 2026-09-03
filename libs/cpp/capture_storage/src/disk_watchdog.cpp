// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/disk_watchdog.hpp"

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

namespace capture::storage {

DiskWatchdog::DiskWatchdog(std::filesystem::path volume_path)
    : path_(std::move(volume_path)) {}

int64_t DiskWatchdog::free_bytes() const {
  {
    std::lock_guard lock(mu_);
    if (override_) {
      return *override_;
    }
  }
  ULARGE_INTEGER free_bytes_available{};
  if (!GetDiskFreeSpaceExW(path_.wstring().c_str(), &free_bytes_available,
                           nullptr, nullptr)) {
    return -1;
  }
  return static_cast<int64_t>(free_bytes_available.QuadPart);
}

bool DiskWatchdog::at_hard_floor() const {
  const int64_t free = free_bytes();
  if (free < 0) {
    return false;
  }
  return free <= kDiskReserveBytes;
}

void DiskWatchdog::set_free_bytes_override(std::optional<int64_t> bytes) {
  std::lock_guard lock(mu_);
  override_ = bytes;
}

void DiskWatchdog::set_alert_callback(AlertFn fn) { alert_ = std::move(fn); }

void DiskWatchdog::poll() {
  const int64_t free = free_bytes();
  if (free < 0) {
    return;
  }
  std::string level = "info";
  if (free <= kDiskReserveBytes) {
    level = "hard_floor";
  } else {
    // Rough estimate without throughput: treat < 20 GiB as critical, < 40 as warning.
    if (free < 20LL * 1024 * 1024 * 1024) {
      level = "critical";
    } else if (free < 40LL * 1024 * 1024 * 1024) {
      level = "warning";
    }
  }
  if (level != last_level_ && alert_) {
    alert_(level, "free_bytes=" + std::to_string(free));
  }
  last_level_ = level;
}

}  // namespace capture::storage
