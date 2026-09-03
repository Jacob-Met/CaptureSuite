// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/control_server.hpp"
#include "capture_daemon/process_security.hpp"
#include "capture_daemon/sim_engine.hpp"

#include "capture/logging.hpp"
#include "capture/version.hpp"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <thread>
#include <vector>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <objbase.h>
#include <rpc.h>
#pragma comment(lib, "Rpcrt4.lib")
#pragma comment(lib, "ole32.lib")
#endif

namespace {

std::string make_instance_id() {
#ifdef _WIN32
  UUID uuid{};
  UuidCreate(&uuid);
  RPC_CSTR str = nullptr;
  if (UuidToStringA(&uuid, &str) == RPC_S_OK && str != nullptr) {
    std::string out(reinterpret_cast<char*>(str));
    RpcStringFreeA(&str);
    return out;
  }
#endif
  return "local-dev";
}

int run_self_test() {
  using capture::daemon::SimEngine;
  SimEngine engine;
  const auto root =
      std::filesystem::temp_directory_path() / "capturesuite_self_test";
  std::filesystem::remove_all(root);
  std::filesystem::create_directories(root);
  engine.set_package_parent(root);
  std::string err;

  if (!engine.create_session("self-test-session", err)) {
    std::fprintf(stderr, "create_session failed: %s\n", err.c_str());
    return 1;
  }
  std::string camera_id = "sim.camera.sagittal";
  for (const auto& src : engine.sources()) {
    if (src.modality == "video") {
      camera_id = src.source_id;
      break;
    }
  }
  const std::vector<std::string> selected = {
      camera_id, "sim.emg.main", "sim.imu.upper", "sim.radar.1",
      "sim.replay.demo"};
  if (!engine.select_sources(selected, err)) {
    std::fprintf(stderr, "select_sources failed: %s\n", err.c_str());
    return 1;
  }
  if (!engine.start_selected(err)) {
    std::fprintf(stderr, "start_selected failed: %s\n", err.c_str());
    return 1;
  }
  std::this_thread::sleep_for(std::chrono::milliseconds(250));
  engine.create_checkpoint("SelfTest", "self_test");
  engine.annotate("marker", "self_test");
  engine.add_sync_anchor("clapper", "self_test");

  if (!engine.disconnect_source("sim.emg.main", err)) {
    std::fprintf(stderr, "disconnect failed: %s\n", err.c_str());
    return 1;
  }
  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  // Other modalities must keep recording while EMG is disconnected.
  // Real cameras may need longer to produce the first frame (or be denied);
  // only require simulated streams here.
  auto mid = engine.recording_stats();
  for (const auto& s : mid.streams) {
    if (s.source_id == "sim.emg.main") {
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
    if (s.sample_count <= 0) {
      std::fprintf(stderr, "expected samples on %s during EMG disconnect\n",
                   s.source_id.c_str());
      return 1;
    }
  }

  if (!engine.reconnect_source("sim.emg.main", err)) {
    std::fprintf(stderr, "reconnect failed: %s\n", err.c_str());
    return 1;
  }
  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  const auto token = engine.request_stop_token();
  if (!engine.stop(token, err)) {
    std::fprintf(stderr, "stop failed: %s\n", err.c_str());
    return 1;
  }

  const auto stats = engine.recording_stats();
  if (stats.total_samples < 100) {
    std::fprintf(stderr, "too few samples: %lld\n",
                 static_cast<long long>(stats.total_samples));
    return 1;
  }
  if (stats.checkpoint_count < 1 || stats.annotation_count < 1 ||
      stats.sync_anchor_count < 1) {
    std::fprintf(stderr, "missing timeline events\n");
    return 1;
  }
  bool saw_gap = false;
  for (const auto& s : stats.streams) {
    if (s.source_id == "sim.emg.main" && s.gap_count > 0) {
      saw_gap = true;
    }
  }
  if (!saw_gap) {
    std::fprintf(stderr, "expected DISCONNECT gap on EMG\n");
    return 1;
  }

  std::printf("capture_daemon self-test OK — samples=%lld streams=%zu\n",
              static_cast<long long>(stats.total_samples),
              stats.streams.size());
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
#ifdef _WIN32
  CoInitializeEx(nullptr, COINIT_MULTITHREADED);
#endif
  {
    capture::log::Options opts;
    opts.component = "daemon";
    opts.also_stderr = true;
    capture::log::init(opts);
  }
  for (int i = 1; i < argc; ++i) {
    if (std::strcmp(argv[i], "--self-test") == 0) {
      const int rc = run_self_test();
      capture::log::shutdown();
      return rc;
    }
  }

  const std::string instance_id = make_instance_id();
  // Single-segment pipe name (nested backslashes are fragile for some clients).
  const std::string pipe_name =
      "\\\\.\\pipe\\capturesuite." + instance_id + ".control";

  capture::daemon::DaemonJob job;
  std::string err;
  if (!job.create(err)) {
    capture::log::error("job_object_failed", err);
    capture::log::shutdown();
    return 1;
  }

  capture::daemon::SimEngine engine;
  capture::daemon::ControlServer server(engine, instance_id, pipe_name);

  if (!capture::daemon::write_instance_file(instance_id, pipe_name, err)) {
    capture::log::warn("instance_file", err);
  }
  if (!server.start(err)) {
    capture::log::error("control_server_start_failed", err);
    capture::log::shutdown();
    return 1;
  }

  capture::log::info("daemon_started", "control server listening",
                     {{"instance_id", instance_id},
                      {"pipe", pipe_name},
                      {"version", capture::version_string()},
                      {"source_count", std::to_string(engine.sources().size())}});
  std::printf("capture_daemon %s\n", capture::version_string());
  std::printf("instance_id=%s\n", instance_id.c_str());
  std::printf("control_pipe=%s\n", pipe_name.c_str());
  std::printf("sources=%zu (Milestone 4)\n", engine.sources().size());
  std::fflush(stdout);

  // Run until Ctrl+C / process kill.
  while (true) {
    std::this_thread::sleep_for(std::chrono::seconds(1));
  }
}
