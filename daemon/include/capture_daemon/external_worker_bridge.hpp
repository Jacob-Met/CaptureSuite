// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "capture_daemon/preview_types.hpp"
#include "capture_daemon/process_security.hpp"
#include "capture_daemon/worker_host.hpp"

#include "capture/v1/health.pb.h"
#include "capture/v1/source.pb.h"
#include "capture/v1/worker.pb.h"

#include <chrono>
#include <filesystem>
#include <functional>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

namespace capture::daemon {

struct ExternalWorkerHealth {
  double measured_rate_hz = 0;
  int64_t dropped_count = 0;
  int64_t dropped_last_10s = 0;
  int64_t recorded_sample_count = 0;
  bool data_arriving = false;
  bool write_ok = true;
  bool process_alive = true;
  std::string current_segment;
  std::string last_error_code;
  std::string last_error_message;
  std::string encoder_name;
  std::string encode_mode;
};

// Shared out-of-process worker lifecycle for camera, radar, and future
// modality workers. Plugin-specific bits (exe path, env gate, preview decode,
// spawn timeouts) live in PluginSpec so SimEngine does not grow another
// near-copy of this class per vendor.
struct ExternalWorkerPluginSpec {
  std::string plugin_id;           // camera.gstreamer | radar.ifx | …
  std::string family;              // "camera" | "radar" (log + worker-id prefix)
  std::string enable_env;          // CAPTURE_USE_CAMERA_WORKER, …
  std::string exe_env;             // CAPTURE_CAMERA_WORKER_EXE, …
  std::string exe_name;            // capture_worker_camera.exe
  std::string workers_subdir;      // camera | radar
  bool require_gstreamer = false;
  bool skip_auto_in_unit_tests = true;
  std::chrono::milliseconds spawn_timeout{8000};
  std::chrono::milliseconds connect_timeout{15000};
  std::chrono::milliseconds start_timeout{20000};
  std::chrono::milliseconds stop_timeout{60000};
  std::chrono::milliseconds enumerate_timeout{20000};
  // OverloadEvent → health message when the worker doesn't supply one.
  std::string overload_code = "OVERLOAD_DROP";
  std::string overload_message = "record queue overrun";
};

class ExternalWorkerBridge {
 public:
  ExternalWorkerBridge(std::string instance_id, ExternalWorkerPluginSpec spec);
  ~ExternalWorkerBridge();

  ExternalWorkerBridge(const ExternalWorkerBridge&) = delete;
  ExternalWorkerBridge& operator=(const ExternalWorkerBridge&) = delete;

  const ExternalWorkerPluginSpec& spec() const { return spec_; }

  static bool forced_off(const ExternalWorkerPluginSpec& spec);
  static bool should_enable(const ExternalWorkerPluginSpec& spec);
  static std::filesystem::path resolve_worker_exe(
      const ExternalWorkerPluginSpec& spec);
  static std::filesystem::path resolve_gstreamer_root();
  static bool gstreamer_available();

  bool forced_off() const { return forced_off(spec_); }
  bool should_enable() const { return should_enable(spec_); }
  std::filesystem::path resolve_worker_exe() const {
    return resolve_worker_exe(spec_);
  }

  // Spawns a short-lived worker, copies Identify sources, stops it.
  bool enumerate(std::vector<capture::v1::SourceInstance>& out,
                 std::string& error);

  bool spawn_for_source(const std::string& source_id, std::string& error);
  bool connect_source(const std::string& source_id, std::string& error);
  bool start_capture(const std::string& source_id,
                     const capture::v1::StartRequest& req, std::string& error);
  bool stop_capture(const std::string& source_id, std::string& error);
  bool get_config_schema(const std::string& source_id,
                         capture::v1::GetConfigSchemaReply& reply,
                         std::string& error);
  bool apply_config(const std::string& source_id, const std::string& config_json,
                    capture::v1::ApplyConfigReply& reply, std::string& error);
  void stop_all();
  // Skip StopCapture RPC — close pipes and TerminateProcess. Use when a worker
  // is hung (USB wedge) so rediscovery is not blocked on a 60s Stop timeout.
  void force_stop_all();
  // Tear down one worker slot (alive or dead) so the next spawn can reopen.
  void force_stop_worker(const std::string& source_id);

  int poll(
      const std::function<void(const capture::v1::SegmentSealed&)>& on_sealed,
      const std::function<void(PreviewFrameData)>& on_preview = {},
      const std::function<void(const capture::v1::OverloadEvent&)>& on_overload =
          {});

  bool has_worker(const std::string& source_id) const;
  ExternalWorkerHealth health(const std::string& source_id) const;
  std::string preferred_encoder() const { return preferred_encoder_; }

  // True when a previously spawned worker process has exited unexpectedly.
  bool worker_died(const std::string& source_id) const;

 private:
  std::string sanitize_worker_id(const std::string& source_id) const;

  std::string instance_id_;
  ExternalWorkerPluginSpec spec_;
  DaemonJob job_;
  WorkerHost host_;
  mutable std::mutex mu_;
  std::unordered_map<std::string, SpawnedWorker> workers_;
  std::unordered_map<std::string, bool> connected_;
  std::unordered_map<std::string, ExternalWorkerHealth> health_;
  std::string preferred_encoder_;
};

PreviewFrameData external_preview_from_proto(
    const capture::v1::PreviewFrame& in);

ExternalWorkerPluginSpec camera_worker_plugin_spec();
ExternalWorkerPluginSpec radar_worker_plugin_spec();
// Hardcoded fallbacks used when no plugin.json is present.
ExternalWorkerPluginSpec camera_worker_plugin_spec_builtin();
ExternalWorkerPluginSpec radar_worker_plugin_spec_builtin();

}  // namespace capture::daemon
