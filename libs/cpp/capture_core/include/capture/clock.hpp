// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <optional>
#include <string>

namespace capture {

struct WallAnchor {
  // FILETIME-compatible 100ns intervals since 1601 UTC, for provenance only.
  // This stays stable across platforms because the serialized session schema
  // predates the macOS port and already names this field as FILETIME-derived.
  uint64_t filetime_utc = 0;
  std::string iso_utc;
};

struct T0 {
  // qpc_* field names are retained for session/wire compatibility. On Windows
  // they are native QPC ticks/frequency; on POSIX they are monotonic ticks with
  // an explicit positive frequency supplied by SessionClock.
  int64_t qpc_ticks = 0;
  int64_t qpc_frequency = 0;
  int64_t uncertainty_ns = 0;
  WallAnchor wall;
};

// Monotonic session clock. Windows uses QueryPerformanceCounter. POSIX/macOS
// uses std::chrono::steady_clock exposed as nanosecond ticks at 1 GHz. Session
// time is never derived from wall clock.
class SessionClock {
 public:
  SessionClock();

  int64_t qpc_frequency() const { return frequency_; }
  int64_t now_qpc() const;
  // Nanoseconds since this SessionClock instance was created (monotonic).
  int64_t now_monotonic_ns() const;

  bool has_t0() const { return t0_.has_value(); }
  const T0& t0() const { return *t0_; }

  // Establish T0 with an interleaved monotonic/wall triple. Returns uncertainty_ns.
  T0 establish_t0();

  // Session nanoseconds since T0. Requires establish_t0().
  int64_t session_now_ns() const;
  int64_t qpc_to_session_ns(int64_t qpc_ticks) const;

  void clear_t0();

  static WallAnchor read_wall_utc();
  static int64_t qpc_delta_to_ns(int64_t delta_ticks, int64_t frequency);

 private:
  int64_t frequency_ = 0;
  int64_t process_start_qpc_ = 0;
  std::optional<T0> t0_;
};

}  // namespace capture
