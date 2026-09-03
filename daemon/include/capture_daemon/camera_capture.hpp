// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "capture_daemon/preview_types.hpp"

#include <atomic>
#include <cstdint>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace capture::daemon {

struct CameraDeviceInfo {
  std::string source_id;           // camera.<stable_key_hash>
  std::string stable_device_key;   // MF symbolic link (immutable)
  std::string friendly_name;
  std::string vendor;
  std::string model;
  std::string symbolic_link;
};

struct CameraFrameTiming {
  int64_t sequence = 0;
  int64_t host_arrival_ns = 0;
  int64_t device_timestamp_100ns = 0;  // MF sample time, 100 ns units
  uint32_t width = 0;
  uint32_t height = 0;
};

// In-process Media Foundation grabber for Milestone 4.
// Records frame timing only (encoded video is Milestone 7).
class CameraCapture {
 public:
  CameraCapture();
  ~CameraCapture();

  CameraCapture(const CameraCapture&) = delete;
  CameraCapture& operator=(const CameraCapture&) = delete;

  static std::vector<CameraDeviceInfo> enumerate();

  bool open(const CameraDeviceInfo& device, std::string& error);
  void close();

  bool start(std::string& error);
  void stop();

  bool is_open() const { return open_; }
  bool is_running() const { return running_.load(); }
  const CameraDeviceInfo& device() const { return device_; }

  // Latest-wins RGB24 thumbnail for preview (longest edge <= 480).
  bool take_preview(PreviewFrameData& out);
  bool copy_preview(PreviewFrameData& out) const;
  // Drain timing samples produced since last call (for MCAP sidecar).
  std::vector<CameraFrameTiming> drain_timings();

  double measured_rate_hz() const;
  int64_t frame_count() const { return frame_count_.load(); }
  std::string last_error() const;

 private:
  void capture_loop();
  bool read_one_frame(std::string& error);

  CameraDeviceInfo device_;
  void* source_reader_ = nullptr;  // IMFSourceReader*
  bool open_ = false;
  std::atomic<bool> running_{false};
  std::thread worker_;

  mutable std::mutex mu_;
  PreviewSlot preview_;
  std::vector<CameraFrameTiming> timings_;
  std::string last_error_;
  int64_t sequence_ = 0;
  std::atomic<int64_t> frame_count_{0};
  int64_t rate_window_start_ns_ = 0;
  int64_t rate_window_frames_ = 0;
  double measured_rate_hz_ = 0;
  uint32_t native_width_ = 0;
  uint32_t native_height_ = 0;
};

}  // namespace capture::daemon
