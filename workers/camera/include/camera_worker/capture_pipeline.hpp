// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "camera_worker/camera_enumerate.hpp"

#include "capture/storage/mcap_stream_writer.hpp"
#include "capture/v1/health.pb.h"
#include "capture/v1/preview.pb.h"
#include "capture/v1/worker.pb.h"

#include <atomic>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <mutex>
#include <string>
#include <thread>

namespace capture::camera_worker {

enum class EncodeMode {
  Passthrough,
  EncodeRaw,
  EncodeTranscoded,
};

struct CapturePipelineOptions {
  std::string encoder_preference = "auto";  // or concrete element name
  bool preview_enabled = true;
  double preview_max_rate_hz = 10.0;
  // "thumbnail" = 320x240 (default, cheap on the control pipe).
  // "capture" = match the armed capture mode resolution (still JPEG, rate-capped).
  std::string preview_quality = "thumbnail";
  int preview_width = 320;
  int preview_height = 240;
  // Empty = let the device pick. Otherwise a CaptureMode::caps_string().
  std::string source_caps;
  bool source_is_jpeg = false;
};

struct CaptureStartConfig {
  std::filesystem::path package_path;
  std::string session_id;
  int64_t session_t0_qpc_ns = 0;
  double nominal_fps = 30.0;
};

// Full VIDEO_PIPELINE.md graph: mfvideosrc → tee → record + preview.
class CapturePipeline {
 public:
  using SegmentSealedFn = std::function<void(const capture::v1::SegmentSealed&)>;
  using PreviewFn = std::function<void(const capture::v1::PreviewFrame&)>;
  using OverloadFn = std::function<void(const std::string& reason)>;
  using HealthFn = std::function<void(const capture::v1::HealthSnapshot&)>;

  CapturePipeline();
  ~CapturePipeline();

  CapturePipeline(const CapturePipeline&) = delete;
  CapturePipeline& operator=(const CapturePipeline&) = delete;

  bool prepare(const CameraDevice& device, const CapturePipelineOptions& opts,
               std::string& error);
  bool start(const CaptureStartConfig& cfg, std::string& error);
  bool stop(std::string& error);
  // Hot-update preview branch (size / rate / jpeg quality) while running.
  // Does not touch the record branch or require a session restart.
  bool update_preview_options(const CapturePipelineOptions& opts,
                              std::string& error);

  bool running() const { return running_.load(); }
  EncodeMode encode_mode() const { return encode_mode_; }
  std::string encoder_name() const { return encoder_name_; }
  std::string negotiated_caps() const;

  void set_segment_sealed_callback(SegmentSealedFn cb) {
    on_segment_sealed_ = std::move(cb);
  }
  void set_preview_callback(PreviewFn cb) { on_preview_ = std::move(cb); }
  void set_overload_callback(OverloadFn cb) { on_overload_ = std::move(cb); }
  void set_health_callback(HealthFn cb) { on_health_ = std::move(cb); }

  capture::v1::PreviewDescriptor preview_descriptor() const;
  static std::string probe_preferred_encoder();
  static const char* encode_mode_name(EncodeMode mode);

  // Called from GStreamer format-location-full (public for C trampoline).
  char* format_location(unsigned int fragment_id);
  // Called from record-branch pad probe.
  void on_record_buffer(void* buffer);
  void notify_overload(const std::string& reason);

 private:
  bool build_pipeline(std::string& error);
  bool choose_encoder(std::string& error);
  void apply_preview_element_settings();
  bool open_timing_segment(int fragment_id, std::string& error);
  void seal_mkv_segment(int fragment_id);
  void teardown();
  void preview_loop();
  void bus_loop();
  void health_loop();
  bool write_stream_json(std::string& error) const;
  static int64_t now_qpc_ns();
  int64_t session_ns_from_qpc(int64_t qpc_ns) const;

  CameraDevice device_;
  CapturePipelineOptions opts_;
  CaptureStartConfig start_cfg_;
  EncodeMode encode_mode_ = EncodeMode::EncodeTranscoded;
  std::string encoder_name_;
  std::string negotiated_caps_;

  void* pipeline_ = nullptr;  // GstElement*
  void* appsink_ = nullptr;
  void* splitmux_ = nullptr;
  void* record_queue_ = nullptr;
  void* preview_rate_ = nullptr;   // videorate
  void* preview_caps_ = nullptr;   // capsfilter after videoscale
  void* preview_jpeg_ = nullptr;   // jpegenc

  std::filesystem::path segments_dir_;
  std::string stream_id_;
  capture::storage::McapStreamWriter timing_writer_;
  int current_fragment_ = -1;
  int64_t frame_index_in_segment_ = 0;
  int64_t global_sequence_ = 0;
  int64_t segment_start_session_ns_ = -1;
  int64_t segment_end_session_ns_ = -1;
  int64_t segment_frame_count_ = 0;

  std::atomic<bool> running_{false};
  std::atomic<bool> stop_threads_{false};
  std::atomic<int64_t> dropped_count_{0};
  std::atomic<int64_t> frames_in_window_{0};
  std::atomic<int64_t> window_start_qpc_ns_{0};
  std::atomic<double> measured_rate_hz_{0};
  std::thread preview_thread_;
  std::thread bus_thread_;
  std::thread health_thread_;
  mutable std::mutex mu_;

  SegmentSealedFn on_segment_sealed_;
  PreviewFn on_preview_;
  OverloadFn on_overload_;
  HealthFn on_health_;
};

}  // namespace capture::camera_worker
