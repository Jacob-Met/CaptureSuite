// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "camera_worker/camera_enumerate.hpp"

#include <string>

namespace capture::camera_worker {

// Opens mfvideosrc for the device long enough to negotiate caps, then tears
// down. Used by Connect to prove the GStreamer path without starting record.
bool probe_device_open(const CameraDevice& device, std::string& negotiated_caps,
                       std::string& error);

}  // namespace capture::camera_worker
