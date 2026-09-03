// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "camera_worker/camera_enumerate.hpp"
#include "camera_worker/capture_mode.hpp"
#include "camera_worker/capture_pipeline.hpp"

#include "capture/v1/common.pb.h"
#include "capture/v1/preview.pb.h"
#include "capture/v1/source.pb.h"
#include "capture/v1/worker.pb.h"

#include <google/protobuf/message.h>

#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

namespace capture::camera_worker {

class WorkerSession {
 public:
  using OutboundFn = std::function<void(capture::v1::MessageType type,
                                        const std::string& bytes)>;

  explicit WorkerSession(std::string plugin_id);

  void set_outbound(OutboundFn fn) { outbound_ = std::move(fn); }

  void refresh_devices();
  capture::v1::SourceManifest build_manifest() const;
  void fill_discover(capture::v1::DiscoverReply* reply) const;
  bool connect_source(const std::string& source_id,
                      capture::v1::ConnectReply* reply);
  bool start_source(const capture::v1::StartRequest& req,
                    capture::v1::StartReply* reply);
  bool stop_source(const std::string& source_id,
                   capture::v1::StopReply* reply);
  bool preview_descriptor(const std::string& source_id,
                          capture::v1::GetPreviewDescriptorReply* reply);
  bool get_config_schema(const std::string& source_id,
                         capture::v1::GetConfigSchemaReply* reply) const;
  bool apply_config(const capture::v1::ApplyConfigRequest& req,
                    capture::v1::ApplyConfigReply* reply);

  const std::vector<CameraDevice>& devices() const { return devices_; }
  const std::string& plugin_id() const { return plugin_id_; }
  std::string config_json(const std::string& source_id) const;

 private:
  void fill_source(const CameraDevice& device,
                   capture::v1::SourceInstance* out) const;
  const CameraDevice* find_device(const std::string& source_id) const;
  const std::vector<CaptureMode>& modes_for(const std::string& source_id) const;
  void emit(capture::v1::MessageType type, const google::protobuf::Message& msg);

  std::string plugin_id_;
  std::string gst_version_;
  std::vector<CameraDevice> devices_;
  std::string connected_source_id_;
  std::string connected_caps_;
  std::unique_ptr<CapturePipeline> pipeline_;
  OutboundFn outbound_;
  std::mutex outbound_mu_;
  std::unordered_map<std::string, std::string> config_json_;
  mutable std::unordered_map<std::string, std::vector<CaptureMode>> modes_cache_;
};

}  // namespace capture::camera_worker
