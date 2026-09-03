// SPDX-License-Identifier: GPL-3.0-only
#include "camera_worker/worker_session.hpp"

#include "camera_worker/gst_pipeline.hpp"
#include "camera_worker/uvc_controls.hpp"

#include "capture/v1/health.pb.h"

#include <gst/gst.h>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <cstdlib>
#include <optional>

namespace capture::camera_worker {

WorkerSession::WorkerSession(std::string plugin_id)
    : plugin_id_(std::move(plugin_id)) {
  guint major = 0;
  guint minor = 0;
  guint micro = 0;
  guint nano = 0;
  gst_version(&major, &minor, &micro, &nano);
  gst_version_ = std::to_string(major) + "." + std::to_string(minor) + "." +
                 std::to_string(micro);
  refresh_devices();
}

void WorkerSession::refresh_devices() {
  devices_ = enumerate_cameras();
  const char* fake = std::getenv("CAPTURE_CAMERA_FAKE");
  if (fake != nullptr && fake[0] != '\0' && fake[0] != '0') {
    CameraDevice d;
    d.source_id = "camera.fake";
    d.stable_device_key = "fake-videotestsrc";
    d.symbolic_link = "fake-videotestsrc";
    d.friendly_name = "Fake Camera (videotestsrc)";
    d.vendor = "CaptureSuite";
    d.model = "videotestsrc";
    devices_.push_back(std::move(d));
  }
}

void WorkerSession::emit(capture::v1::MessageType type,
                         const google::protobuf::Message& msg) {
  if (!outbound_) {
    return;
  }
  std::string bytes;
  msg.SerializeToString(&bytes);
  std::lock_guard lock(outbound_mu_);
  outbound_(type, bytes);
}

void WorkerSession::fill_source(const CameraDevice& device,
                                capture::v1::SourceInstance* out) const {
  out->set_source_id(device.source_id);
  out->set_source_type("camera");
  out->set_alias(device.friendly_name.empty() ? device.source_id
                                              : device.friendly_name);
  out->set_plugin_id(plugin_id_);
  out->set_plugin_version("0.1.0");
  out->set_enabled(true);
  out->set_lifecycle_state(capture::v1::SOURCE_LIFECYCLE_DISCOVERED);
  (*out->mutable_metadata())["modality"] = "video";
  (*out->mutable_metadata())["record_stack"] = "gstreamer";
  (*out->mutable_metadata())["gstreamer_version"] = gst_version_;

  auto* phys = out->add_physical_devices();
  phys->set_vendor(device.vendor);
  phys->set_model(device.model);
  phys->set_stable_device_key(device.stable_device_key);
  phys->set_connection_path(device.symbolic_link);
  out->add_physical_device_ids(device.stable_device_key);

  auto* stream = out->add_streams();
  stream->set_stream_id(device.source_id + ".video");
  stream->set_source_id(device.source_id);
  stream->set_modality("video");
  stream->set_nominal_rate_hz(30.0);
  stream->set_data_schema_id("video.frame_timing/1");
}

capture::v1::SourceManifest WorkerSession::build_manifest() const {
  capture::v1::SourceManifest manifest;
  manifest.set_plugin_id(plugin_id_);
  manifest.set_plugin_version("0.1.0");
  (*manifest.mutable_capabilities())["isolation"] = "per_source";
  (*manifest.mutable_capabilities())["record_stack"] = "gstreamer";
  (*manifest.mutable_capabilities())["gstreamer_version"] = gst_version_;
  const std::string enc = CapturePipeline::probe_preferred_encoder();
  if (!enc.empty()) {
    (*manifest.mutable_capabilities())["preferred_encoder"] = enc;
  }
  if (mfvideosrc_available()) {
    (*manifest.mutable_capabilities())["mfvideosrc"] = "true";
  }
  for (const auto& device : devices_) {
    fill_source(device, manifest.add_sources());
  }
  return manifest;
}

void WorkerSession::fill_discover(capture::v1::DiscoverReply* reply) const {
  for (const auto& device : devices_) {
    fill_source(device, reply->add_sources());
  }
}

const CameraDevice* WorkerSession::find_device(
    const std::string& source_id) const {
  for (const auto& device : devices_) {
    if (device.source_id == source_id) {
      return &device;
    }
  }
  return nullptr;
}

const std::vector<CaptureMode>& WorkerSession::modes_for(
    const std::string& source_id) const {
  auto it = modes_cache_.find(source_id);
  if (it != modes_cache_.end()) {
    return it->second;
  }
  const CameraDevice* device = find_device(source_id);
  if (device == nullptr) {
    static const std::vector<CaptureMode> kEmpty;
    return kEmpty;
  }
  modes_cache_[source_id] = enumerate_capture_modes(*device);
  return modes_cache_[source_id];
}

bool WorkerSession::connect_source(const std::string& source_id,
                                   capture::v1::ConnectReply* reply) {
  const CameraDevice* device = find_device(source_id);
  if (device == nullptr) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("unknown camera source_id");
    return false;
  }
  std::string caps;
  std::string err;
  const char* fake = std::getenv("CAPTURE_CAMERA_FAKE");
  const bool use_fake =
      fake != nullptr && fake[0] != '\0' && fake[0] != '0';
  if (use_fake) {
    caps = "video/x-raw,format=I420,width=640,height=480,framerate=30/1";
  } else if (!probe_device_open(*device, caps, err)) {
    reply->mutable_error()->set_code("CONNECT_FAILED");
    reply->mutable_error()->set_message(err);
    return false;
  }
  connected_source_id_ = source_id;
  connected_caps_ = caps;
  fill_source(*device, reply->mutable_source());
  reply->mutable_source()->set_lifecycle_state(
      capture::v1::SOURCE_LIFECYCLE_CONNECTED);
  (*reply->mutable_source()->mutable_metadata())["negotiated_caps"] = caps;
  return true;
}

