// SPDX-License-Identifier: GPL-3.0-only
#include "capture/session_fsm.hpp"

namespace capture {

std::string_view to_string(SessionState state) {
  switch (state) {
    case SessionState::Idle:
      return "IDLE";
    case SessionState::Preparing:
      return "PREPARING";
    case SessionState::Arming:
      return "ARMING";
    case SessionState::Recording:
      return "RECORDING";
    case SessionState::Stopping:
      return "STOPPING";
    case SessionState::Finalized:
      return "FINALIZED";
    case SessionState::Recovering:
      return "RECOVERING";
    case SessionState::Failed:
      return "FAILED";
  }
  return "UNKNOWN";
}

void SessionFsm::issue_stop_token(std::string token) {
  stop_token_ = std::move(token);
}

bool SessionFsm::consume_stop_token(std::string_view token) {
  if (!stop_token_ || *stop_token_ != token) {
    return false;
  }
  stop_token_.reset();
  return true;
}

TransitionResult SessionFsm::apply(SessionEvent event) {
  TransitionResult result;
  result.from = state_;
  result.to = state_;

  auto accept = [&](SessionState next) {
    state_ = next;
    result.ok = true;
    result.to = next;
    return result;
  };

  auto reject = [&](std::string_view msg) {
    result.ok = false;
    result.error_code = "INVALID_STATE";
    result.message = std::string(msg);
    return result;
  };

  if (event == SessionEvent::FatalError) {
    return accept(SessionState::Failed);
  }

  switch (state_) {
    case SessionState::Idle:
      if (event == SessionEvent::CreateSession) {
        return accept(SessionState::Preparing);
      }
      if (event == SessionEvent::OpenSessionFinalized) {
        return accept(SessionState::Idle);
      }
      if (event == SessionEvent::OpenSessionUnfinalized) {
        return accept(SessionState::Recovering);
      }
      break;

    case SessionState::Preparing:
      if (event == SessionEvent::StartSelected ||
          event == SessionEvent::StartAllReady) {
        return accept(SessionState::Arming);
      }
      if (event == SessionEvent::FinalizeSession) {
        return accept(SessionState::Finalized);
      }
      break;

    case SessionState::Arming:
      if (event == SessionEvent::ArmCompleteAll ||
          event == SessionEvent::ArmTimeoutSome) {
        return accept(SessionState::Recording);
      }
      if (event == SessionEvent::ArmTimeoutNone) {
        return accept(SessionState::Preparing);
      }
      break;

    case SessionState::Recording:
      if (event == SessionEvent::Stop) {
        return accept(SessionState::Stopping);
      }
      break;

    case SessionState::Stopping:
      if (event == SessionEvent::DrainComplete ||
          event == SessionEvent::DrainTimeout) {
        return accept(SessionState::Finalized);
      }
      break;

    case SessionState::Recovering:
      if (event == SessionEvent::RecoveryComplete) {
        return accept(SessionState::Finalized);
      }
      if (event == SessionEvent::RecoveryFailed) {
        return accept(SessionState::Failed);
      }
      break;

    case SessionState::Finalized:
    case SessionState::Failed:
      break;
  }

  return reject("illegal session transition");
}

}  // namespace capture
