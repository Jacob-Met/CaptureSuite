// SPDX-License-Identifier: GPL-3.0-only
#include "camera_worker/gst_pipeline.hpp"

#include <gst/gst.h>

#include <string>

namespace capture::camera_worker {

bool probe_device_open(const CameraDevice& device, std::string& negotiated_caps,
                       std::string& error) {
  negotiated_caps.clear();
  if (device.symbolic_link.empty()) {
    error = "device has no MF symbolic link";
    return false;
  }
  if (!mfvideosrc_available()) {
    error = "mfvideosrc element not available";
    return false;
  }

  // Minimal graph: source ! fakesink. Caps negotiation proves the device opens.
  GstElement* pipeline = gst_pipeline_new("probe");
  GstElement* src = gst_element_factory_make("mfvideosrc", "src");
  GstElement* sink = gst_element_factory_make("fakesink", "sink");
  if (pipeline == nullptr || src == nullptr || sink == nullptr) {
    error = "failed to create probe elements";
    if (pipeline) {
      gst_object_unref(pipeline);
    }
    return false;
  }
  g_object_set(src, "device-path", device.symbolic_link.c_str(), nullptr);
  g_object_set(sink, "sync", FALSE, nullptr);
  gst_bin_add_many(GST_BIN(pipeline), src, sink, nullptr);
  if (!gst_element_link(src, sink)) {
    error = "failed to link mfvideosrc to fakesink";
    gst_object_unref(pipeline);
    return false;
  }

  const GstStateChangeReturn ret =
      gst_element_set_state(pipeline, GST_STATE_PAUSED);
  if (ret == GST_STATE_CHANGE_FAILURE) {
    error = "mfvideosrc failed to reach PAUSED (device busy or unsupported?)";
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);
    return false;
  }

  // Wait briefly for async state change / caps.
  GstState state = GST_STATE_NULL;
  gst_element_get_state(pipeline, &state, nullptr, 3 * GST_SECOND);

  GstPad* pad = gst_element_get_static_pad(src, "src");
  if (pad != nullptr) {
    GstCaps* caps = gst_pad_get_current_caps(pad);
    if (caps == nullptr) {
      caps = gst_pad_query_caps(pad, nullptr);
    }
    if (caps != nullptr) {
      gchar* text = gst_caps_to_string(caps);
      if (text != nullptr) {
        negotiated_caps = text;
        g_free(text);
      }
      gst_caps_unref(caps);
    }
    gst_object_unref(pad);
  }

  gst_element_set_state(pipeline, GST_STATE_NULL);
  gst_object_unref(pipeline);

  if (negotiated_caps.empty()) {
    error = "device opened but no caps negotiated";
    return false;
  }
  return true;
}

}  // namespace capture::camera_worker
