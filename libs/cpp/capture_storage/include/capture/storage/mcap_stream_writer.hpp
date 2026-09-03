// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace mcap {
class McapWriter;
struct Schema;
struct Channel;
}  // namespace mcap

namespace capture::storage {

struct StreamWriterConfig {
  std::string source_id;
  std::string stream_id;
  std::string modality;
  std::string data_schema_id;  // e.g. emg.batch/1
  std::string schema_encoding = "protobuf";
  std::vector<std::byte> schema_data;  // FileDescriptorSet bytes (may be empty)
  double nominal_rate_hz = 0;
  // Rotation thresholds (injectable for tests).
  int64_t rotate_bytes = 512LL * 1024 * 1024;
  int64_t rotate_session_ns = 300LL * 1000000000LL;
  int max_batch_samples = 4096;
  int64_t max_batch_ns = 50LL * 1000000LL;  // 50 ms default
  // Filename after the six-digit index, e.g. ".mcap" or ".timing.mcap".
  std::string filename_suffix = ".mcap";
  bool compress = true;
  // When true, never rotate on size/time; caller opens/closes per external segment.
  bool external_rotation = false;
};

struct SamplePoint {
  int64_t sequence = 0;
  int64_t session_time_ns = 0;
  int64_t host_arrival_ns = 0;
  uint32_t quality_flags = 0;
  std::vector<uint8_t> payload;  // modality-specific; may be empty for timing-only
};

struct SealedSegmentInfo {
  std::filesystem::path relative_path;  // from package root
  std::filesystem::path absolute_path;
  int64_t size_bytes = 0;
  std::string hash_blake3_hex;
  int64_t start_session_time_ns = 0;
  int64_t end_session_time_ns = 0;
  int64_t actual_count = 0;
  int segment_index = 0;
  // When set (worker SegmentSealed), preferred over path heuristics.
  std::string source_id;
  std::string stream_id;
};

// Writes protobuf-batched samples into rotating MCAP segments.
class McapStreamWriter {
 public:
  using RotateCallback = std::function<void(const SealedSegmentInfo&)>;

  McapStreamWriter();
  ~McapStreamWriter();

  McapStreamWriter(const McapStreamWriter&) = delete;
  McapStreamWriter& operator=(const McapStreamWriter&) = delete;

  bool open(std::filesystem::path segments_dir, std::filesystem::path package_root,
            StreamWriterConfig config, std::string& error,
            int initial_segment_index = 0);
  void set_rotate_callback(RotateCallback cb) { on_rotate_ = std::move(cb); }
  void set_writes_blocked(bool blocked) { writes_blocked_ = blocked; }

  bool append(const SamplePoint& sample, std::string& error);
  bool flush(std::string& error);
  bool close(std::string& error);  // seals current segment
  // Seal the current segment (if any) and open `index` as the next file.
  // Used when an external muxer (splitmuxsink) owns rotation.
  bool open_segment_index(int index, std::string& error);

  int64_t total_samples() const { return total_samples_; }
  int current_segment_index() const { return segment_index_; }
  const StreamWriterConfig& config() const { return config_; }

 private:
  bool open_segment(std::string& error);
  bool close_segment(bool seal, std::string& error);
  bool flush_batch(std::string& error);
  bool should_rotate() const;
  std::string serialize_batch() const;

  std::filesystem::path segments_dir_;
  std::filesystem::path package_root_;
  StreamWriterConfig config_;
  RotateCallback on_rotate_;

  std::unique_ptr<mcap::McapWriter> writer_;
  std::unique_ptr<std::ofstream> file_;
  uint16_t channel_id_ = 0;
  int segment_index_ = 0;
  int64_t segment_start_ns_ = -1;
  int64_t segment_end_ns_ = -1;
  int64_t segment_count_ = 0;
  int64_t total_samples_ = 0;
  int64_t approx_bytes_ = 0;
  bool writes_blocked_ = false;

  std::vector<SamplePoint> batch_;
  int64_t batch_start_ns_ = -1;
};

}  // namespace capture::storage
