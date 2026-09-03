// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "camera_worker/camera_enumerate.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace capture::camera_worker {

// One discrete capture mode the device can deliver (VIDEO_PIPELINE / CONFIGURATION_UI).
struct CaptureMode {
  int width = 0;
  int height = 0;
  int fps_n = 0;
  int fps_d = 1;
  bool is_jpeg = false;
  std::string pixel_format;  // e.g. NV12, YUY2; empty for MJPEG

  // Stable wire value for JSON Schema enum, e.g. "1920x1080@30:NV12".
  std::string key() const;
  // Operator-facing label, e.g. "1080p (FHD) · 1920×1080 @ 30 fps (NV12)".
  std::string label() const;
  // Capsfilter string for the source branch.
  std::string caps_string() const;
};

// Probe mfvideosrc pad caps for the device. Deduplicates by WxH@fps preferring
// raw over MJPEG when both exist.
std::vector<CaptureMode> enumerate_capture_modes(const CameraDevice& device);

// Pick a sensible default: 1080p@~30 if present, else 1440p, else highest under 4K, else first.
std::string default_capture_mode_key(const std::vector<CaptureMode>& modes);

}  // namespace capture::camera_worker
