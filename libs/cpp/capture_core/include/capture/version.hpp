// SPDX-License-Identifier: GPL-3.0-only
#pragma once

namespace capture {

constexpr int kVersionMajor = 0;
constexpr int kVersionMinor = 1;
constexpr int kVersionPatch = 0;

const char* version_string() noexcept;

}  // namespace capture
