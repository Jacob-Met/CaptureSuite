// SPDX-License-Identifier: GPL-3.0-only
#include "capture/env.hpp"

int main() {
  const auto value = capture::env::get("CAPTURE_ENV_HELPER_PROBE");
  return capture::env::enabled("CAPTURE_ENV_HELPER_PROBE") || value.has_value() ? 0 : 0;
}
