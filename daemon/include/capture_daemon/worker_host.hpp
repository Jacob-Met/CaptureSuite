// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "capture_daemon/process_security.hpp"

#include "capture/framing.hpp"
#include "capture/v1/health.pb.h"
#include "capture/v1/preview.pb.h"
#include "capture/v1/source.pb.h"
#include "capture/v1/worker.pb.h"

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

namespace capture::daemon {

struct SpawnedWorker {
  std::string worker_id;
  std::string plugin_id;
  std::string pipe_name;
  std::uint32_t pid = 0;
  void* process = nullptr;  // HANDLE
  void* thread = nullptr;   // primary thread HANDLE
  void* pipe = nullptr;     // connected worker pipe HANDLE
  capture::v1::SourceManifest manifest;
  // Serialises pipe reads and decoder access. An RPC and the event drain both
  // consume frames from the same pipe; without this the drain can swallow an
  // RPC reply, which the caller then waits out to its full timeout. Held by
  // pointer so SpawnedWorker stays movable.
  std::unique_ptr<std::mutex> io_mutex = std::make_unique<std::mutex>();
  // Retained across reads so coalesced RPC replies + events are not dropped.
  capture::FrameDecoder decoder;
  std::vector<capture::v1::PreviewFrame> pending_previews;
  std::vector<capture::v1::SegmentSealed> pending_sealed;
  std::vector<capture::v1::HealthSnapshot> pending_health;
  std::vector<capture::v1::OverloadEvent> pending_overloads;
};

// Spawns out-of-process workers per WORKER_HOST.md: pipe server first,
// CREATE_SUSPENDED → AssignProcessToJobObject → ResumeThread → Hello → Identify.
class WorkerHost {
 public:
  WorkerHost(DaemonJob& job, std::string instance_id);

  bool spawn(const std::filesystem::path& executable,
             const std::string& worker_id, const std::string& plugin_id,
             SpawnedWorker& out, std::string& error,
             std::chrono::milliseconds connect_timeout =
                 std::chrono::milliseconds(5000));

  // Closes the pipe and terminates the process if still running.
  void stop(SpawnedWorker& worker);

  // Request/response helpers on an already-spawned worker pipe.
  bool discover(SpawnedWorker& worker, capture::v1::DiscoverReply& reply,
                std::string& error,
                std::chrono::milliseconds timeout =
                    std::chrono::milliseconds(5000));
  bool connect(SpawnedWorker& worker, const std::string& source_id,
               capture::v1::ConnectReply& reply, std::string& error,
               std::chrono::milliseconds timeout =
                   std::chrono::milliseconds(10000));
  bool start_capture(SpawnedWorker& worker,
                     const capture::v1::StartRequest& req,
                     capture::v1::StartReply& reply, std::string& error,
                     std::chrono::milliseconds timeout =
                         std::chrono::milliseconds(15000));
  bool stop_capture(SpawnedWorker& worker, const std::string& source_id,
                    capture::v1::StopReply& reply, std::string& error,
                    std::chrono::milliseconds timeout =
                        std::chrono::milliseconds(10000));
  bool get_config_schema(SpawnedWorker& worker, const std::string& source_id,
                         capture::v1::GetConfigSchemaReply& reply,
                         std::string& error,
                         std::chrono::milliseconds timeout =
                             std::chrono::milliseconds(5000));
  bool apply_config(SpawnedWorker& worker,
                    const capture::v1::ApplyConfigRequest& req,
                    capture::v1::ApplyConfigReply& reply, std::string& error,
                    std::chrono::milliseconds timeout =
                        std::chrono::milliseconds(5000));

  // Drain buffered + in-flight unsolicited worker events. SegmentSealed is
  // acknowledged automatically. Returns events delivered to callbacks.
  int drain_events(
      SpawnedWorker& worker,
      const std::function<void(const capture::v1::SegmentSealed&)>& on_sealed,
      const std::function<void(const capture::v1::PreviewFrame&)>& on_preview =
          {},
      const std::function<void(const capture::v1::HealthSnapshot&)>& on_health =
          {},
      const std::function<void(const capture::v1::OverloadEvent&)>& on_overload =
          {});

 private:
  DaemonJob& job_;
  std::string instance_id_;
};

std::string worker_pipe_name(const std::string& instance_id,
                             const std::string& worker_id);

}  // namespace capture::daemon
