// SPDX-License-Identifier: GPL-3.0-only
#include "capture/env.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdlib>
#include <string>

TEST_CASE("environment helper preserves values and absence", "[env]") {
  constexpr const char* key = "CAPTURE_TEST_ENV_HELPER";
#ifdef _WIN32
  REQUIRE(_putenv_s(key, "alpha") == 0);
#else
  REQUIRE(setenv(key, "alpha", 1) == 0);
#endif
  const auto present = capture::env::get(key);
  REQUIRE(present.has_value());
  REQUIRE(*present == "alpha");
  REQUIRE(capture::env::enabled(key));

#ifdef _WIN32
  REQUIRE(_putenv_s(key, "0") == 0);
#else
  REQUIRE(setenv(key, "0", 1) == 0);
#endif
  REQUIRE_FALSE(capture::env::enabled(key));

#ifdef _WIN32
  REQUIRE(_putenv_s(key, "") == 0);
#else
  REQUIRE(unsetenv(key) == 0);
#endif
  REQUIRE_FALSE(capture::env::get(key).has_value());
}
