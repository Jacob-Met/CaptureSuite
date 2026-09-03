// SPDX-License-Identifier: GPL-3.0-only
#include <catch2/catch_test_macros.hpp>

#include "capture/clock.hpp"

#include <chrono>
#include <thread>

TEST_CASE("SessionClock QPC frequency is positive", "[clock]") {
  capture::SessionClock clock;
  REQUIRE(clock.qpc_frequency() > 0);
  REQUIRE(clock.now_qpc() > 0);
}

TEST_CASE("SessionClock establish_t0 and session time advances", "[clock]") {
  capture::SessionClock clock;
  auto t0 = clock.establish_t0();
  REQUIRE(t0.qpc_frequency > 0);
  REQUIRE(t0.uncertainty_ns >= 0);
  REQUIRE_FALSE(t0.wall.iso_utc.empty());

  const int64_t a = clock.session_now_ns();
  std::this_thread::sleep_for(std::chrono::milliseconds(5));
  const int64_t b = clock.session_now_ns();
  REQUIRE(b > a);
}

TEST_CASE("qpc_delta_to_ns round-trip sanity", "[clock]") {
  capture::SessionClock clock;
  const int64_t freq = clock.qpc_frequency();
  const int64_t one_sec = capture::SessionClock::qpc_delta_to_ns(freq, freq);
  REQUIRE(one_sec == 1'000'000'000);
}
