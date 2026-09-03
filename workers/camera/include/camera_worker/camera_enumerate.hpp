// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <string>
#include <vector>

namespace capture::camera_worker {

struct CameraDevice {
  std::string source_id;          // camera.<hash> — stable across MF/GStreamer
  std::string stable_device_key;  // MF symbolic link
  std::string friendly_name;
  std::string vendor;
  std::string model;
  std::string symbolic_link;
};

// Media Foundation enumeration; identity key is the symbolic link so source
// IDs survive the GStreamer cutover (VIDEO_PIPELINE.md).
std::vector<CameraDevice> enumerate_cameras();

// Returns empty on success; otherwise a human-readable GStreamer init error.
std::string init_gstreamer();

bool mfvideosrc_available();

}  // namespace capture::camera_worker
