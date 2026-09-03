// SPDX-License-Identifier: GPL-3.0-only
#include "radar_worker/worker_session.hpp"

#include "capture/v1/health.pb.h"

#include <ifxBase/Version.h>

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cmath>

namespace capture::radar_worker {

WorkerSession::WorkerSession(std::string plugin_id)
    : plugin_id_(std::move(plugin_id)) {
  if (const char* ver = ifx_sdk_get_version_string_full()) {
    sdk_version_ = ver;
  }
}

void WorkerSession::refresh_devices() {
  devices_.clear();
  for (const auto& board : enumerate_fmcw_boards()) {
    DeviceEntry entry;
    entry.board = board;
    entry.source_id = source_id_from_uuid(board.uuid);
    devices_.push_back(std::move(entry));
  }
  for (const auto& board : enumerate_ltr11_boards()) {
    DeviceEntry entry;
    entry.board = board;
    entry.source_id = source_id_from_uuid(board.uuid);
    devices_.push_back(std::move(entry));
  }
}

void WorkerSession::close_device() {
  fmcw_device_.reset();
  ltr11_device_.reset();
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

void WorkerSession::fill_source(const DeviceEntry& entry,
                                capture::v1::SourceInstance* out) const {
  const bool is_ltr11 = entry.board.kind == BoardKind::Ltr11;
  out->set_source_id(entry.source_id);
  out->set_source_type("radar");
  const std::string alias = entry.board.sensor_description.empty()
                                ? entry.source_id
                                : entry.board.sensor_description;
  out->set_alias(alias);
  out->set_plugin_id(plugin_id_);
  out->set_plugin_version("0.1.0");
  out->set_enabled(true);
  out->set_lifecycle_state(capture::v1::SOURCE_LIFECYCLE_DISCOVERED);
  (*out->mutable_metadata())["modality"] =
      is_ltr11 ? "radar_doppler" : "radar";
  (*out->mutable_metadata())["record_stack"] =
      is_ltr11 ? "ifx_ltr11" : "ifx_fmcw";
  (*out->mutable_metadata())["ifx_sdk_version"] = sdk_version_;

  auto* phys = out->add_physical_devices();
  phys->set_vendor("Infineon");
  phys->set_model(entry.board.sensor_description.empty()
                      ? (is_ltr11 ? "BGT60LTR11AIP" : "BGT60TR13C")
                      : entry.board.sensor_description);
  phys->set_stable_device_key(entry.board.uuid);
  phys->set_connection_path(entry.board.uuid);
  out->add_physical_device_ids(entry.board.uuid);

  auto* stream = out->add_streams();
  stream->set_stream_id(entry.source_id + ".frame");
  stream->set_source_id(entry.source_id);
  if (is_ltr11) {
    stream->set_modality("radar_doppler");
    stream->set_nominal_rate_hz(7.8);
    stream->set_data_schema_id("radar.doppler/1");
  } else {
    stream->set_modality("radar");
    stream->set_nominal_rate_hz(20.0);
    stream->set_data_schema_id("radar.frame/1");
  }
}

capture::v1::SourceManifest WorkerSession::build_manifest() const {
  capture::v1::SourceManifest manifest;
  manifest.set_plugin_id(plugin_id_);
  manifest.set_plugin_version("0.1.0");
  (*manifest.mutable_capabilities())["isolation"] = "per_source";
  (*manifest.mutable_capabilities())["record_stack"] = "ifx_fmcw,ifx_ltr11";
  (*manifest.mutable_capabilities())["ifx_sdk_version"] = sdk_version_;
  for (const auto& entry : devices_) {
    fill_source(entry, manifest.add_sources());
  }
  return manifest;
}

void WorkerSession::fill_discover(capture::v1::DiscoverReply* reply) const {
  for (const auto& entry : devices_) {
    fill_source(entry, reply->add_sources());
  }
}

const WorkerSession::DeviceEntry* WorkerSession::find_device(
    const std::string& source_id) const {
  for (const auto& entry : devices_) {
    if (entry.source_id == source_id) {
      return &entry;
    }
  }
  return nullptr;
}

FmcwSequenceConfig WorkerSession::fmcw_sequence_config(
    const std::string& source_id) const {
  FmcwSequenceConfig out;
  try {
    const auto text = config_json(source_id);
    const auto cfg = nlohmann::json::parse(text.empty() ? "{}" : text);
    out.frame_repetition_time_s =
        cfg.value("frame_repetition_time_s", out.frame_repetition_time_s);
    out.chirp_repetition_time_s =
        cfg.value("chirp_repetition_time_s", out.chirp_repetition_time_s);
    out.num_chirps = cfg.value("num_chirps", out.num_chirps);
    out.start_frequency_Hz =
        cfg.value("start_frequency_Hz", out.start_frequency_Hz);
    out.end_frequency_Hz =
        cfg.value("end_frequency_Hz", out.end_frequency_Hz);
    out.sample_rate_Hz = cfg.value("sample_rate_Hz", out.sample_rate_Hz);
    out.num_samples = cfg.value("num_samples", out.num_samples);
    out.rx_mask = cfg.value("rx_mask", out.rx_mask);
    out.tx_mask = cfg.value("tx_mask", out.tx_mask);
    out.tx_power_level = cfg.value("tx_power_level", out.tx_power_level);
    out.lp_cutoff_Hz = cfg.value("lp_cutoff_Hz", out.lp_cutoff_Hz);
    out.hp_cutoff_Hz = cfg.value("hp_cutoff_Hz", out.hp_cutoff_Hz);
    out.if_gain_dB = cfg.value("if_gain_dB", out.if_gain_dB);
  } catch (...) {
  }
  return out;
}

bool WorkerSession::connect_source(const std::string& source_id,
                                   capture::v1::ConnectReply* reply) {
  const DeviceEntry* entry = find_device(source_id);
  if (entry == nullptr) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("unknown radar source_id");
    return false;
  }
  close_device();
  std::string err;
  if (entry->board.kind == BoardKind::Ltr11) {
    ltr11_device_ = std::make_unique<IfxLtr11Device>();
    if (!ltr11_device_->open(entry->board.uuid, err)) {
      reply->mutable_error()->set_code("CONNECT_FAILED");
      reply->mutable_error()->set_message(err);
      ltr11_device_.reset();
      return false;
    }
    if (!ltr11_device_->apply_defaults(err)) {
      reply->mutable_error()->set_code("CONNECT_FAILED");
      reply->mutable_error()->set_message(err);
      ltr11_device_.reset();
      return false;
    }
    connected_kind_ = BoardKind::Ltr11;
  } else {
    fmcw_device_ = std::make_unique<IfxFmcwDevice>();
    if (!fmcw_device_->open(entry->board.uuid, err)) {
      reply->mutable_error()->set_code("CONNECT_FAILED");
      reply->mutable_error()->set_message(err);
      fmcw_device_.reset();
      return false;
    }
    if (!fmcw_device_->apply_sequence(fmcw_sequence_config(source_id), err)) {
      reply->mutable_error()->set_code("CONNECT_FAILED");
      reply->mutable_error()->set_message(err);
      fmcw_device_.reset();
      return false;
    }
    connected_kind_ = BoardKind::Fmcw;
  }
  connected_source_id_ = source_id;
  fill_source(*entry, reply->mutable_source());
  reply->mutable_source()->set_lifecycle_state(
      capture::v1::SOURCE_LIFECYCLE_CONNECTED);
  const std::string hash =
      connected_kind_ == BoardKind::Ltr11
          ? ltr11_device_->configuration_hash()
          : fmcw_device_->configuration_hash();
  (*reply->mutable_source()->mutable_metadata())["configuration_hash"] = hash;
  return true;
}

bool WorkerSession::start_source(const capture::v1::StartRequest& req,
                                 capture::v1::StartReply* reply) {
  const DeviceEntry* entry = find_device(req.source_id());
  if (entry == nullptr) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("unknown radar source_id");
    return false;
  }
  if (req.session_package_path().empty()) {
    reply->mutable_error()->set_code("BAD_REQUEST");
    reply->mutable_error()->set_message("session_package_path required");
    return false;
  }