bool WorkerSession::start_source(const capture::v1::StartRequest& req,
                                 capture::v1::StartReply* reply) {
  const CameraDevice* device = find_device(req.source_id());
  if (device == nullptr) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("unknown camera source_id");
    return false;
  }
  if (req.session_package_path().empty()) {
    reply->mutable_error()->set_code("BAD_REQUEST");
    reply->mutable_error()->set_message("session_package_path required");
    return false;
  }

  connected_source_id_ = req.source_id();
  pipeline_ = std::make_unique<CapturePipeline>();
  pipeline_->set_segment_sealed_callback(
      [this](const capture::v1::SegmentSealed& sealed) {
        emit(capture::v1::MESSAGE_TYPE_SEGMENT_SEALED, sealed);
      });
  pipeline_->set_preview_callback([this](const capture::v1::PreviewFrame& frame) {
    emit(capture::v1::MESSAGE_TYPE_PREVIEW_FRAME, frame);
  });
  pipeline_->set_overload_callback([this](const std::string& reason) {
    std::fprintf(stderr, "camera worker overload: %s\n", reason.c_str());
    capture::v1::OverloadEvent ov;
    ov.set_source_id(connected_source_id_);
    ov.set_stream_id(connected_source_id_ + ".video");
    ov.set_session_time_ns(0);
    ov.set_queue_occupancy(1.0);
    ov.set_dropped_count(1);
    emit(capture::v1::MESSAGE_TYPE_OVERLOAD_EVENT, ov);
    (void)reason;
  });
  pipeline_->set_health_callback([this](const capture::v1::HealthSnapshot& hs) {
    emit(capture::v1::MESSAGE_TYPE_HEALTH_SNAPSHOT, hs);
  });

  CapturePipelineOptions opts;
  double nominal_fps = 30.0;
  try {
    const auto cfg_json =
        nlohmann::json::parse(config_json(req.source_id()).empty()
                                  ? "{}"
                                  : config_json(req.source_id()));
    opts.encoder_preference = cfg_json.value("encoder_preference", "auto");
    opts.preview_enabled = cfg_json.value("preview_enabled", true);
    opts.preview_max_rate_hz = cfg_json.value("preview_max_rate_hz", 10.0);
    opts.preview_quality = cfg_json.value("preview_quality", "thumbnail");
    const std::string mode_key = cfg_json.value("capture_mode", "");
    if (!mode_key.empty()) {
      for (const auto& mode : modes_for(req.source_id())) {
        if (mode.key() == mode_key) {
          opts.source_caps = mode.caps_string();
          opts.source_is_jpeg = mode.is_jpeg;
          if (mode.fps_d > 0) {
            nominal_fps = static_cast<double>(mode.fps_n) / mode.fps_d;
          }
          if (opts.preview_quality == "capture" && mode.width > 0 &&
              mode.height > 0) {
            opts.preview_width = mode.width;
            opts.preview_height = mode.height;
          }
          break;
        }
      }
    }
  } catch (...) {
  }

  std::string err;
  if (!pipeline_->prepare(*device, opts, err)) {
    reply->mutable_error()->set_code("PREPARE_FAILED");
    reply->mutable_error()->set_message(err);
    pipeline_.reset();
    return false;
  }

  CaptureStartConfig cfg;
  cfg.package_path = req.session_package_path();
  cfg.session_id = req.session_id();
  cfg.session_t0_qpc_ns = req.session_t0_qpc_ns();
  cfg.nominal_fps = nominal_fps;
  if (!pipeline_->start(cfg, err)) {
    reply->mutable_error()->set_code("START_FAILED");
    reply->mutable_error()->set_message(err);
    pipeline_.reset();
    return false;
  }
  reply->set_first_datum_session_time_ns(0);
  return true;
}

