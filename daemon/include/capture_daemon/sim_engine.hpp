// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "capture/clock.hpp"
#include "capture/recording_buffer.hpp"
#include "capture/session_fsm.hpp"
#include "capture/source_fsm.hpp"
#include "capture/storage/disk_watchdog.hpp"
#include "capture/storage/session_package.hpp"
#include "capture_daemon/camera_capture.hpp"
#include "capture_daemon/camera_worker_bridge.hpp"
#include "capture_daemon/preview_types.hpp"
#include "capture_daemon/radar_worker_bridge.hpp"

#include <atomic>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

namespace capture::daemon {

struct SimSourceDesc {
  std::string source_id;
  std::string source_type;
  std::string alias;
  std::string modality;
  std::string stream_id;
  double nominal_rate_hz = 0;
  bool supports_arm = true;
  bool is_replay = false;
  bool is_camera = false;
  bool is_virtual_camera = false;
  bool is_radar = false;
  std::string stable_device_key;
  std::string vendor;
  std::string model;
  std::string serial;
  std::string camera_symbolic_link;
  // When set (e.g. from a worker SourceInstance), fill_source_instance prefers
  // these over modality/is_camera/is_radar fallbacks.
  std::string plugin_id;
  std::string data_schema_id;
};

struct CheckpointEvent {
  std::string checkpoint_id;
  int64_t original_timestamp_ns = 0;
  int64_t effective_timestamp_ns = 0;
  std::string name;
  std::string created_via;
  std::string notes;
  bool timestamp_modified = false;
};

struct AnnotationEvent {
  std::string annotation_id;
  int64_t timestamp_ns = 0;
  std::string text;
  std::string created_via;
};

struct SyncAnchorEvent {
  std::string sync_anchor_id;
  int64_t timestamp_ns = 0;
  std::string mechanism;
  std::string created_via;
};

struct StreamStats {
  std::string stream_id;
  std::string source_id;
  int64_t sample_count = 0;
  int64_t gap_count = 0;
  int64_t open_gap_count = 0;
};

struct RecordingStats {
  SessionState state = SessionState::Idle;
  int64_t elapsed_session_ns = 0;
  int64_t total_samples = 0;
  int64_t checkpoint_count = 0;
  int64_t annotation_count = 0;
  int64_t sync_anchor_count = 0;
  std::string package_path;
  std::vector<StreamStats> streams;
};

struct HealthSnapshotData {
  std::string source_id;
  SourceLifecycle lifecycle = SourceLifecycle::Unavailable;
  SourceHealth health = SourceHealth::Ok;
  bool connected = false;
  bool data_arriving = false;
  double measured_rate_hz = 0;
  double expected_rate_hz = 0;
  int64_t dropped_count = 0;
  int64_t dropped_last_10s = 0;
  bool write_ok = true;
  std::string current_segment;
  bool has_open_gap = false;
  std::string open_gap_cause;
  int64_t open_gap_start_ns = 0;
  int32_t gap_count = 0;
  std::string last_error_code;
  std::string last_error_message;
  int64_t session_time_ns = 0;
};

struct AlertData {
  std::string alert_id;
  std::string level;  // INFO | WARNING | CRITICAL
  std::string source_id;
  std::string code;
  std::string message;
  int64_t session_time_ns = 0;
  bool acknowledged = false;
};

struct DiskStatusData {
  int64_t free_bytes = 0;
  int64_t reserve_bytes = 0;
  double write_mb_per_s = 0;
  double estimated_remaining_minutes = 0;
  std::string headroom_level = "INFO";
  bool writers_blocked = false;
};

struct PreflightCheckData {
  std::string check_id;
  std::string name;
  std::string status;  // ok | warn | fail
  std::string message;
  bool overridable = false;
};

struct LaneViewData {
  std::string source_id;
  std::string stream_id;
  std::string modality;
  std::string alias;
  int64_t sample_count = 0;
  int64_t first_sample_session_ns = 0;
  int64_t last_sample_session_ns = 0;
  SourceLifecycle lifecycle = SourceLifecycle::Unavailable;
  std::vector<GapRecord> gaps;
};

struct SessionViewData {
  std::string session_id;
  std::string package_path;
  SessionState state = SessionState::Idle;
  int64_t elapsed_session_ns = 0;
  std::string t0_wall_clock_utc;
  std::vector<CheckpointEvent> checkpoints;
  std::vector<AnnotationEvent> annotations;
  std::vector<SyncAnchorEvent> sync_anchors;
  std::vector<LaneViewData> lanes;
  std::vector<AlertData> alerts;
  DiskStatusData disk;
  bool rehearsal_active = false;
};

class SimEngine {
 public:
  SimEngine();
  ~SimEngine();