  if ((connected_kind_ == BoardKind::Fmcw && !fmcw_device_) ||
      (connected_kind_ == BoardKind::Ltr11 && !ltr11_device_) ||
      connected_source_id_ != req.source_id()) {
    capture::v1::ConnectReply connect;
    if (!connect_source(req.source_id(), &connect)) {
      reply->mutable_error()->CopyFrom(connect.error());
      return false;
    }
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
    std::fprintf(stderr, "radar worker overload: %s\n", reason.c_str());
    capture::v1::OverloadEvent ov;
    ov.set_source_id(connected_source_id_);
    ov.set_stream_id(connected_source_id_ + ".frame");
    ov.set_session_time_ns(0);
    ov.set_queue_occupancy(1.0);
    ov.set_dropped_count(1);
    emit(capture::v1::MESSAGE_TYPE_OVERLOAD_EVENT, ov);
  });
  pipeline_->set_health_callback([this](const capture::v1::HealthSnapshot& hs) {
    emit(capture::v1::MESSAGE_TYPE_HEALTH_SNAPSHOT, hs);
  });

  std::string err;
  if (!pipeline_->prepare(req.source_id(), connected_kind_, fmcw_device_.get(),
                          ltr11_device_.get(), err)) {
    reply->mutable_error()->set_code("PREPARE_FAILED");
    reply->mutable_error()->set_message(err);
    pipeline_.reset();
    return false;
  }
  try {
    const auto cfg_json =
        nlohmann::json::parse(config_json(req.source_id()).empty()
                                  ? "{}"
                                  : config_json(req.source_id()));
    if (cfg_json.contains("preview_view") &&
        cfg_json.at("preview_view").is_string()) {
      pipeline_->set_preview_view(cfg_json.at("preview_view").get<std::string>());
    }
  } catch (...) {
  }

  CaptureStartConfig cfg;
  cfg.package_path = req.session_package_path();
  cfg.session_id = req.session_id();
  cfg.session_t0_qpc_ns = req.session_t0_qpc_ns();
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
  if (!connected_source_id_.empty() && !source_id.empty() &&
      source_id != connected_source_id_) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("source not active");
    return false;
  }
  if (pipeline_) {
    std::string err;
    if (!pipeline_->stop(err)) {
      reply->mutable_error()->set_code("STOP_FAILED");
      reply->mutable_error()->set_message(err);
      return false;
    }
    pipeline_.reset();
  }
  close_device();
  connected_source_id_.clear();
  return true;
}

