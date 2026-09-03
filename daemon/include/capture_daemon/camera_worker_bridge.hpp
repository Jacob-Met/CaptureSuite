// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "capture_daemon/external_worker_bridge.hpp"

namespace capture::daemon {

// Compatibility alias — camera-specific fields live on ExternalWorkerHealth.
using CameraWorkerHealth = ExternalWorkerHealth;

// Thin facade over ExternalWorkerBridge so existing SimEngine call sites keep
// compiling while all lifecycle logic lives in one place.
class CameraWorkerBridge {
 public:
  explicit CameraWorkerBridge(std::string instance_id)
      : impl_(std::move(instance_id), camera_worker_plugin_spec()) {}

  static bool should_enable() {
    return ExternalWorkerBridge::should_enable(camera_worker_plugin_spec());
  }
  static bool forced_off() {
    return ExternalWorkerBridge::forced_off(camera_worker_plugin_spec());
  }
  static std::filesystem::path resolve_worker_exe() {
    return ExternalWorkerBridge::resolve_worker_exe(camera_worker_plugin_spec());
  }
  static std::filesystem::path resolve_gstreamer_root() {
    return ExternalWorkerBridge::resolve_gstreamer_root();
  }
  static bool gstreamer_available() {
    return ExternalWorkerBridge::gstreamer_available();
  }

  bool spawn_for_source(const std::string& source_id, std::string& error) {
    return impl_.spawn_for_source(source_id, error);
  }
  bool connect_source(const std::string& source_id, std::string& error) {
    return impl_.connect_source(source_id, error);
  }
  bool start_capture(const std::string& source_id,
                     const capture::v1::StartRequest& req, std::string& error) {
    return impl_.start_capture(source_id, req, error);
  }
  bool stop_capture(const std::string& source_id, std::string& error) {
    return impl_.stop_capture(source_id, error);
  }
  bool get_config_schema(const std::string& source_id,
                         capture::v1::GetConfigSchemaReply& reply,
                         std::string& error) {
    return impl_.get_config_schema(source_id, reply, error);
  }
  bool apply_config(const std::string& source_id, const std::string& config_json,
                    capture::v1::ApplyConfigReply& reply, std::string& error) {
    return impl_.apply_config(source_id, config_json, reply, error);
  }
  void stop_all() { impl_.stop_all(); }
  void force_stop_all() { impl_.force_stop_all(); }
  void force_stop_worker(const std::string& source_id) {
    impl_.force_stop_worker(source_id);
  }

  int poll(
      const std::function<void(const capture::v1::SegmentSealed&)>& on_sealed,
      const std::function<void(PreviewFrameData)>& on_preview = {},
      const std::function<void(const capture::v1::OverloadEvent&)>& on_overload =
          {}) {
    return impl_.poll(on_sealed, on_preview, on_overload);
  }

  bool has_worker(const std::string& source_id) const {
    return impl_.has_worker(source_id);
  }
  CameraWorkerHealth health(const std::string& source_id) const {
    return impl_.health(source_id);
  }
  std::string preferred_encoder() const { return impl_.preferred_encoder(); }
  bool worker_died(const std::string& source_id) const {
    return impl_.worker_died(source_id);
  }
  ExternalWorkerBridge& impl() { return impl_; }
  const ExternalWorkerBridge& impl() const { return impl_; }

 private:
  ExternalWorkerBridge impl_;
};

inline PreviewFrameData preview_from_proto(const capture::v1::PreviewFrame& in) {
  return external_preview_from_proto(in);
}

}  // namespace capture::daemon
