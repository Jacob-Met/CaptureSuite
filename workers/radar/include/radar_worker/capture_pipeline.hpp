// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "radar_worker/ifx_device.hpp"

#include "capture/storage/mcap_stream_writer.hpp"
#include "capture/v1/health.pb.h"
#include "capture/v1/preview.pb.h"
#include "capture/v1/worker.pb.h"

#include <atomic>
#include <cstdint>
#include <deque>
#include <filesystem>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace capture::radar_worker {

struct CaptureStartConfig {
  std::filesystem::path package_path;
  std::string session_id;
  int64_t session_t0_qpc_ns = 0;
};

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

  bool prepare(const std::string& source_id, BoardKind kind,
               IfxFmcwDevice* fmcw, IfxLtr11Device* ltr11,
               std::string& error);
  bool start(const CaptureStartConfig& cfg, std::string& error);
  bool stop(std::string& error);

  bool running() const { return running_.load(); }
  bool failed() const { return failed_.load(); }

  // Live preview mode switch (Fusion-style views). Safe during acquisition.
  void set_preview_view(std::string view);
  std::string preview_view() const;

  void set_segment_sealed_callback(SegmentSealedFn cb) {
    on_segment_sealed_ = std::move(cb);
  }
  void set_preview_callback(PreviewFn cb) { on_preview_ = std::move(cb); }
  void set_overload_callback(OverloadFn cb) { on_overload_ = std::move(cb); }
  void set_health_callback(HealthFn cb) { on_health_ = std::move(cb); }

  capture::v1::PreviewDescriptor preview_descriptor() const;

 private:
  void acquisition_loop();
  void acquisition_loop_fmcw();
  void acquisition_loop_ltr11();
  void health_loop();
  bool write_stream_json(std::string& error) const;
  static int64_t now_qpc_ns();
  int64_t session_ns_from_qpc(int64_t qpc_ns) const;
  void handle_frame_error(IfxFrameError err);
  double nominal_rate_hz() const;
  std::string configuration_hash() const;
  void emit_fmcw_preview(const std::vector<uint16_t>& raw, int64_t session,
                         int64_t sequence);
  void emit_ltr11_preview(const Ltr11FrameResult& frame, int64_t session,
                          int64_t sequence);
  void push_spectrogram_row(const std::vector<float>& row, float display_max);
  void emit_spectrogram_matrix(int64_t session, int64_t sequence,
                               const char* row_axis, const char* col_axis);

  std::string source_id_;
  std::string stream_id_;
  BoardKind kind_ = BoardKind::Fmcw;
  IfxFmcwDevice* fmcw_ = nullptr;
  IfxLtr11Device* ltr11_ = nullptr;
  CaptureStartConfig start_cfg_;
  std::filesystem::path segments_dir_;

  capture::storage::McapStreamWriter writer_;
  int64_t frame_index_ = 0;
  int64_t global_sequence_ = 0;
  int64_t last_frame_index_ = -1;

  std::atomic<bool> running_{false};
  std::atomic<bool> stop_threads_{false};
  std::atomic<bool> failed_{false};
  std::atomic<int64_t> frames_in_window_{0};
  std::atomic<int64_t> window_start_qpc_ns_{0};
  std::atomic<double> measured_rate_hz_{0};

  std::thread acquisition_thread_;
  std::thread health_thread_;
  mutable std::mutex mu_;

  std::string preview_view_;
  std::deque<std::vector<float>> spectrogram_rows_;
  float spectrogram_display_max_ = 1.0f;
  static constexpr std::size_t kSpectrogramHistory = 48;

  SegmentSealedFn on_segment_sealed_;
  PreviewFn on_preview_;
  OverloadFn on_overload_;
  HealthFn on_health_;
};

}  // namespace capture::radar_worker
