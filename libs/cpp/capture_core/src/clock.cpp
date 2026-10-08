// SPDX-License-Identifier: GPL-3.0-only
#include "capture/clock.hpp"

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#else
#include <chrono>
#include <ctime>
#endif

#include <algorithm>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <utility>

#if defined(_MSC_VER)
#include <intrin.h>
#endif

namespace capture {
namespace {

#ifdef _WIN32
int64_t query_frequency() {
  LARGE_INTEGER freq{};
  if (!QueryPerformanceFrequency(&freq) || freq.QuadPart <= 0) {
    throw std::runtime_error("QueryPerformanceFrequency failed");
  }
  return static_cast<int64_t>(freq.QuadPart);
}

int64_t query_counter() {
  LARGE_INTEGER counter{};
  if (!QueryPerformanceCounter(&counter)) {
    throw std::runtime_error("QueryPerformanceCounter failed");
  }
  return static_cast<int64_t>(counter.QuadPart);
}

#else
// Convert the native steady clock to nanosecond ticks; "QPC" frequency is 1e9.
int64_t query_frequency() { return 1000000000LL; }

int64_t query_counter() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
             std::chrono::steady_clock::now().time_since_epoch())
      .count();
}
#endif

}  // namespace

SessionClock::SessionClock()
    : frequency_(query_frequency()), process_start_qpc_(query_counter()) {}

int64_t SessionClock::now_qpc() const { return query_counter(); }

int64_t SessionClock::qpc_delta_to_ns(int64_t delta_ticks, int64_t frequency) {
  if (frequency <= 0) {
    throw std::invalid_argument("invalid QPC frequency");
  }
#if defined(_MSC_VER)
  // signed 128-bit style multiply then divide.
  const bool negative = delta_ticks < 0;
  const uint64_t abs_delta =
      negative ? static_cast<uint64_t>(-delta_ticks) : static_cast<uint64_t>(delta_ticks);
  uint64_t high = 0;
  const uint64_t low = _umul128(abs_delta, 1000000000ULL, &high);
  // Divide 128-bit (high:low) by frequency.
  uint64_t remainder = 0;
  uint64_t quotient_high = 0;
  if (high != 0) {
    quotient_high = high / static_cast<uint64_t>(frequency);
    remainder = high % static_cast<uint64_t>(frequency);
  }
  // (remainder << 64 | low) / frequency — use _udiv128 when available.
  uint64_t quotient_low = 0;
#if defined(_UDIV128) || defined(_MSC_VER)
  quotient_low = _udiv128(remainder, low, static_cast<uint64_t>(frequency), &remainder);
#else
  // Fallback: long double (still fine for QPC ranges).
  const long double num =
      static_cast<long double>(delta_ticks) * 1000000000.0L;
  return static_cast<int64_t>(num / static_cast<long double>(frequency));
#endif
  (void)quotient_high;  // expected 0 for session-length intervals
  const int64_t result = static_cast<int64_t>(quotient_low);
  return negative ? -result : result;
#else
  // GCC/Clang's wide integer keeps the multiply exact. Mark this deliberate
  // extension locally so the rest of the target retains -Wpedantic/-Werror.
  __extension__ using WideTicks = __int128;
  const WideTicks num = static_cast<WideTicks>(delta_ticks) * 1000000000;
  return static_cast<int64_t>(num / frequency);
#endif
}

int64_t SessionClock::now_monotonic_ns() const {
  return qpc_delta_to_ns(now_qpc() - process_start_qpc_, frequency_);
}

#ifdef _WIN32
WallAnchor SessionClock::read_wall_utc() {
  FILETIME ft{};
  GetSystemTimePreciseAsFileTime(&ft);
  ULARGE_INTEGER uli{};
  uli.LowPart = ft.dwLowDateTime;
  uli.HighPart = ft.dwHighDateTime;

  SYSTEMTIME st{};
  FileTimeToSystemTime(&ft, &st);
  std::ostringstream oss;
  oss << std::setfill('0') << std::setw(4) << st.wYear << '-' << std::setw(2)
      << st.wMonth << '-' << std::setw(2) << st.wDay << 'T' << std::setw(2)
      << st.wHour << ':' << std::setw(2) << st.wMinute << ':' << std::setw(2)
      << st.wSecond << '.' << std::setw(3) << st.wMilliseconds << 'Z';

  WallAnchor anchor;
  anchor.filetime_utc = uli.QuadPart;
  anchor.iso_utc = oss.str();
  return anchor;
}

#else
WallAnchor SessionClock::read_wall_utc() {
  using namespace std::chrono;
  const auto now = system_clock::now();
  const auto ns = duration_cast<nanoseconds>(now.time_since_epoch()).count();
  const std::time_t secs = static_cast<std::time_t>(ns / 1000000000LL);
  const int ms = static_cast<int>((ns / 1000000LL) % 1000);
  std::tm tm{};
  gmtime_r(&secs, &tm);
  std::ostringstream oss;
  oss << std::setfill('0') << std::setw(4) << (tm.tm_year + 1900) << '-'
      << std::setw(2) << (tm.tm_mon + 1) << '-' << std::setw(2) << tm.tm_mday
      << 'T' << std::setw(2) << tm.tm_hour << ':' << std::setw(2) << tm.tm_min
      << ':' << std::setw(2) << tm.tm_sec << '.' << std::setw(3) << ms << 'Z';
  WallAnchor anchor;
  // FILETIME epoch (1601) is 11644473600 s before the Unix epoch.
  anchor.filetime_utc = static_cast<uint64_t>(ns / 100) + 116444736000000000ULL;
  anchor.iso_utc = oss.str();
  return anchor;
}

#endif

T0 SessionClock::establish_t0() {
  const int64_t q0 = now_qpc();
  (void)read_wall_utc();
  const int64_t q1 = now_qpc();
  const WallAnchor w1 = read_wall_utc();
  const int64_t q2 = now_qpc();
  (void)read_wall_utc();

  int64_t qs[3] = {q0, q1, q2};
  std::sort(std::begin(qs), std::end(qs));
  const int64_t median_qpc = qs[1];
  const int64_t uncertainty = qpc_delta_to_ns(qs[2] - qs[0], frequency_) / 2;

  T0 t0;
  t0.qpc_ticks = median_qpc;
  t0.qpc_frequency = frequency_;
  t0.uncertainty_ns = uncertainty;
  t0.wall = w1;
  t0_ = t0;
  return t0;
}

int64_t SessionClock::session_now_ns() const {
  if (!t0_) {
    throw std::logic_error("session_now_ns called before establish_t0");
  }
  return qpc_to_session_ns(now_qpc());
}

int64_t SessionClock::qpc_to_session_ns(int64_t qpc_ticks) const {
  if (!t0_) {
    throw std::logic_error("qpc_to_session_ns called before establish_t0");
  }
  return qpc_delta_to_ns(qpc_ticks - t0_->qpc_ticks, frequency_);
}

void SessionClock::clear_t0() { t0_.reset(); }

}  // namespace capture
