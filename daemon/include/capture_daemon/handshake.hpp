// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "capture/v1/common.pb.h"

#include <string>

namespace capture::daemon {

inline constexpr int kProtocolMajor = 1;
inline constexpr int kProtocolMinor = 5;

capture::v1::HelloAck negotiate_hello(const capture::v1::Hello& hello,
                                      const std::string& instance_id);

}  // namespace capture::daemon
