// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdlib>
#include <optional>
#include <string>

namespace capture::env {

inline std::optional<std::string> get(const char* name) {
#ifdef _WIN32
  char* value = nullptr;
  size_t length = 0;
  if (_dupenv_s(&value, &length, name) != 0 || value == nullptr) {
    return std::nullopt;
  }
  std::string out(value);
  free(value);
  return out;
#else
  const char* value = std::getenv(name);
  return value == nullptr ? std::nullopt
                          : std::optional<std::string>(std::string(value));
#endif
}

inline bool enabled(const char* name) {
  const auto value = get(name);
  return value.has_value() && !value->empty() && value->front() != '0';
}

}  // namespace capture::env