bool WorkerSession::stop_source(const std::string& source_id,
                                capture::v1::StopReply* reply) {
  if (!connected_source_id_.empty() && source_id != connected_source_id_) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("source not active");
    return false;
  }
  if (!pipeline_) {
    return true;
  }
  std::string err;
  if (!pipeline_->stop(err)) {
    reply->mutable_error()->set_code("STOP_FAILED");
    reply->mutable_error()->set_message(err);
    return false;
  }
  pipeline_.reset();
  return true;
}

bool WorkerSession::preview_descriptor(
    const std::string& source_id,
    capture::v1::GetPreviewDescriptorReply* reply) {
  if (pipeline_ && (source_id.empty() || source_id == connected_source_id_)) {
    *reply->mutable_preview() = pipeline_->preview_descriptor();
    return true;
  }
  const CameraDevice* device = find_device(source_id);
  if (device == nullptr) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("unknown camera source_id");
    return false;
  }
  capture::v1::PreviewDescriptor d;
  d.set_source_id(device->source_id);
  d.set_stream_id(device->source_id + ".video");
  d.set_kind(capture::v1::PREVIEW_KIND_IMAGE_THUMBNAIL);
  d.set_ring_slot_count(3);
  d.set_max_payload_bytes(256 * 1024);
  d.set_max_rate_hz(15.0);
  d.set_drop_policy(capture::v1::PREVIEW_DROP_POLICY_LATEST_WINS);
  d.set_content_type("image/jpeg");
  d.set_enabled(true);
  *reply->mutable_preview() = d;
  return true;
}

std::string WorkerSession::config_json(const std::string& source_id) const {
  auto it = config_json_.find(source_id);
  return it == config_json_.end() ? "{}" : it->second;
}

