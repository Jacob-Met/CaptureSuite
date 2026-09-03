// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "radar_worker/capture_pipeline.hpp"
#include "radar_worker/ifx_device.hpp"

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

namespace capture::radar_worker {

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

  const std::string& plugin_id() const { return plugin_id_; }
  std::string config_json(const std::string& source_id) const;

 private:
  struct DeviceEntry {
    BoardInfo board;
    std::string source_id;
  };

  void fill_source(const DeviceEntry& entry,
                   capture::v1::SourceInstance* out) const;
  const DeviceEntry* find_device(const std::string& source_id) const;
  void emit(capture::v1::MessageType type, const google::protobuf::Message& msg);
  FmcwSequenceConfig fmcw_sequence_config(
      const std::string& source_id) const;
  void close_device();

  std::string plugin_id_;
  std::string sdk_version_;
  std::vector<DeviceEntry> devices_;
  std::string connected_source_id_;
  BoardKind connected_kind_ = BoardKind::Fmcw;
  std::unique_ptr<IfxFmcwDevice> fmcw_device_;
  std::unique_ptr<IfxLtr11Device> ltr11_device_;
  std::unique_ptr<CapturePipeline> pipeline_;
  OutboundFn outbound_;
  std::mutex outbound_mu_;
  std::unordered_map<std::string, std::string> config_json_;
};

}  // namespace capture::radar_worker
