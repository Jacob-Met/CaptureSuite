// SPDX-License-Identifier: GPL-3.0-only
#include <catch2/catch_test_macros.hpp>

#include "capture/session_fsm.hpp"

TEST_CASE("session happy path to finalized", "[session_fsm]") {
  capture::SessionFsm fsm;
  REQUIRE(fsm.state() == capture::SessionState::Idle);
  REQUIRE(fsm.apply(capture::SessionEvent::CreateSession).ok);
  REQUIRE(fsm.state() == capture::SessionState::Preparing);
  REQUIRE(fsm.apply(capture::SessionEvent::StartSelected).ok);
  REQUIRE(fsm.state() == capture::SessionState::Arming);
  REQUIRE(fsm.apply(capture::SessionEvent::ArmCompleteAll).ok);
  REQUIRE(fsm.state() == capture::SessionState::Recording);

  fsm.issue_stop_token("tok");
  REQUIRE(fsm.consume_stop_token("tok"));
  REQUIRE(fsm.apply(capture::SessionEvent::Stop).ok);
  REQUIRE(fsm.state() == capture::SessionState::Stopping);
  REQUIRE(fsm.apply(capture::SessionEvent::DrainComplete).ok);
  REQUIRE(fsm.state() == capture::SessionState::Finalized);
}

TEST_CASE("illegal session transitions rejected", "[session_fsm]") {
  capture::SessionFsm fsm;
  auto tr = fsm.apply(capture::SessionEvent::Stop);
  REQUIRE_FALSE(tr.ok);
  REQUIRE(tr.error_code == "INVALID_STATE");
  REQUIRE(fsm.state() == capture::SessionState::Idle);
}

TEST_CASE("arm timeout none returns to preparing", "[session_fsm]") {
  capture::SessionFsm fsm;
  REQUIRE(fsm.apply(capture::SessionEvent::CreateSession).ok);
  REQUIRE(fsm.apply(capture::SessionEvent::StartSelected).ok);
  REQUIRE(fsm.apply(capture::SessionEvent::ArmTimeoutNone).ok);
  REQUIRE(fsm.state() == capture::SessionState::Preparing);
}
