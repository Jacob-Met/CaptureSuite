// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <string>
#include <string_view>

namespace capture {

enum class SourceLifecycle {
  Unavailable,
  Discovered,
  Connected,
  Pairing,
  Configured,
  Validated,
  Ready,
  Armed,
  Recording,
  Stopping,
  Finalized,
  Failed,
};

enum class SourceHealth {
  Ok,
  Warning,
  Error,
};

enum class SourceEvent {
  Discover,
  Connect,
  ConnectFail,
  Pair,
  PairComplete,
  ApplyConfig,
  Validate,
  MarkReady,
  Arm,
  Start,
  Stop,
  DrainComplete,
  DeviceLost,     // stays RECORDING, health ERROR
  Reconnected,    // stays RECORDING, health OK
  Unrecoverable,
};

struct SourceTransitionResult {
  bool ok = false;
  SourceLifecycle from = SourceLifecycle::Unavailable;
  SourceLifecycle to = SourceLifecycle::Unavailable;
  SourceHealth health = SourceHealth::Ok;
  bool open_disconnect_gap = false;
  bool close_gap = false;
  std::string error_code;
  std::string message;
};

std::string_view to_string(SourceLifecycle state);
std::string_view to_string(SourceHealth health);

class SourceFsm {
 public:
  SourceLifecycle lifecycle() const { return lifecycle_; }
  SourceHealth health() const { return health_; }
  bool selected() const { return selected_; }

  void set_selected(bool selected) { selected_ = selected; }

  SourceTransitionResult apply(SourceEvent event);

 private:
  SourceLifecycle lifecycle_ = SourceLifecycle::Unavailable;
  SourceHealth health_ = SourceHealth::Ok;
  bool selected_ = true;
};

}  // namespace capture