bool WorkerSession::get_config_schema(
    const std::string& source_id,
    capture::v1::GetConfigSchemaReply* reply) const {
  if (find_device(source_id) == nullptr) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("unknown camera source_id");
    return false;
  }
  const auto& modes = modes_for(source_id);
  nlohmann::json mode_enum = nlohmann::json::array();
  nlohmann::json mode_labels = nlohmann::json::object();
  for (const auto& mode : modes) {
    mode_enum.push_back(mode.key());
    mode_labels[mode.key()] = mode.label();
  }
  const std::string default_mode = default_capture_mode_key(modes);

  nlohmann::json schema = {
      {"$schema", "https://json-schema.org/draft/2020-12/schema"},
      {"type", "object"},
      {"title", source_id},
      {"schema_revision", "camera.gstreamer/4"},
      {"properties",
       {{"capture_mode",
         {{"type", "string"},
          {"enum", mode_enum},
          {"default", default_mode},
          {"title", "Capture mode"},
          {"description",
           "Device-reported resolution and frame rate. Restart required."},
          {"x-capture-group", "Stream"},
          {"x-capture-order", 1},
          {"x-capture-enum-labels", mode_labels},
          {"x-capture-restart-required", true}}},
        {"preview_enabled",
         {{"type", "boolean"},
          {"default", true},
          {"title", "Preview enabled"},
          {"x-capture-group", "Preview"},
          {"x-capture-order", 1}}},
        {"preview_quality",
         {{"type", "string"},
          {"enum", {"thumbnail", "capture"}},
          {"default", "thumbnail"},
          {"title", "Preview quality"},
          {"description",
           "thumbnail = 320×240 (cheap). capture = same resolution as the "
           "armed capture mode (still JPEG, still rate-capped, droppable)."},
          {"x-capture-group", "Preview"},
          {"x-capture-order", 2},
          {"x-capture-enum-labels",
           {{"thumbnail", "Thumbnail (320×240)"},
            {"capture", "Match capture mode"}}}}},
        {"preview_max_rate_hz",
         {{"type", "number"},
          {"minimum", 1},
          {"maximum", 30},
          {"default", 10},
          {"title", "Preview max rate"},
          {"x-capture-units", "Hz"},
          {"x-capture-group", "Preview"},
          {"x-capture-order", 3}}},
        {"encoder_preference",
         {{"type", "string"},
          {"enum",
           {"auto", "nvh264enc", "qsvh264enc", "amfh264enc", "mfh264enc",
            "x264enc"}},
          {"default", "auto"},
          {"title", "Encoder preference"},
          {"x-capture-group", "Encode"},
          {"x-capture-order", 1},
          {"x-capture-restart-required", true}}}}}};
  if (mode_enum.empty()) {
    schema["properties"].erase("capture_mode");
  }
  UvcControlLimits uvc;
  std::string uvc_err;
  if (const CameraDevice* dev = find_device(source_id)) {
    (void)query_uvc_limits(*dev, uvc, uvc_err);
  }
  schema["properties"]["exposure_auto"] = {
      {"type", "boolean"},
      {"default", true},
      {"title", "Auto exposure"},
      {"x-capture-group", "Image"},
      {"x-capture-order", 1}};
  schema["properties"]["exposure_time"] = {
      {"type", "integer"},
      {"minimum", uvc.exposure_min},
      {"maximum", uvc.exposure_max},
      {"default", uvc.exposure_default},
      {"title", "Exposure"},
      {"description",
       "Manual exposure in log₂ seconds (IAMCameraControl). Ignored when "
       "auto exposure is on."},
      {"x-capture-group", "Image"},
      {"x-capture-order", 2}};
  schema["properties"]["gain"] = {
      {"type", "integer"},
      {"minimum", uvc.gain_min},
      {"maximum", uvc.gain_max},
      {"default", uvc.gain_default},
      {"title", "Gain"},
      {"x-capture-group", "Image"},
      {"x-capture-order", 3}};
  const std::string current = config_json(source_id);
  try {
    const auto cur = nlohmann::json::parse(current.empty() ? "{}" : current);
    if (cur.is_object()) {
      for (auto& [name, prop] : schema["properties"].items()) {
        if (cur.contains(name)) {
          prop["default"] = cur.at(name);
        }
      }
    }
  } catch (...) {
  }
  reply->set_schema_json(schema.dump());
  reply->set_current_json(current);
  reply->set_effective_json(current.empty() ? "{}" : current);
  reply->set_schema_revision("camera.gstreamer/4");
  return true;
}

