// SPDX-License-Identifier: GPL-3.0-only
#include "capture/clock.hpp"

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

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
  const __int128 num = static_cast<__int128>(delta_ticks) * 1000000000;
  return static_cast<int64_t>(num / frequency);
#endif
}

int64_t SessionClock::now_monotonic_ns() const {
  return qpc_delta_to_ns(now_qpc() - process_start_qpc_, frequency_);
}

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
