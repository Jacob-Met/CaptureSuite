// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <mutex>
#include <string>
#include <vector>

namespace capture::daemon {

// Mirrors capture.v1.PreviewKind. Kept protobuf-free so the engine and the
// device backends do not depend on generated code.
enum class PreviewKind {
  Unspecified = 0,
  ImageThumbnail = 1,
  TraceSingle = 2,
  TraceBlock = 3,
  Orientation = 4,
  VectorProfile = 5,
  Matrix2D = 6,
  ScalarSeries = 7,
};

// Declares what a source will publish, so the UI can allocate without guessing.
struct PreviewDescriptorData {
  std::string source_id;
  std::string stream_id;
  PreviewKind kind = PreviewKind::Unspecified;
  uint32_t max_payload_bytes = 0;
  double max_rate_hz = 0;
  std::string content_type;
  uint32_t selected_channel = 0;
  std::vector<std::string> available_channels;
  bool enabled = true;
};

// One preview update. The payload fields are a flat union-by-convention: only
// the members implied by `kind` are populated. A struct rather than a variant
// because preview frames are copied into a single slot per source and the
// wasted members cost less than the dispatch ceremony would.
struct PreviewFrameData {
  std::string source_id;
  std::string stream_id;
  PreviewKind kind = PreviewKind::Unspecified;
  int64_t session_time_ns = 0;
  int64_t sequence = 0;
  int64_t dropped_since_last = 0;
  uint32_t selected_channel = 0;

  // TraceSingle / TraceBlock / ScalarSeries / VectorProfile
  std::vector<std::string> channel_names;
  uint32_t channel_count = 0;
  uint32_t points_per_channel = 0;
  std::vector<float> samples;  // channel-major
  float display_min = 0;
  float display_max = 0;
  std::string units;
  double decimated_from_rate_hz = 0;

  // ImageThumbnail
  std::vector<uint8_t> image;
  uint32_t width = 0;
  uint32_t height = 0;
  std::string pixel_format;  // jpeg | rgb24

  // Orientation
  double qw = 1;
  double qx = 0;
  double qy = 0;
  double qz = 0;
  double accel_magnitude = 0;
  double gyro_magnitude = 0;

  // Matrix2D
  uint32_t rows = 0;
  uint32_t cols = 0;
  // Worker-supplied axis labels; a spectrogram stacks time on the row axis.
  std::string row_axis;
  std::string col_axis;
};

// Latest-wins single-slot mailbox. Publishing over an unconsumed frame is
// normal and counted, never blocking: preview must not back-pressure capture.
class PreviewSlot {
 public:
  void publish(PreviewFrameData frame) {
    std::lock_guard lock(mu_);
    if (pending_) {
      ++dropped_;
    }
    frame_ = std::move(frame);
    pending_ = true;
    has_frame_ = true;
  }

  // Moves the pending frame out, attributing drops since the last take.
  // Prefer copy_latest() for multi-subscriber push so one client cannot steal
  // the mailbox from another.
  bool take(PreviewFrameData& out) {
    std::lock_guard lock(mu_);
    if (!pending_) {
      return false;
    }
    out = std::move(frame_);
    out.dropped_since_last = dropped_;
    dropped_ = 0;
    pending_ = false;
    return true;
  }

  // Copy the newest frame without clearing. Safe for multiple subscribers.
  bool copy_latest(PreviewFrameData& out) const {
    std::lock_guard lock(mu_);
    if (!has_frame_) {
      return false;
    }
    out = frame_;
    out.dropped_since_last = dropped_;
    return true;
  }

  void clear() {
    std::lock_guard lock(mu_);
    pending_ = false;
    has_frame_ = false;
    dropped_ = 0;
  }

 private:
  mutable std::mutex mu_;
  PreviewFrameData frame_;
  bool pending_ = false;
  bool has_frame_ = false;
  int64_t dropped_ = 0;
};

}  // namespace capture::daemon