bool WorkerSession::apply_config(const capture::v1::ApplyConfigRequest& req,
                                 capture::v1::ApplyConfigReply* reply) {
  if (find_device(req.source_id()) == nullptr) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("unknown camera source_id");
    return false;
  }
  std::string text(req.configuration().begin(), req.configuration().end());
  if (text.empty()) {
    text = "{}";
  }
  nlohmann::json requested;
  try {
    requested = nlohmann::json::parse(text);
  } catch (const std::exception& ex) {
    reply->mutable_error()->set_code("BAD_REQUEST");
    reply->mutable_error()->set_message(std::string("invalid JSON: ") +
                                        ex.what());
    return false;
  }
  nlohmann::json effective = requested;
  if (!effective.contains("encoder_preference")) {
    effective["encoder_preference"] = "auto";
  }
  if (!effective.contains("preview_enabled")) {
    effective["preview_enabled"] = true;
  }
  if (!effective.contains("preview_max_rate_hz")) {
    effective["preview_max_rate_hz"] = 10;
  }
  {
    std::string q = effective.value("preview_quality", "thumbnail");
    if (q != "thumbnail" && q != "capture") {
      q = "thumbnail";
      reply->add_coerced_fields("preview_quality");
    }
    effective["preview_quality"] = q;
  }
  const auto& modes = modes_for(req.source_id());
  if (!modes.empty()) {
    const std::string fallback = default_capture_mode_key(modes);
    std::string selected = effective.value("capture_mode", fallback);
    bool known = false;
    for (const auto& mode : modes) {
      if (mode.key() == selected) {
        known = true;
        break;
      }
    }
    if (!known) {
      selected = fallback;
      reply->add_coerced_fields("capture_mode");
    }
    effective["capture_mode"] = selected;
  }
  if (!effective.contains("exposure_auto")) {
    effective["exposure_auto"] = true;
  }
  config_json_[req.source_id()] = effective.dump();
  const std::string pref = effective.value("encoder_preference", "auto");
  if (!pref.empty() && pref != "auto") {
    _putenv_s("CAPTURE_CAMERA_ENCODER", pref.c_str());
  } else {
    _putenv_s("CAPTURE_CAMERA_ENCODER", "");
  }

  // Preview size/rate can change live; capture_mode / encoder still need a
  // re-arm because they rebuild the record branch.
  if (pipeline_ != nullptr &&
      (req.source_id().empty() || req.source_id() == connected_source_id_)) {
    CapturePipelineOptions preview_opts;
    preview_opts.preview_enabled = effective.value("preview_enabled", true);
    preview_opts.preview_max_rate_hz =
        effective.value("preview_max_rate_hz", 10.0);
    preview_opts.preview_quality =
        effective.value("preview_quality", "thumbnail");
    preview_opts.preview_width = 320;
    preview_opts.preview_height = 240;
    if (preview_opts.preview_quality == "capture" && !modes.empty()) {
      const std::string mode_key = effective.value(
          "capture_mode", default_capture_mode_key(modes));
      for (const auto& mode : modes) {
        if (mode.key() == mode_key && mode.width > 0 && mode.height > 0) {
          preview_opts.preview_width = mode.width;
          preview_opts.preview_height = mode.height;
          break;
        }
      }
    }
    std::string preview_err;
    if (!pipeline_->update_preview_options(preview_opts, preview_err)) {
      std::fprintf(stderr, "camera worker: preview update failed: %s\n",
                   preview_err.c_str());
    }
  }

  const bool touch_exposure = requested.contains("exposure_auto") ||
                            requested.contains("exposure_time");
  const bool touch_gain = requested.contains("gain");
  if (const CameraDevice* d = find_device(req.source_id())) {
    if (touch_exposure || touch_gain) {
      const bool exposure_auto = effective.value("exposure_auto", true);
      std::optional<int> exposure_time;
      if (effective.contains("exposure_time") &&
          effective["exposure_time"].is_number_integer()) {
        exposure_time = effective["exposure_time"].get<int>();
      }
      std::optional<int> gain;
      if (touch_gain && effective.contains("gain") &&
          effective["gain"].is_number_integer()) {
        gain = effective["gain"].get<int>();
      }
      UvcControlLimits limits;
      std::string limits_err;
      if (query_uvc_limits(*d, limits, limits_err)) {
        if (exposure_time.has_value()) {
          exposure_time = std::clamp(*exposure_time, limits.exposure_min,
                                     limits.exposure_max);
          effective["exposure_time"] = *exposure_time;
        }
        if (gain.has_value()) {
          gain = std::clamp(*gain, limits.gain_min, limits.gain_max);
          effective["gain"] = *gain;
        }
      }
      std::string uvc_err;
      if (!apply_uvc_controls(*d, exposure_auto,
                               exposure_auto ? std::nullopt : exposure_time,
                               gain, uvc_err)) {
        std::fprintf(stderr, "camera worker: UVC control apply failed: %s\n",
                     uvc_err.c_str());
      }
      config_json_[req.source_id()] = effective.dump();
    }
  }

  reply->set_requested_json(text);
  reply->set_effective_json(effective.dump());
  reply->set_schema_revision("camera.gstreamer/4");
  if (const CameraDevice* d = find_device(req.source_id())) {
    fill_source(*d, reply->mutable_source());
  }
  return true;
}

}  // namespace capture::camera_worker
