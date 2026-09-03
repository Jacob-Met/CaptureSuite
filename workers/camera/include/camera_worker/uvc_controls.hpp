// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "camera_worker/camera_enumerate.hpp"

#include <optional>
#include <string>

namespace capture::camera_worker {

struct UvcControlLimits {
  bool exposure_available = false;
  int exposure_min = -13;
  int exposure_max = 0;
  int exposure_default = -5;
  int exposure_step = 1;

  bool gain_available = false;
  int gain_min = 0;
  int gain_max = 255;
  int gain_default = 0;
  int gain_step = 1;
};

// Query IAMCameraControl / IAMVideoProcAmp ranges for schema min/max.
bool query_uvc_limits(const CameraDevice& device, UvcControlLimits& out,
                      std::string& err);

// Apply live image controls. Only fields with a value are written.
bool apply_uvc_controls(const CameraDevice& device, bool exposure_auto,
                        std::optional<int> exposure_time,
                        std::optional<int> gain, std::string& err);

}  // namespace capture::camera_worker
