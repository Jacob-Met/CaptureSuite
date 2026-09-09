// SPDX-License-Identifier: GPL-3.0-only
#include <catch2/catch_test_macros.hpp>

#include "capture_daemon/sim_engine.hpp"
#include "capture/env.hpp"

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <optional>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <objbase.h>
#endif

namespace {

struct ComInit {
  ComInit() {
#ifdef _WIN32
    CoInitializeEx(nullptr, COINIT_MULTITHREADED);
#endif
  }
  ~ComInit() {
#ifdef _WIN32
    CoUninitialize();
#endif
  }
};

struct ScopedEnv {
  std::string name;
  std::optional<std::string> old;

  ScopedEnv(std::string key, const char* value)
      : name(std::move(key)), old(capture::env::get(name.c_str())) {
#ifdef _WIN32
    _putenv_s(name.c_str(), value);
#else
    setenv(name.c_str(), value, 1);
#endif
  }
  ~ScopedEnv() {
#ifdef _WIN32
    _putenv_s(name.c_str(), old ? old->c_str() : "");
#else
    if (old) {
      setenv(name.c_str(), old->c_str(), 1);
    } else {
      unsetenv(name.c_str());
    }
#endif
  }
};

std::string first_video_source(const capture::daemon::SimEngine& engine) {
  for (const auto& src : engine.sources()) {
    if (src.modality == "video") {
      return src.source_id;
    }
  }
  return "sim.camera.sagittal";
}

}  // namespace


TEST_CASE("sim-only environment never exposes a physical camera source",
          "[sim_engine][isolation]") {
  ScopedEnv sim_only("CAPTURE_TEST_SIM_ONLY", "1");
  capture::daemon::SimEngine engine;
  bool saw_sim_camera = false;
  for (const auto& source : engine.sources()) {
    REQUIRE(source.source_type != "camera");
    if (source.source_id == "sim.camera.sagittal") {
      saw_sim_camera = true;
    }
  }
  REQUIRE(saw_sim_camera);
}

TEST_CASE("multi-family sim records together with fault isolation",
          "[sim_engine]") {
  ComInit com;
  const auto root =
      std::filesystem::temp_directory_path() / "capturesuite_m2_sim_test";
  std::filesystem::remove_all(root);
  std::filesystem::create_directories(root);

  capture::daemon::SimEngine engine;
  engine.set_package_parent(root);
  std::string err;

  const std::string video_id = first_video_source(engine);
  // Fault-isolation probe: prefer a non-camera sim source so sample counts
  // are deterministic even when a real webcam is slow to produce frames.
  const std::string fault_id = "sim.emg.main";

  REQUIRE(engine.create_session("m2-test", err));
  REQUIRE(engine.select_sources(
      {video_id, "sim.emg.main", "sim.imu.upper", "sim.radar.1",
       "sim.replay.demo"},
      err));
  REQUIRE(engine.start_selected(err));
  REQUIRE(engine.is_recording());

  std::this_thread::sleep_for(std::chrono::milliseconds(200));
  auto cp = engine.create_checkpoint("A", "test");
  REQUIRE_FALSE(cp.checkpoint_id.empty());
  engine.annotate("note", "test");
  engine.add_sync_anchor("clapper", "test");

  REQUIRE(engine.disconnect_source(fault_id, err));
  std::this_thread::sleep_for(std::chrono::milliseconds(80));

  auto mid = engine.recording_stats();
  REQUIRE(mid.total_samples > 0);
  bool others_live = false;
  for (const auto& s : mid.streams) {
    if (s.source_id == fault_id) {
      continue;
    }
    bool is_camera = false;
    for (const auto& src : engine.sources()) {
      if (src.source_id == s.source_id && src.is_camera) {
        is_camera = true;
        break;
      }
    }
    if (is_camera) {
      continue;
    }
    if (s.sample_count > 0) {
      others_live = true;
    }
  }
  REQUIRE(others_live);

  REQUIRE(engine.reconnect_source(fault_id, err));
  const auto token = engine.request_stop_token();
  REQUIRE(engine.stop(token, err));
  REQUIRE_FALSE(engine.is_recording());

  auto stats = engine.recording_stats();
  REQUIRE(stats.state == capture::SessionState::Finalized);
  REQUIRE(stats.checkpoint_count == 1);
  REQUIRE(stats.annotation_count == 1);
  REQUIRE(stats.sync_anchor_count == 1);
  REQUIRE(stats.streams.size() >= 4);

  bool fault_gap = false;
  for (const auto& s : stats.streams) {
    if (s.source_id == fault_id) {
      fault_gap = s.gap_count > 0;
    }
  }
  REQUIRE(fault_gap);
}

TEST_CASE("preview descriptors cover contract kinds", "[sim_engine][preview]") {
  ComInit com;
  capture::daemon::SimEngine engine;
  auto descs = engine.list_preview_descriptors({});
  REQUIRE(descs.size() >= 5);

  bool saw_image = false;
  bool saw_trace = false;
  bool saw_orient = false;
  bool saw_matrix = false;
  for (const auto& d : descs) {
    using capture::daemon::PreviewKind;
    if (d.kind == PreviewKind::ImageThumbnail) {
      saw_image = true;
    }
    if (d.kind == PreviewKind::TraceBlock || d.kind == PreviewKind::TraceSingle) {
      saw_trace = true;
    }
    if (d.kind == PreviewKind::Orientation) {
      saw_orient = true;
    }
    if (d.kind == PreviewKind::Matrix2D) {
      saw_matrix = true;
    }
  }
  REQUIRE(saw_image);
  REQUIRE(saw_trace);
  REQUIRE(saw_orient);
  REQUIRE(saw_matrix);
}

TEST_CASE("preflight and rehearsal against selected sim sources",
          "[sim_engine][preflight]") {
  ComInit com;
  const auto root =
      std::filesystem::temp_directory_path() / "capturesuite_m4_preflight";
  std::filesystem::remove_all(root);
  std::filesystem::create_directories(root);

  capture::daemon::SimEngine engine;
  engine.set_package_parent(root);
  std::string err;
  REQUIRE(engine.create_session("preflight-test", err));
  REQUIRE(engine.select_sources({"sim.emg.main", "sim.imu.upper"}, err));

  bool ok = false;
  auto checks = engine.run_preflight({}, ok, err);
  REQUIRE_FALSE(checks.empty());
  REQUIRE(ok);

  REQUIRE(engine.start_rehearsal({}, err));
  REQUIRE(engine.rehearsal_active());
  std::this_thread::sleep_for(std::chrono::milliseconds(120));
  auto frames = engine.take_preview_frames();
  REQUIRE_FALSE(frames.empty());
  REQUIRE(engine.stop_rehearsal(err));
}
