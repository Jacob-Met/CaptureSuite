// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <optional>
#include <string>
#include <string_view>

namespace capture {

enum class SessionState {
  Idle,
  Preparing,
  Arming,
  Recording,
  Stopping,
  Finalized,
  Recovering,
  Failed,
};

enum class SessionEvent {
  CreateSession,
  OpenSessionFinalized,
  OpenSessionUnfinalized,
  StartSelected,
  StartAllReady,
  FinalizeSession,
  ArmCompleteAll,
  ArmTimeoutSome,
  ArmTimeoutNone,
  Stop,
  DrainComplete,
  DrainTimeout,
  RecoveryComplete,
  RecoveryFailed,
  FatalError,
};

struct TransitionResult {
  bool ok = false;
  SessionState from = SessionState::Idle;
  SessionState to = SessionState::Idle;
  std::string error_code;  // INVALID_STATE when rejected
  std::string message;
};

std::string_view to_string(SessionState state);

class SessionFsm {
 public:
  SessionState state() const { return state_; }

  TransitionResult apply(SessionEvent event);

  // Stop requires a prior RequestStop token.
  void issue_stop_token(std::string token);
  bool consume_stop_token(std::string_view token);
  bool has_stop_token() const { return stop_token_.has_value(); }

 private:
  SessionState state_ = SessionState::Idle;
  std::optional<std::string> stop_token_;
};

}  // namespace capture
