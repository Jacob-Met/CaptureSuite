// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/camera_worker_bridge.hpp"
#include "capture/env.hpp"
#include "capture_daemon/worker_host.hpp"
#include "capture/storage/session_package.hpp"

#include <catch2/catch_test_macros.hpp>

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <thread>

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

namespace {

std::filesystem::path stub_exe() {
#ifdef CAPTURE_BINARY_DIR
  const auto from_build =
      std::filesystem::path(CAPTURE_BINARY_DIR) / "workers" / "stub" /
      "capture_worker_stub.exe";
  if (std::filesystem::exists(from_build)) {
    return from_build;
  }
#endif
  wchar_t path[MAX_PATH]{};
  GetModuleFileNameW(nullptr, path, MAX_PATH);
  auto dir = std::filesystem::path(path).parent_path();
  auto candidate = dir / "capture_worker_stub.exe";
  if (std::filesystem::exists(candidate)) {
    return candidate;
  }
  return dir.parent_path().parent_path() / "workers" / "stub" /
         "capture_worker_stub.exe";
}

}  // namespace

TEST_CASE("worker host spawns stub with Hello and Identify", "[worker_host]") {
  const auto exe = stub_exe();
  REQUIRE(std::filesystem::exists(exe));

  capture::daemon::DaemonJob job;
  std::string err;
  REQUIRE(job.create(err));

  capture::daemon::WorkerHost host(job, "test-instance-worker-host");
  capture::daemon::SpawnedWorker worker;
  REQUIRE(host.spawn(exe, "stub-1", "stub.plugin", worker, err,
                     std::chrono::milliseconds(8000)));
  REQUIRE(worker.pid != 0);
  REQUIRE(worker.manifest.plugin_id() == "stub.plugin");
  REQUIRE(worker.manifest.sources_size() >= 1);
  REQUIRE(worker.manifest.sources(0).source_id() == "stub.source.1");
  const auto isolation = worker.manifest.capabilities().find("isolation");
  REQUIRE(isolation != worker.manifest.capabilities().end());
  REQUIRE(isolation->second == "per_source");

  host.stop(worker);
}

#if defined(CAPTURE_HAS_CAMERA_WORKER)
TEST_CASE("worker host spawns camera worker Identify", "[worker_host][camera]") {
  const auto exe = std::filesystem::path(CAPTURE_BINARY_DIR) / "workers" /
                     "camera" / "capture_worker_camera.exe";
  REQUIRE(std::filesystem::exists(exe));

  // Worker needs GStreamer DLLs on PATH.
  const auto gst = capture::env::get("GSTREAMER_1_0_ROOT_MSVC_X86_64");
  REQUIRE(gst.has_value());
  std::string path_env = *gst + "\\bin;";
  if (const auto old = capture::env::get("PATH")) {
    path_env += *old;
  }
  _putenv_s("PATH", path_env.c_str());

  capture::daemon::DaemonJob job;
  std::string err;
  REQUIRE(job.create(err));

  capture::daemon::WorkerHost host(job, "test-instance-camera-worker");
  capture::daemon::SpawnedWorker worker;
  REQUIRE(host.spawn(exe, "cam-1", "camera.gstreamer", worker, err,
                     std::chrono::milliseconds(15000)));
  REQUIRE(worker.manifest.plugin_id() == "camera.gstreamer");
  const auto isolation = worker.manifest.capabilities().find("isolation");
  REQUIRE(isolation != worker.manifest.capabilities().end());
  REQUIRE(isolation->second == "per_source");
  const auto stack = worker.manifest.capabilities().find("record_stack");
  REQUIRE(stack != worker.manifest.capabilities().end());
  REQUIRE(stack->second == "gstreamer");
  // Cameras are machine-dependent; zero devices is still a valid Identify.
  capture::v1::DiscoverReply discovered;
  REQUIRE(host.discover(worker, discovered, err));
  REQUIRE_FALSE(discovered.error().code().size() > 0);
  if (discovered.sources_size() > 0) {
    capture::v1::ConnectReply connected;
    REQUIRE(host.connect(worker, discovered.sources(0).source_id(), connected,
                         err, std::chrono::milliseconds(15000)));
    // Device may be busy (in use by another app); only require a typed reply.
    if (!connected.error().code().size()) {
      REQUIRE(connected.source().lifecycle_state() ==
              capture::v1::SOURCE_LIFECYCLE_CONNECTED);
      const auto caps = connected.source().metadata().find("negotiated_caps");
      REQUIRE(caps != connected.source().metadata().end());
      REQUIRE_FALSE(caps->second.empty());
    }
  }
  host.stop(worker);
}