  SimEngine(const SimEngine&) = delete;
  SimEngine& operator=(const SimEngine&) = delete;

  const std::vector<SimSourceDesc>& sources() const { return sources_; }
  SourceFsm& source_fsm(const std::string& source_id);
  const SourceFsm& source_fsm(const std::string& source_id) const;
  SessionState session_state() const;

  void set_package_parent(std::filesystem::path parent);
  void set_rotate_bytes(int64_t bytes);
  void set_descriptor_set_path(std::filesystem::path path);

  bool create_session(std::string session_id, std::string& error);
  bool create_session(std::string session_id, std::string package_parent,
                      std::string& error);
  std::string session_id() const;
  std::string package_path() const;

  bool open_session(const std::string& package_path, bool& recovered,
                    std::string& error);

  bool select_sources(const std::vector<std::string>& source_ids, std::string& error);
  std::vector<std::string> selected_source_ids() const;

  void prepare_selected_sources();

  bool start_selected(std::string& error);
  // Selects every source that can be prepared to READY, then starts recording.
  bool start_all_ready(std::vector<std::string>& started_source_ids,
                       std::string& error);
  std::string request_stop_token();
  bool stop(const std::string& confirmation_token, std::string& error);
  bool finalize_session(std::string& error);
  bool acknowledge_alert(const std::string& alert_id, AlertData& out,
                         std::string& error);

  // JSON Schema document for a source (CONFIGURATION_UI.md). Empty source_id
  // rejected. Schema is dynamic per source type in the in-process sim/camera path.
  // Non-const: camera schemas are fetched from the worker (may spawn it).
  bool get_config_schema(const std::string& source_id, std::string& schema_json,
                         std::string& error);
  bool apply_config(const std::string& source_id, const std::string& config_json,
                    std::string& effective_json,
                    std::vector<std::string>& coerced_fields,
                    std::string& schema_revision, std::string& error);
  std::string config_snapshot(const std::string& source_id) const;
  // Copy alert events at/after cursor for a status subscriber. Each client keeps
  // its own cursor so multi-client push does not steal events from peers.
  std::vector<AlertData> alert_events_from(std::size_t cursor) const;
  std::size_t alert_event_count() const;

  CheckpointEvent create_checkpoint(std::string name, std::string created_via);
  bool update_checkpoint(const std::string& checkpoint_id,
                         const std::string* name, const std::string* notes,
                         const int64_t* effective_timestamp_ns,
                         const std::string& reason, CheckpointEvent& out,
                         std::string& error);
  AnnotationEvent annotate(std::string text, std::string created_via);
  SyncAnchorEvent add_sync_anchor(std::string mechanism, std::string created_via);

  bool disconnect_source(const std::string& source_id, std::string& error);
  bool reconnect_source(const std::string& source_id, std::string& error);
  bool inject_fault(const std::string& source_id, const std::string& fault_type,
                    int64_t drop_count, std::string& error);

  // Tear down external workers, re-enumerate cameras/radars, rebuild source
  // rail. Idle/Preparing/Finalized only; auto-stops rehearsal.
  bool rescan_sources(std::string& error);

  std::vector<PreflightCheckData> run_preflight(
      const std::vector<std::string>& source_ids, bool& ok, std::string& error);
  bool start_rehearsal(const std::vector<std::string>& source_ids, std::string& error);
  bool stop_rehearsal(std::string& error);
  bool rehearsal_active() const;

  std::vector<PreviewDescriptorData> list_preview_descriptors(
      const std::vector<std::string>& source_ids) const;
  bool set_preview_config(const std::string& source_id, const bool* enabled,
                          const uint32_t* selected_channel,
                          PreviewDescriptorData& out, std::string& error);
  // Drain latest-wins preview for all sources that have pending frames.
  // Destructive drain (single consumer). Prefer latest_preview_frames for push.
  std::vector<PreviewFrameData> take_preview_frames();
  // Non-destructive snapshot of each source's newest preview frame.
  std::vector<PreviewFrameData> latest_preview_frames() const;
  std::vector<HealthSnapshotData> health_snapshots() const;
  DiskStatusData disk_status() const;
  SessionViewData session_view() const;

