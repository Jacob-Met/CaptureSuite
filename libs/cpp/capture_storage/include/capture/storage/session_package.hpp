// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "capture/storage/disk_watchdog.hpp"
#include "capture/storage/journal.hpp"
#include "capture/storage/mcap_stream_writer.hpp"

#include <atomic>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace capture::storage {

struct PackageStreamDesc {
  std::string source_id;
  std::string stream_id;
  std::string modality;
  std::string alias;
  std::string source_type;
  double nominal_rate_hz = 0;
  // When true, the owning worker writes segment files and reports SegmentSealed.
  // The daemon still writes source/stream metadata but does not open an MCAP writer.
  bool external_segments = false;
};

struct PackageOptions {
  std::filesystem::path parent_dir;
  std::string session_id;
  std::string session_name;
  std::string daemon_version = "0.1.0";
  int64_t rotate_bytes = 512LL * 1024 * 1024;
  int64_t rotate_session_ns = 300LL * 1000000000LL;
  std::filesystem::path descriptor_set_path;
};

struct IntegrityEntry {
  std::string path;
  int64_t size_bytes = 0;
  std::string hash_blake3_hex;
  std::string source_id;
  std::string stream_id;
  int64_t start_session_time_ns = 0;
  int64_t end_session_time_ns = 0;
  int64_t expected_count = 0;
  int64_t actual_count = 0;
  std::string status;
};

struct CheckpointRecord {
  std::string checkpoint_id;
  int64_t original_timestamp_ns = 0;
  int64_t effective_timestamp_ns = 0;
  std::string name;
  std::string created_via;
};

struct AnnotationRecord {
  std::string annotation_id;
  int64_t timestamp_ns = 0;
  std::string text;
  std::string created_via;
};

struct SyncAnchorRecord {
  std::string sync_anchor_id;
  int64_t timestamp_ns = 0;
  std::string mechanism;
  std::string created_via;
};

class SessionPackage {
 public:
  SessionPackage() = default;
  ~SessionPackage();

  SessionPackage(const SessionPackage&) = delete;
  SessionPackage& operator=(const SessionPackage&) = delete;

  bool create(const PackageOptions& opts, std::string& error);
  const std::filesystem::path& root() const { return root_; }
  const std::string& session_id() const { return session_id_; }
  std::string state() const;

  bool begin_recording(const std::vector<PackageStreamDesc>& streams,
                       int64_t t0_qpc_ticks, int64_t qpc_frequency,
                       const std::string& t0_wall_utc, int64_t t0_uncertainty_ns,
                       std::string& error);

  bool write_sample(const std::string& stream_id, const SamplePoint& sample,
                    std::string& error);

  bool add_checkpoint(const std::string& checkpoint_id, int64_t ts_ns,
                      const std::string& name, const std::string& created_via,
                      std::string& error);
  bool add_annotation(const std::string& annotation_id, int64_t ts_ns,
                      const std::string& text, const std::string& created_via,
                      std::string& error);
  bool add_sync_anchor(const std::string& sync_id, int64_t ts_ns,
                       const std::string& mechanism,
                       const std::string& created_via, std::string& error);

  bool open_gap(const std::string& source_id, const std::string& stream_id,
                const std::string& cause, int64_t start_ns, std::string& error);
  bool close_gap(const std::string& stream_id, int64_t end_ns, std::string& error);

  bool journal_event(const std::string& kind, int64_t session_time_ns,
                     const std::string& source_id, const std::string& stream_id,
                     const std::string& payload_json, std::string& error);

  void poll_disk();
  bool writes_blocked() const { return writes_blocked_; }
  void set_free_bytes_override(std::optional<int64_t> bytes);

  bool finalize(std::string& error);

  int64_t sample_count(const std::string& stream_id) const;
  int64_t total_samples() const;
  int sealed_segment_count() const { return sealed_segment_count_; }

  // Worker-reported sealed segment (VIDEO_PIPELINE / WORKER_HOST). Updates
  // integrity.json and journals SEGMENT_ROTATED.
  void record_external_segment(const SealedSegmentInfo& info);

 private:
  bool write_manifest(std::string& error);
  bool write_integrity(std::string& error);
  bool write_events_json(std::string& error);
  bool write_arrays_json(std::string& error);
  bool ensure_source_metadata(const PackageStreamDesc& desc, std::string& error);
  std::vector<std::byte> load_schema_data() const;
  std::string data_schema_for(const std::string& modality) const;
  std::string wall_now_utc() const;
  void on_segment_sealed(const SealedSegmentInfo& info);

  mutable std::recursive_mutex mu_;
  // root_ is assigned once in create() and read without the lock thereafter.
  std::filesystem::path root_;
  std::string session_id_;
  std::string state_ = "preparing";
  PackageOptions opts_;
  Journal journal_;
  std::unique_ptr<DiskWatchdog> watchdog_;
  // Read by the lock-free getters below, so both must be atomic.
  std::atomic<bool> writes_blocked_{false};
  bool write_blocked_journaled_ = false;

  int64_t t0_qpc_ticks_ = 0;
  int64_t qpc_frequency_ = 0;
  std::string t0_wall_utc_;
  int64_t t0_uncertainty_ns_ = 0;
  std::string created_utc_;
  std::vector<std::string> source_ids_;

  std::unordered_map<std::string, std::unique_ptr<McapStreamWriter>> writers_;
  std::unordered_map<std::string, PackageStreamDesc> stream_descs_;
  std::vector<IntegrityEntry> integrity_;
  std::atomic<int> sealed_segment_count_{0};

  std::vector<CheckpointRecord> checkpoints_;
  std::vector<AnnotationRecord> annotations_;
  std::vector<SyncAnchorRecord> sync_anchors_;
};

}  // namespace capture::storage
