// SPDX-License-Identifier: GPL-3.0-only
#include <catch2/catch_test_macros.hpp>

#include "capture/source_fsm.hpp"

TEST_CASE("source path to ready and record", "[source_fsm]") {
  capture::SourceFsm fsm;
  REQUIRE(fsm.apply(capture::SourceEvent::Discover).ok);
  REQUIRE(fsm.apply(capture::SourceEvent::Connect).ok);
  REQUIRE(fsm.apply(capture::SourceEvent::ApplyConfig).ok);
  REQUIRE(fsm.apply(capture::SourceEvent::Validate).ok);
  REQUIRE(fsm.apply(capture::SourceEvent::MarkReady).ok);
  REQUIRE(fsm.lifecycle() == capture::SourceLifecycle::Ready);
  REQUIRE(fsm.apply(capture::SourceEvent::Arm).ok);
  REQUIRE(fsm.apply(capture::SourceEvent::Start).ok);
  REQUIRE(fsm.lifecycle() == capture::SourceLifecycle::Recording);
}

TEST_CASE("disconnect during recording stays recording with error",
          "[source_fsm]") {
  capture::SourceFsm fsm;
  REQUIRE(fsm.apply(capture::SourceEvent::Discover).ok);
  REQUIRE(fsm.apply(capture::SourceEvent::Connect).ok);
  REQUIRE(fsm.apply(capture::SourceEvent::ApplyConfig).ok);
  REQUIRE(fsm.apply(capture::SourceEvent::Validate).ok);
  REQUIRE(fsm.apply(capture::SourceEvent::MarkReady).ok);
  REQUIRE(fsm.apply(capture::SourceEvent::Arm).ok);
  REQUIRE(fsm.apply(capture::SourceEvent::Start).ok);

  auto tr = fsm.apply(capture::SourceEvent::DeviceLost);
  REQUIRE(tr.ok);
  REQUIRE(tr.open_disconnect_gap);
  REQUIRE(fsm.lifecycle() == capture::SourceLifecycle::Recording);
  REQUIRE(fsm.health() == capture::SourceHealth::Error);

  auto back = fsm.apply(capture::SourceEvent::Reconnected);
  REQUIRE(back.ok);
  REQUIRE(back.close_gap);
  REQUIRE(fsm.health() == capture::SourceHealth::Ok);
  REQUIRE(fsm.lifecycle() == capture::SourceLifecycle::Recording);
}