TEST_CASE("camera worker start/stop with videotestsrc",
          "[worker_host][camera]") {
  const auto exe = std::filesystem::path(CAPTURE_BINARY_DIR) / "workers" /
                     "camera" / "capture_worker_camera.exe";
  REQUIRE(std::filesystem::exists(exe));

  const auto gst = capture::env::get("GSTREAMER_1_0_ROOT_MSVC_X86_64");
  REQUIRE(gst.has_value());
  std::string path_env = *gst + "\\bin;";
  if (const auto old = capture::env::get("PATH")) {
    path_env += *old;
  }
  _putenv_s("PATH", path_env.c_str());
  _putenv_s("CAPTURE_CAMERA_FAKE", "1");

  capture::daemon::DaemonJob job;
  std::string err;
  REQUIRE(job.create(err));
  capture::daemon::WorkerHost host(job, "test-instance-camera-fake");
  capture::daemon::SpawnedWorker worker;
  REQUIRE(host.spawn(exe, "cam-fake", "camera.gstreamer", worker, err,
                     std::chrono::milliseconds(15000)));

  const auto pkg = std::filesystem::temp_directory_path() /
                   "capturesuite_camera_fake" / "session.mmsession";
  std::filesystem::remove_all(pkg.parent_path());
  std::filesystem::create_directories(pkg);

  capture::v1::DiscoverReply discovered;
  REQUIRE(host.discover(worker, discovered, err));
  REQUIRE(discovered.sources_size() >= 1);
  const std::string source_id = [&] {
    for (const auto& s : discovered.sources()) {
      if (s.source_id() == "camera.fake") {
        return s.source_id();
      }
    }
    return discovered.sources(0).source_id();
  }();

  capture::v1::StartRequest start;
  start.set_source_id(source_id);
  start.set_session_id("fake-session");
  start.set_session_package_path(pkg.string());
  start.set_session_t0_qpc_ns(0);

  capture::v1::StartReply started;
  REQUIRE(host.start_capture(worker, start, started, err,
                             std::chrono::milliseconds(20000)));
  REQUIRE_FALSE(started.error().code().size() > 0);

  int previews = 0;
  int sealed = 0;
  const auto on_sealed = [&](const capture::v1::SegmentSealed&) { ++sealed; };
  const auto on_preview = [&](const capture::v1::PreviewFrame& f) {
    if (f.has_image() && !f.image().data().empty()) {
      ++previews;
    }
  };
  // Preview may race StartReply on the pipe; poll until frames arrive.
  for (int i = 0; i < 60 && previews < 1; ++i) {
    host.drain_events(worker, on_sealed, on_preview);
    if (previews < 1) {
      std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
  }

  capture::v1::StopReply stopped;
  REQUIRE(host.stop_capture(worker, source_id, stopped, err));
  REQUIRE_FALSE(stopped.error().code().size() > 0);
  for (int i = 0; i < 40 && sealed < 1; ++i) {
    host.drain_events(worker, on_sealed, on_preview);
    if (sealed < 1) {
      std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
  }
  REQUIRE(sealed >= 1);
  REQUIRE(previews >= 1);

  const auto segs =
      pkg / "sources" / source_id / "streams" / "video" / "segments";
  REQUIRE(std::filesystem::exists(segs));
  bool saw_mkv = false;
  for (const auto& ent : std::filesystem::directory_iterator(segs)) {
    if (ent.path().extension() == ".mkv") {
      saw_mkv = true;
      break;
    }
  }
  REQUIRE(saw_mkv);

  host.stop(worker);
  _putenv_s("CAPTURE_CAMERA_FAKE", "");
}

TEST_CASE("camera worker bridge seals into session package",
          "[worker_host][camera][bridge]") {
  const auto exe = std::filesystem::path(CAPTURE_BINARY_DIR) / "workers" /
                     "camera" / "capture_worker_camera.exe";
  REQUIRE(std::filesystem::exists(exe));

  const auto gst = capture::env::get("GSTREAMER_1_0_ROOT_MSVC_X86_64");
  REQUIRE(gst.has_value());
  std::string path_env = *gst + "\\bin;";
  if (const auto old = capture::env::get("PATH")) {
    path_env += *old;
  }
  _putenv_s("PATH", path_env.c_str());
  _putenv_s("CAPTURE_CAMERA_FAKE", "1");
  _putenv_s("CAPTURE_CAMERA_WORKER_EXE", exe.string().c_str());

  const auto parent = std::filesystem::temp_directory_path() /
                      "capturesuite_bridge_seal";
  std::filesystem::remove_all(parent);

  capture::storage::PackageOptions opts;
  opts.parent_dir = parent;
  opts.session_id = "bridge-seal";
  std::string err;
  capture::storage::SessionPackage package;
  REQUIRE(package.create(opts, err));

  std::vector<capture::storage::PackageStreamDesc> streams = {
      {"camera.fake", "camera.fake.video", "video", "Fake", "camera", 30.0}};
  REQUIRE(package.begin_recording(streams, 0, 10000000, "1970-01-01T00:00:00Z",
                                  0, err));

  capture::daemon::CameraWorkerBridge bridge("bridge-test");
  REQUIRE(bridge.spawn_for_source("camera.fake", err));

  capture::v1::StartRequest start;
  start.set_source_id("camera.fake");
  start.set_session_id("bridge-seal");
  start.set_session_package_path(package.root().string());
  start.set_session_t0_qpc_ns(0);
  REQUIRE(bridge.start_capture("camera.fake", start, err));

  int sealed = 0;
  for (int i = 0; i < 40; ++i) {
    bridge.poll(
        [&](const capture::v1::SegmentSealed& s) {
          capture::storage::SealedSegmentInfo info;
          info.relative_path = s.path();
          info.size_bytes = s.size_bytes();
          info.hash_blake3_hex = s.hash_blake3_hex();
          info.start_session_time_ns = s.start_session_time_ns();
          info.end_session_time_ns = s.end_session_time_ns();
          info.actual_count = s.actual_count();
          info.segment_index = static_cast<int>(s.segment_index());
          info.source_id = s.source_id();
          info.stream_id = s.stream_id();
          package.record_external_segment(info);
          ++sealed;
        });
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  REQUIRE(bridge.stop_capture("camera.fake", err));
  bridge.poll([&](const capture::v1::SegmentSealed& s) {
    capture::storage::SealedSegmentInfo info;
    info.relative_path = s.path();
    info.size_bytes = s.size_bytes();
    info.hash_blake3_hex = s.hash_blake3_hex();
    info.start_session_time_ns = s.start_session_time_ns();
    info.end_session_time_ns = s.end_session_time_ns();
    info.actual_count = s.actual_count();
    info.segment_index = static_cast<int>(s.segment_index());
    info.source_id = s.source_id();
    info.stream_id = s.stream_id();
    package.record_external_segment(info);
    ++sealed;
  });
  REQUIRE(sealed >= 1);
  REQUIRE(package.sealed_segment_count() >= 1);

  bridge.stop_all();
  _putenv_s("CAPTURE_CAMERA_FAKE", "");
  _putenv_s("CAPTURE_CAMERA_WORKER_EXE", "");
}
#endif

TEST_CASE("job object kills worker on close", "[worker_host]") {
  const auto exe = stub_exe();
  REQUIRE(std::filesystem::exists(exe));

  DWORD pid = 0;
  {
    capture::daemon::DaemonJob job;
    std::string err;
    REQUIRE(job.create(err));
    capture::daemon::WorkerHost host(job, "test-instance-job-kill");
    capture::daemon::SpawnedWorker worker;
    REQUIRE(host.spawn(exe, "stub-kill", "stub.plugin", worker, err,
                       std::chrono::milliseconds(8000)));
    pid = worker.pid;
    // Leak process/pipe handles into the OS; closing the job must still kill.
    worker.process = nullptr;
    worker.thread = nullptr;
    worker.pipe = nullptr;
  }

  HANDLE process = OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION,
                               FALSE, pid);
  REQUIRE(process != nullptr);
  const DWORD wait = WaitForSingleObject(process, 5000);
  CloseHandle(process);
  REQUIRE(wait == WAIT_OBJECT_0);
}