bool WorkerSession::preview_descriptor(
    const std::string& source_id,
    capture::v1::GetPreviewDescriptorReply* reply) {
  if (pipeline_ && (source_id.empty() || source_id == connected_source_id_)) {
    *reply->mutable_preview() = pipeline_->preview_descriptor();
    return true;
  }
  const DeviceEntry* entry = find_device(source_id);
  if (entry == nullptr) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("unknown radar source_id");
    return false;
  }
  capture::v1::PreviewDescriptor d;
  d.set_source_id(entry->source_id);
  d.set_stream_id(entry->source_id + ".frame");
  d.set_ring_slot_count(3);
  d.set_max_rate_hz(5.0);
  d.set_drop_policy(capture::v1::PREVIEW_DROP_POLICY_LATEST_WINS);
  d.set_enabled(true);
  if (entry->board.kind == BoardKind::Ltr11) {
    d.set_kind(capture::v1::PREVIEW_KIND_TRACE_BLOCK);
    d.set_max_payload_bytes(64 * static_cast<uint32_t>(sizeof(float)));
    d.set_content_type("application/x-capture-trace");
  } else {
    d.set_kind(capture::v1::PREVIEW_KIND_MATRIX_2D);
    d.set_max_payload_bytes(128 * 128 * static_cast<uint32_t>(sizeof(float)));
    d.set_content_type("application/x-capture-matrix");
  }
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
  const DeviceEntry* entry = find_device(source_id);
  if (entry == nullptr) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("unknown radar source_id");
    return false;
  }
  const std::string current = config_json(source_id);
  nlohmann::json cur = nlohmann::json::object();
  try {
    cur = nlohmann::json::parse(current.empty() ? "{}" : current);
  } catch (...) {
  }

  if (entry->board.kind == BoardKind::Ltr11) {
    const std::string view_default =
        cur.value("preview_view", "motion_trace");
    nlohmann::json schema = {
        {"$schema", "https://json-schema.org/draft/2020-12/schema"},
        {"type", "object"},
        {"title", source_id},
        {"schema_revision", "radar.ifx/3"},
        {"properties",
         {{"preview_view",
           {{"type", "string"},
            {"enum", {"motion_trace", "doppler_spectrogram"}},
            {"default", view_default},
            {"title", "Preview view"},
            {"description",
             "Derived Fusion-style preview (not recorded)."},
            {"x-capture-group", "Preview"},
            {"x-capture-order", 1},
            {"x-capture-enum-labels",
             {{"motion_trace", "Motion trace"},
              {"doppler_spectrogram", "Doppler spectrogram"}}}}}}}};
    reply->set_schema_json(schema.dump());
    reply->set_current_json(current);
    reply->set_effective_json(current.empty() ? "{}" : current);
    reply->set_schema_revision("radar.ifx/3");
    return true;
  }

  const FmcwSequenceConfig dflt = fmcw_sequence_config(source_id);
  const std::string view_default =
      cur.value("preview_view", "range_doppler");
  auto restart_num = [](const char* title, const char* group, int order,
                        const char* units, double minimum, double maximum,
                        double def) {
    nlohmann::json p = {{"type", "number"},
                        {"minimum", minimum},
                        {"maximum", maximum},
                        {"default", def},
                        {"title", title},
                        {"x-capture-group", group},
                        {"x-capture-order", order},
                        {"x-capture-restart-required", true}};
    if (units != nullptr && units[0] != '\0') {
      p["x-capture-units"] = units;
    }
    return p;
  };
  auto restart_int = [](const char* title, const char* group, int order,
                        int minimum, int maximum, int def) {
    return nlohmann::json{{"type", "integer"},
                          {"minimum", minimum},
                          {"maximum", maximum},
                          {"default", def},
                          {"title", title},
                          {"x-capture-group", group},
                          {"x-capture-order", order},
                          {"x-capture-restart-required", true}};
  };
  nlohmann::json schema = {
      {"$schema", "https://json-schema.org/draft/2020-12/schema"},
      {"type", "object"},
      {"title", source_id},
      {"schema_revision", "radar.ifx/3"},
      {"properties",
       {{"frame_repetition_time_s",
         restart_num("Frame repetition time", "Timing", 1, "s", 0.01, 1.0,
                     dflt.frame_repetition_time_s)},
        {"chirp_repetition_time_s",
         restart_num("Chirp repetition time", "Timing", 2, "s", 1e-6, 1e-2,
                     dflt.chirp_repetition_time_s)},
        {"num_chirps",
         restart_int("Chirps per frame", "Geometry", 3, 1, 512,
                     static_cast<int>(dflt.num_chirps))},
        {"num_samples",
         restart_int("Samples per chirp", "Geometry", 4, 32, 4095,
                     static_cast<int>(dflt.num_samples))},
        {"start_frequency_Hz",
         restart_num("Start frequency", "RF", 5, "Hz", 58e9, 63.5e9,
                     dflt.start_frequency_Hz)},
        {"end_frequency_Hz",
         restart_num("End frequency", "RF", 6, "Hz", 58e9, 63.5e9,
                     dflt.end_frequency_Hz)},
        {"sample_rate_Hz",
         restart_num("ADC sample rate", "RF", 7, "Hz", 78200, 4e6,
                     dflt.sample_rate_Hz)},
        {"rx_mask",
         restart_int("RX antenna mask", "Antennas", 8, 1, 7,
                     static_cast<int>(dflt.rx_mask))},
        {"tx_mask",
         restart_int("TX antenna mask", "Antennas", 9, 1, 1,
                     static_cast<int>(dflt.tx_mask))},
        {"tx_power_level",
         restart_int("TX power level", "Antennas", 10, 0, 31,
                     static_cast<int>(dflt.tx_power_level))},
        {"if_gain_dB",
         restart_int("IF gain", "Analog", 11, 18, 60,
                     static_cast<int>(dflt.if_gain_dB))},
        {"lp_cutoff_Hz",
         restart_int("LP cutoff", "Analog", 12, 500000, 500000,
                     static_cast<int>(dflt.lp_cutoff_Hz))},
        {"hp_cutoff_Hz",
         restart_int("HP cutoff", "Analog", 13, 20000, 80000,
                     static_cast<int>(dflt.hp_cutoff_Hz))},
        {"preview_view",
         {{"type", "string"},
          {"enum",
           {"range_doppler", "range_doppler_hd", "range_spectrum",
            "range_spectrogram", "time_domain"}},
          {"default", view_default},
          {"title", "Preview view"},
          {"description",
           "Derived Fusion-style preview (not recorded)."},
          {"x-capture-group", "Preview"},
          {"x-capture-order", 20},
          {"x-capture-enum-labels",
           {{"range_doppler", "Range-Doppler"},
            {"range_doppler_hd", "Range-Doppler (HD)"},
            {"range_spectrum", "Range spectrum"},
            {"range_spectrogram", "Range spectrogram"},
            {"time_domain", "Time domain"}}}}}}}};
  reply->set_schema_json(schema.dump());
  reply->set_current_json(current);
  reply->set_effective_json(current.empty() ? "{}" : current);
  reply->set_schema_revision("radar.ifx/3");
  return true;
}