  bool is_recording() const;
  int64_t session_elapsed_ns() const;
  RecordingStats recording_stats() const;
  const std::vector<CheckpointEvent>& checkpoints() const { return checkpoints_; }
  bool uses_camera_workers() const { return camera_workers_ != nullptr; }
  bool uses_radar_workers() const { return radar_workers_ != nullptr; }
  std::string camera_worker_encoder() const;

 private:
  void ensure_default_sources();
  void recording_loop();
  void preview_loop();
  void stop_recording_thread();
  void stop_preview_thread();
  void reset_sources_for_new_session();
  void ensure_preview_running_unlocked();
  void generate_sim_preview_unlocked(const SimSourceDesc& src, int64_t session_ns);
  void publish_camera_preview_unlocked(const SimSourceDesc& src,
                                       int64_t session_ns);
  PreviewDescriptorData make_preview_desc(const SimSourceDesc& src) const;
  HealthSnapshotData make_health(const SimSourceDesc& src) const;
  void push_alert(std::string level, std::string source_id, std::string code,
                  std::string message);
  bool open_camera_unlocked(const SimSourceDesc& src, std::string& error);
  void drain_camera_workers();
  void drain_radar_workers();
  // Marks DeviceLost + opens an explicit DISCONNECT gap when an external
  // worker process exits mid-rehearsal/record. Other sources keep running.
  void supervise_external_workers();

  mutable std::mutex mu_;
  SessionClock clock_;
  SessionFsm session_fsm_;
  RecordingStore store_;
  // Held by shared_ptr so a caller can take a handle under mu_, release mu_, and
  // then do storage I/O. Never call a SessionPackage method that touches the disk
  // while holding mu_: a stalled volume would then delay Stop and checkpoints,
  // both of which must stay immediate. Session creation is the one exception,
  // since there is nothing to protect until the package exists.
  std::shared_ptr<capture::storage::SessionPackage> package_;
  std::filesystem::path package_parent_;
  std::filesystem::path descriptor_set_path_;
  int64_t rotate_bytes_ = 512LL * 1024 * 1024;

  std::vector<SimSourceDesc> sources_;
  std::unordered_map<std::string, SourceFsm> fsms_;
  std::unordered_map<std::string, int64_t> drop_remaining_;
  std::unordered_map<std::string, int64_t> gap_counts_;
  std::unordered_map<std::string, std::unique_ptr<PreviewSlot>> preview_slots_;
  std::unordered_map<std::string, PreviewDescriptorData> preview_cfg_;
  std::unordered_map<std::string, int64_t> preview_seq_;
  std::unordered_map<std::string, double> measured_rate_;
  std::unordered_map<std::string, int64_t> samples_in_window_;
  std::unordered_map<std::string, int64_t> window_start_ns_;
  std::unordered_map<std::string, std::unique_ptr<CameraCapture>> cameras_;
  std::unordered_map<std::string, int64_t> camera_preview_seq_;
  std::unique_ptr<CameraWorkerBridge> camera_workers_;
  std::unique_ptr<RadarWorkerBridge> radar_workers_;
  std::string session_id_;
  std::string t0_wall_utc_;
  // Read-only attach after OpenSession (no SessionPackage writers).
  bool review_mode_ = false;
  std::filesystem::path review_package_path_;
  std::vector<LaneViewData> review_lanes_;

  std::atomic<bool> recording_{false};
  std::atomic<bool> preview_running_{false};
  std::atomic<bool> rehearsal_{false};
  std::thread worker_;
  std::thread preview_worker_;
  std::vector<CheckpointEvent> checkpoints_;
  std::vector<AnnotationEvent> annotations_;
  std::vector<SyncAnchorEvent> sync_anchors_;
  std::vector<AlertData> alerts_;
  std::vector<AlertData> alert_events_;
  std::unordered_map<std::string, std::string> config_json_;
  int64_t sequence_counter_ = 0;
};

}  // namespace capture::daemon
