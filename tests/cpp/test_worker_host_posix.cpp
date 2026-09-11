// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/worker_host.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cerrno>
#include <chrono>
#include <csignal>
#include <filesystem>
#include <string>
#include <thread>

namespace {

std::filesystem::path stub_exe() {
#ifdef CAPTURE_BINARY_DIR
  const auto candidate =
      std::filesystem::path(CAPTURE_BINARY_DIR) / "workers" / "stub" /
      "capture_worker_stub";
  if (std::filesystem::exists(candidate)) {
    return candidate;
  }
#endif
  return {};
}

bool process_is_gone(std::uint32_t pid) {
  for (int i = 0; i < 100; ++i) {
    errno = 0;
    if (kill(static_cast<pid_t>(pid), 0) != 0 && errno == ESRCH) {
      return true;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  return false;
}

}  // namespace

TEST_CASE("POSIX worker host spawns stub with Hello and Identify",
          "[worker_host][posix]") {
  const auto exe = stub_exe();
  REQUIRE_FALSE(exe.empty());
  REQUIRE(std::filesystem::exists(exe));

  capture::daemon::DaemonJob job;
  std::string error;
  REQUIRE(job.create(error));

  capture::daemon::WorkerHost host(job, "test-instance-worker-host-posix");
  capture::daemon::SpawnedWorker worker;
  REQUIRE(host.spawn(exe, "stub-posix-1", "stub.plugin", worker, error,
                     std::chrono::milliseconds(8000)));
  REQUIRE(worker.pid != 0);
  REQUIRE(worker.manifest.plugin_id() == "stub.plugin");
  REQUIRE(worker.manifest.sources_size() >= 1);
  REQUIRE(worker.manifest.sources(0).source_id() == "stub.source.1");
  const auto isolation = worker.manifest.capabilities().find("isolation");
  REQUIRE(isolation != worker.manifest.capabilities().end());
  REQUIRE(isolation->second == "per_source");

  host.stop(worker);
  REQUIRE(worker.pid == 0);
  REQUIRE(worker.pipe == nullptr);
  REQUIRE(worker.process == nullptr);
}

TEST_CASE("POSIX worker owner kills registered child on close",
          "[worker_host][posix]") {
  const auto exe = stub_exe();
  REQUIRE_FALSE(exe.empty());
  REQUIRE(std::filesystem::exists(exe));

  std::uint32_t pid = 0;
  {
    capture::daemon::DaemonJob job;
    std::string error;
    REQUIRE(job.create(error));
    capture::daemon::WorkerHost host(job, "test-instance-job-kill-posix");
    capture::daemon::SpawnedWorker worker;
    REQUIRE(host.spawn(exe, "stub-posix-kill", "stub.plugin", worker, error,
                       std::chrono::milliseconds(8000)));
    pid = worker.pid;
    REQUIRE(pid != 0);
    // Deliberately bypass WorkerHost::stop. DaemonJob still owns the pid and
    // must reap it during orderly daemon teardown.
    worker.process = nullptr;
    worker.pipe = nullptr;
  }

  REQUIRE(process_is_gone(pid));
}