bool WorkerSession::apply_config(const capture::v1::ApplyConfigRequest& req,
                                 capture::v1::ApplyConfigReply* reply) {
  const DeviceEntry* entry = find_device(req.source_id());
  if (entry == nullptr) {
    reply->mutable_error()->set_code("NOT_FOUND");
    reply->mutable_error()->set_message("unknown radar source_id");
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

  nlohmann::json effective = nlohmann::json::object();
  try {
    effective = nlohmann::json::parse(config_json(req.source_id()).empty()
                                          ? "{}"
                                          : config_json(req.source_id()));
  } catch (...) {
  }
  if (!effective.is_object()) {
    effective = nlohmann::json::object();
  }
  for (auto it = requested.begin(); it != requested.end(); ++it) {
    effective[it.key()] = it.value();
  }

  if (entry->board.kind == BoardKind::Ltr11) {
    static const char* kLtr11Views[] = {"motion_trace", "doppler_spectrogram"};
    std::string view = effective.value("preview_view", "motion_trace");
    bool ok = false;
    for (const char* v : kLtr11Views) {
      if (view == v) {
        ok = true;
        break;
      }
    }
    if (!ok) {
      view = "motion_trace";
      reply->add_coerced_fields("preview_view");
    }
    effective = {{"preview_view", view}};
    const std::string eff = effective.dump();
    config_json_[req.source_id()] = eff;
    if (pipeline_ &&
        (req.source_id().empty() || req.source_id() == connected_source_id_)) {
      pipeline_->set_preview_view(view);
    }
    reply->set_requested_json(text);
    reply->set_effective_json(eff);
    reply->set_schema_revision("radar.ifx/3");
    fill_source(*entry, reply->mutable_source());
    return true;
  }

  const FmcwSequenceConfig prev_seq = fmcw_sequence_config(req.source_id());
  FmcwSequenceConfig seq;
  auto clamp_d = [&](const char* key, double lo, double hi, double& dst) {
    dst = effective.value(key, dst);
    if (dst < lo || dst > hi) {
      dst = (std::max)(lo, (std::min)(hi, dst));
      reply->add_coerced_fields(key);
    }
    effective[key] = dst;
  };
  auto clamp_u = [&](const char* key, uint32_t lo, uint32_t hi, uint32_t& dst) {
    dst = effective.value(key, dst);
    if (dst < lo || dst > hi) {
      dst = (std::max)(lo, (std::min)(hi, dst));
      reply->add_coerced_fields(key);
    }
    effective[key] = dst;
  };
  clamp_d("frame_repetition_time_s", 0.01, 1.0, seq.frame_repetition_time_s);
  clamp_d("chirp_repetition_time_s", 1e-6, 1e-2, seq.chirp_repetition_time_s);
  clamp_u("num_chirps", 1, 512, seq.num_chirps);
  clamp_u("num_samples", 32, 4095, seq.num_samples);
  clamp_d("start_frequency_Hz", 58e9, 63.5e9, seq.start_frequency_Hz);
  clamp_d("end_frequency_Hz", 58e9, 63.5e9, seq.end_frequency_Hz);
  if (seq.end_frequency_Hz <= seq.start_frequency_Hz) {
    seq.end_frequency_Hz = seq.start_frequency_Hz + 0.5e9;
    reply->add_coerced_fields("end_frequency_Hz");
    effective["end_frequency_Hz"] = seq.end_frequency_Hz;
  }
  clamp_d("sample_rate_Hz", 78200.0, 4e6, seq.sample_rate_Hz);
  clamp_u("rx_mask", 1, 7, seq.rx_mask);
  clamp_u("tx_mask", 1, 1, seq.tx_mask);
  clamp_u("tx_power_level", 0, 31, seq.tx_power_level);
  clamp_u("if_gain_dB", 18, 60, seq.if_gain_dB);
  clamp_u("lp_cutoff_Hz", 500000, 500000, seq.lp_cutoff_Hz);
  // Board supports discrete HP cutoffs; coerce to nearest of {20,45,70,80} kHz.
  {
    uint32_t hp = effective.value("hp_cutoff_Hz", seq.hp_cutoff_Hz);
    static const uint32_t kHp[] = {20000, 45000, 70000, 80000};
    uint32_t best = kHp[0];
    uint32_t best_d = (hp > best) ? (hp - best) : (best - hp);
    for (uint32_t cand : kHp) {
      const uint32_t d = (hp > cand) ? (hp - cand) : (cand - hp);
      if (d < best_d) {
        best = cand;
        best_d = d;
      }
    }
    if (best != hp) {
      reply->add_coerced_fields("hp_cutoff_Hz");
    }
    seq.hp_cutoff_Hz = best;
    effective["hp_cutoff_Hz"] = best;
  }

  static const char* kFmcwViews[] = {"range_doppler", "range_doppler_hd",
                                     "range_spectrum", "range_spectrogram",
                                     "time_domain"};
  std::string view = effective.value("preview_view", "range_doppler");
  bool view_ok = false;
  for (const char* v : kFmcwViews) {
    if (view == v) {
      view_ok = true;
      break;
    }
  }
  if (!view_ok) {
    view = "range_doppler";
    reply->add_coerced_fields("preview_view");
  }
  effective["preview_view"] = view;

  const std::string eff = effective.dump();
  config_json_[req.source_id()] = eff;

  const bool seq_changed =
      std::abs(seq.frame_repetition_time_s - prev_seq.frame_repetition_time_s) >
          1e-12 ||
      std::abs(seq.chirp_repetition_time_s - prev_seq.chirp_repetition_time_s) >
          1e-12 ||
      seq.num_chirps != prev_seq.num_chirps ||
      seq.num_samples != prev_seq.num_samples ||
      std::abs(seq.start_frequency_Hz - prev_seq.start_frequency_Hz) > 1.0 ||
      std::abs(seq.end_frequency_Hz - prev_seq.end_frequency_Hz) > 1.0 ||
      std::abs(seq.sample_rate_Hz - prev_seq.sample_rate_Hz) > 1.0 ||
      seq.rx_mask != prev_seq.rx_mask || seq.tx_mask != prev_seq.tx_mask ||
      seq.tx_power_level != prev_seq.tx_power_level ||
      seq.if_gain_dB != prev_seq.if_gain_dB ||
      seq.lp_cutoff_Hz != prev_seq.lp_cutoff_Hz ||
      seq.hp_cutoff_Hz != prev_seq.hp_cutoff_Hz;

  if (seq_changed && fmcw_device_ != nullptr &&
      (req.source_id().empty() || req.source_id() == connected_source_id_)) {
    if (pipeline_) {
      reply->mutable_error()->set_code("RESTART_REQUIRED");
      reply->mutable_error()->set_message(
          "chirp geometry changes require stopping capture first");
      return false;
    }
    std::string err;
    if (!fmcw_device_->apply_sequence(seq, err)) {
      reply->mutable_error()->set_code("APPLY_FAILED");
      reply->mutable_error()->set_message(err);
      return false;
    }
  }
  if (pipeline_ &&
      (req.source_id().empty() || req.source_id() == connected_source_id_)) {
    pipeline_->set_preview_view(view);
  }

  reply->set_requested_json(text);
  reply->set_effective_json(eff);
  reply->set_schema_revision("radar.ifx/3");
  fill_source(*entry, reply->mutable_source());
  return true;
}

}  // namespace capture::radar_worker
