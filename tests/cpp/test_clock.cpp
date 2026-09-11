// SPDX-License-Identifier: GPL-3.0-only
#include <catch2/catch_test_macros.hpp>

#include "capture/clock.hpp"

#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <thread>

namespace {
constexpr uint64_t kUnixEpochFiletime100ns = 116444736000000000ULL;
}

TEST_CASE("SessionClock monotonic frequency is positive", "[clock]") {
  capture::SessionClock clock;
  REQUIRE(clock.qpc_frequency() > 0);
  REQUIRE(clock.now_qpc() > 0);
}

TEST_CASE("SessionClock process-relative monotonic time advances", "[clock]") {
  capture::SessionClock clock;
  const int64_t a = clock.now_monotonic_ns();
  std::this_thread::sleep_for(std::chrono::milliseconds(2));
  const int64_t b = clock.now_monotonic_ns();
  REQUIRE(a >= 0);
  REQUIRE(b > a);
}

TEST_CASE("SessionClock establish_t0 and session time advances", "[clock]") {
  capture::SessionClock clock;
  auto t0 = clock.establish_t0();
  REQUIRE(t0.qpc_frequency > 0);
  REQUIRE(t0.uncertainty_ns >= 0);
  REQUIRE_FALSE(t0.wall.iso_utc.empty());
  REQUIRE(t0.wall.iso_utc.find('T') != std::string::npos);
  REQUIRE(t0.wall.iso_utc.back() == 'Z');
  REQUIRE(t0.wall.filetime_utc > kUnixEpochFiletime100ns);

  const int64_t a = clock.session_now_ns();
  std::this_thread::sleep_for(std::chrono::milliseconds(5));
  const int64_t b = clock.session_now_ns();
  REQUIRE(b > a);
}

TEST_CASE("qpc_delta_to_ns signed round-trip sanity", "[clock]") {
  capture::SessionClock clock;
  const int64_t freq = clock.qpc_frequency();
  REQUIRE(capture::SessionClock::qpc_delta_to_ns(freq, freq) == 1'000'000'000);
  REQUIRE(capture::SessionClock::qpc_delta_to_ns(-freq, freq) == -1'000'000'000);
  REQUIRE(capture::SessionClock::qpc_delta_to_ns(0, freq) == 0);
  REQUIRE_THROWS_AS(capture::SessionClock::qpc_delta_to_ns(1, 0),
                    std::invalid_argument);
}
