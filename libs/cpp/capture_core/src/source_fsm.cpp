// SPDX-License-Identifier: GPL-3.0-only
#include "capture/source_fsm.hpp"

namespace capture {

std::string_view to_string(SourceLifecycle state) {
  switch (state) {
    case SourceLifecycle::Unavailable:
      return "UNAVAILABLE";
    case SourceLifecycle::Discovered:
      return "DISCOVERED";
    case SourceLifecycle::Connected:
      return "CONNECTED";
    case SourceLifecycle::Pairing:
      return "PAIRING";
    case SourceLifecycle::Configured:
      return "CONFIGURED";
    case SourceLifecycle::Validated:
      return "VALIDATED";
    case SourceLifecycle::Ready:
      return "READY";
    case SourceLifecycle::Armed:
      return "ARMED";
    case SourceLifecycle::Recording:
      return "RECORDING";
    case SourceLifecycle::Stopping:
      return "STOPPING";
    case SourceLifecycle::Finalized:
      return "FINALIZED";
    case SourceLifecycle::Failed:
      return "FAILED";
  }
  return "UNKNOWN";
}

std::string_view to_string(SourceHealth health) {
  switch (health) {
    case SourceHealth::Ok:
      return "OK";
    case SourceHealth::Warning:
      return "WARNING";
    case SourceHealth::Error:
      return "ERROR";
  }
  return "UNKNOWN";
}

SourceTransitionResult SourceFsm::apply(SourceEvent event) {
  SourceTransitionResult result;
  result.from = lifecycle_;
  result.to = lifecycle_;
  result.health = health_;

  auto accept = [&](SourceLifecycle next) {
    lifecycle_ = next;
    result.ok = true;
    result.to = next;
    result.health = health_;
    return result;
  };

  auto reject = [&](std::string_view msg) {
    result.ok = false;
    result.error_code = "INVALID_STATE";
    result.message = std::string(msg);
    return result;
  };

  if (event == SourceEvent::Unrecoverable) {
    health_ = SourceHealth::Error;
    return accept(SourceLifecycle::Failed);
  }

  // Disconnect during recording: stay RECORDING, mark ERROR + gap.
  if (event == SourceEvent::DeviceLost &&
      lifecycle_ == SourceLifecycle::Recording) {
    health_ = SourceHealth::Error;
    result.ok = true;
    result.open_disconnect_gap = true;
    result.health = health_;
    return result;
  }

  if (event == SourceEvent::Reconnected &&
      lifecycle_ == SourceLifecycle::Recording) {
    health_ = SourceHealth::Ok;
    result.ok = true;
    result.close_gap = true;
    result.health = health_;
    return result;
  }

  switch (lifecycle_) {
    case SourceLifecycle::Unavailable:
      if (event == SourceEvent::Discover) {
        return accept(SourceLifecycle::Discovered);
      }
      break;
    case SourceLifecycle::Discovered:
      if (event == SourceEvent::Connect) {
        return accept(SourceLifecycle::Connected);
      }
      if (event == SourceEvent::ConnectFail) {
        health_ = SourceHealth::Error;
        return accept(SourceLifecycle::Failed);
      }
      break;
    case SourceLifecycle::Connected:
      if (event == SourceEvent::Pair) {
        return accept(SourceLifecycle::Pairing);
      }
      if (event == SourceEvent::ApplyConfig) {
        return accept(SourceLifecycle::Configured);
      }
      break;
    case SourceLifecycle::Pairing:
      if (event == SourceEvent::PairComplete) {
        return accept(SourceLifecycle::Connected);
      }
      break;
    case SourceLifecycle::Configured:
      if (event == SourceEvent::Validate) {
        return accept(SourceLifecycle::Validated);
      }
      break;
    case SourceLifecycle::Validated:
      if (event == SourceEvent::MarkReady) {
        return accept(SourceLifecycle::Ready);
      }
      break;
    case SourceLifecycle::Ready:
      if (event == SourceEvent::Arm) {
        return accept(SourceLifecycle::Armed);
      }
      // Sources without arming may start directly.
      if (event == SourceEvent::Start) {
        return accept(SourceLifecycle::Recording);
      }
      break;
    case SourceLifecycle::Armed:
      if (event == SourceEvent::Start) {
        return accept(SourceLifecycle::Recording);
      }
      break;
    case SourceLifecycle::Recording:
      if (event == SourceEvent::Stop) {
        return accept(SourceLifecycle::Stopping);
      }
      break;
    case SourceLifecycle::Stopping:
      if (event == SourceEvent::DrainComplete) {
        return accept(SourceLifecycle::Finalized);
      }
      break;
    case SourceLifecycle::Finalized:
    case SourceLifecycle::Failed:
      break;
  }

  return reject("illegal source transition");
}

}  // namespace capture
