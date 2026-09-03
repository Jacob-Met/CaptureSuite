// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/sim_engine.hpp"

#include "capture/logging.hpp"
#include "capture/storage/recovery.hpp"

#include "capture/v1/data/emg_batch.pb.h"
#include "capture/v1/data/imu_frame.pb.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_set>
#include <utility>

namespace capture::daemon {
namespace {

std::string make_id(const char* prefix) {
  static std::atomic<uint64_t> counter{1};
  return std::string(prefix) + "-" + std::to_string(counter.fetch_add(1));
}

// Soft phones / OBS-style devices show up in MF even when nothing is streaming.
// Leave them unselected by default so StartAllReady does not spend seconds
// spawning workers for a dead pipe; the operator can still select them when the
// upstream app is running.
void fill_sim_imu_payload(capture::storage::SamplePoint& pt,
                          const std::vector<std::string>& sensor_ids) {
  capture::v1::data::ImuFrame msg;
  auto* t = msg.mutable_timing();
  t->set_sequence_number(pt.sequence);
  t->set_host_arrival_ns(pt.host_arrival_ns);
  t->set_session_time_ns(pt.session_time_ns);
  t->set_quality_flags(pt.quality_flags);
  msg.set_frame_index(pt.sequence);
  msg.set_quality_flags(pt.quality_flags);
  const double phase = static_cast<double>(pt.sequence) * 0.02;
  for (size_t i = 0; i < sensor_ids.size(); ++i) {
    auto* s = msg.add_sensors();
    s->set_sensor_id(sensor_ids[i]);
    const double tt = phase + static_cast<double>(i) * 0.15;
    s->set_qw(static_cast<float>(std::cos(tt * 0.5)));
    s->set_qx(0.f);
    s->set_qy(static_cast<float>(std::sin(tt * 0.5)));
    s->set_qz(0.f);
    s->set_accel_x(0.f);
    s->set_accel_y(0.f);
    s->set_accel_z(static_cast<float>(9.81 + 0.2 * std::sin(tt * 3.0)));
    s->set_gyro_x(0.f);
    s->set_gyro_y(static_cast<float>(0.1 + 0.05 * std::cos(tt * 2.0)));
    s->set_gyro_z(0.f);
  }
  const auto bytes = msg.SerializeAsString();
  pt.payload.assign(bytes.begin(), bytes.end());
}

void fill_sim_emg_payload(capture::storage::SamplePoint& pt, int channel_count,
                          int sample_count, int64_t first_sequence) {
  capture::v1::data::EmgBatch msg;
  auto* t = msg.mutable_timing();
  t->set_sequence_number(pt.sequence);
  t->set_host_arrival_ns(pt.host_arrival_ns);
  t->set_session_time_ns(pt.session_time_ns);
  t->set_quality_flags(pt.quality_flags);
  msg.set_first_sample_index(first_sequence);
  msg.set_sample_count(sample_count);
  for (int c = 0; c < channel_count; ++c) {
    msg.add_channel_ids("ch" + std::to_string(c));
  }
  const size_t n = static_cast<size_t>(channel_count) * sample_count;
  std::string samples;
  samples.resize(n * sizeof(float));
  auto* f = reinterpret_cast<float*>(samples.data());
  for (int c = 0; c < channel_count; ++c) {
    for (int i = 0; i < sample_count; ++i) {
      const float phase =
          static_cast<float>(first_sequence + i) * 0.08f + c * 0.4f;
      f[static_cast<size_t>(c) * sample_count + i] = std::sin(phase) * 0.7f;
    }
  }
  msg.set_samples_f32_le(samples);
  msg.set_quality_flags(pt.quality_flags);
  const auto bytes = msg.SerializeAsString();
  pt.payload.assign(bytes.begin(), bytes.end());
}

bool looks_like_virtual_camera(std::string name) {
  for (char& c : name) {
    c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
  }
  static constexpr const char* kNeedles[] = {
      "iriun",         "droidcam",       "camo",
      "obs virtual",   "obs-camera",     "obs camera",
      "manycam",       "snap camera",    "nvidia broadcast",
      "xsplit",        "vcam",           "virtual camera",
      "virtual webcam", "epoccam",       "unity capture",
  };
  for (const char* needle : kNeedles) {
    if (name.find(needle) != std::string::npos) {
      return true;
    }
  }
  return false;
}

// Higher is better for the single default-selected camera. Prefer a real USB
// webcam (e.g. MX Brio) over the laptop FHD module; never prefer virtual cams.
// Interim live radar preview bridge (M6 spike). When CAPTURE_IFX_PREVIEW=1 and
// tools/vendor_spike/ifx_live_preview.py is pumping matrix.f32, replace the
// synthetic MATRIX_2D for sim.radar.1 with the real BGT60TR13C range-Doppler.
bool try_load_ifx_radar_preview(PreviewFrameData& f,
                                const std::string& source_id) {
  if (source_id != "sim.radar.1") {
    return false;
  }
  char* flag = nullptr;
  size_t flag_len = 0;
  if (_dupenv_s(&flag, &flag_len, "CAPTURE_IFX_PREVIEW") != 0 ||
      flag == nullptr) {
    return false;
  }
  const bool enabled =
      std::strcmp(flag, "1") == 0 || _stricmp(flag, "true") == 0;
  free(flag);
  if (!enabled) {
    return false;
  }

  std::filesystem::path dir;
  char* override_dir = nullptr;
  size_t od_len = 0;
  if (_dupenv_s(&override_dir, &od_len, "CAPTURE_IFX_PREVIEW_DIR") == 0 &&
      override_dir != nullptr) {
    dir = override_dir;
    free(override_dir);
  } else {
    char* local = nullptr;
    size_t local_len = 0;
    if (_dupenv_s(&local, &local_len, "LOCALAPPDATA") != 0 || local == nullptr) {
      return false;
    }
    dir = std::filesystem::path(local) / "CaptureSuite" / "ifx_radar_preview";
    free(local);
  }
  const auto meta_path = dir / "meta.json";
  const auto mat_path = dir / "matrix.f32";
  std::error_code ec;
  if (!std::filesystem::exists(meta_path, ec) ||
      !std::filesystem::exists(mat_path, ec)) {
    return false;
  }
  const auto age = std::filesystem::file_time_type::clock::now() -
                   std::filesystem::last_write_time(meta_path, ec);
  if (ec) {
    return false;
  }
  // Drop stale frames so a stopped pump does not freeze the last map forever.
  if (age > std::chrono::milliseconds(750)) {
    return false;
  }

  try {
    std::ifstream meta_in(meta_path);
    nlohmann::json meta = nlohmann::json::parse(meta_in);
    const uint32_t rows = meta.value("rows", 0u);
    const uint32_t cols = meta.value("cols", 0u);
    if (rows == 0 || cols == 0 || rows > 256 || cols > 512) {
      return false;
    }
    const auto nbytes = static_cast<std::uintmax_t>(rows) * cols * sizeof(float);
    if (std::filesystem::file_size(mat_path, ec) < nbytes || ec) {
      return false;
    }
    std::ifstream mat_in(mat_path, std::ios::binary);
    std::vector<float> values(static_cast<size_t>(rows) * cols);
    mat_in.read(reinterpret_cast<char*>(values.data()),
                static_cast<std::streamsize>(nbytes));
    if (!mat_in) {
      return false;
    }
    f.rows = rows;
    f.cols = cols;
    f.display_min = meta.value("display_min", 0.0f);
    f.display_max = meta.value("display_max", 1.0f);
    f.samples = std::move(values);
    if (meta.contains("sequence")) {
      f.sequence = meta["sequence"].get<int64_t>();
    }
    return true;
  } catch (...) {
    return false;
  }
}

int camera_default_score(const SimSourceDesc& src) {
  if (!src.is_camera || src.is_virtual_camera) {
    return -1000;
  }
  std::string name = src.alias;
  std::string key = src.stable_device_key;
  for (char& c : name) {
    c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
  }
  for (char& c : key) {
    c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
  }
  int score = 100;
  if (key.find("usb#") != std::string::npos) {
    score += 50;
  }
  if (name.find("brio") != std::string::npos ||
      name.find("logitech") != std::string::npos) {
    score += 20;
  }
  if (name.find("fhd camera") != std::string::npos ||
      name.find("integrated") != std::string::npos ||
      name.find("ir camera") != std::string::npos) {
    score -= 30;
  }
  return score;
}

std::filesystem::path default_package_parent() {
  char* session_parent = nullptr;
  size_t sp_len = 0;
  if (_dupenv_s(&session_parent, &sp_len, "CAPTURE_SESSION_PARENT") == 0 &&
      session_parent != nullptr) {
    std::filesystem::path p(session_parent);
    free(session_parent);
    return p;
  }
  char* local = nullptr;
  size_t len = 0;
  if (_dupenv_s(&local, &len, "LOCALAPPDATA") == 0 && local != nullptr) {
    std::filesystem::path p =
        std::filesystem::path(local) / "CaptureSuite" / "sessions";
    free(local);
    return p;
  }
  return std::filesystem::temp_directory_path() / "CaptureSuite" / "sessions";
}

int64_t env_rotate_bytes_or(int64_t fallback) {
  char* rotate = nullptr;
  size_t len = 0;
  if (_dupenv_s(&rotate, &len, "CAPTURE_TEST_ROTATE_BYTES") == 0 &&
      rotate != nullptr) {
    const int64_t v = std::strtoll(rotate, nullptr, 10);
    free(rotate);
    if (v > 0) {
      return v;
    }
  }
  return fallback;
}

float hash_noise(int64_t seq, int channel) {
  const uint32_t x = static_cast<uint32_t>(seq * 1103515245u + channel * 12345u);
  return static_cast<float>((x % 1000) / 1000.0 * 2.0 - 1.0);
}

}  // namespace

SimEngine::SimEngine() {
  package_parent_ = default_package_parent();
  rotate_bytes_ = env_rotate_bytes_or(rotate_bytes_);
  if (CameraWorkerBridge::should_enable()) {
    camera_workers_ = std::make_unique<CameraWorkerBridge>("capture-daemon");
    capture::log::info(
        "camera_worker_bridge",
        CameraWorkerBridge::forced_off()
            ? "camera workers disabled"
            : "out-of-process camera workers enabled (auto or forced)");
  }
  if (RadarWorkerBridge::should_enable()) {
    radar_workers_ = std::make_unique<RadarWorkerBridge>("capture-daemon");
    capture::log::info(
        "radar_worker_bridge",
        RadarWorkerBridge::forced_off()
            ? "radar workers disabled"
            : "out-of-process radar workers enabled (auto or forced)");
  }
  ensure_default_sources();
}

std::string SimEngine::camera_worker_encoder() const {
  if (!camera_workers_) {
    return {};
  }
  return camera_workers_->preferred_encoder();
}

SimEngine::~SimEngine() {
  stop_recording_thread();
  stop_preview_thread();
  if (camera_workers_) {
    camera_workers_->stop_all();
  }
  if (radar_workers_) {
    radar_workers_->stop_all();
  }
  for (auto& [id, cam] : cameras_) {
    (void)id;
    if (cam) {
      cam->stop();
      cam->close();
    }
  }
}

void SimEngine::set_package_parent(std::filesystem::path parent) {
  std::lock_guard lock(mu_);
  package_parent_ = std::move(parent);
}

void SimEngine::set_rotate_bytes(int64_t bytes) {
  std::lock_guard lock(mu_);
  rotate_bytes_ = bytes;
}

void SimEngine::set_descriptor_set_path(std::filesystem::path path) {
  std::lock_guard lock(mu_);
  descriptor_set_path_ = std::move(path);
}

void SimEngine::ensure_default_sources() {
  sources_.clear();
  fsms_.clear();
  preview_cfg_.clear();
  preview_slots_.clear();
  cameras_.clear();

  // Real cameras first when available; otherwise a simulated camera source.
  const auto cams = CameraCapture::enumerate();
  if (!cams.empty()) {
    for (const auto& cam : cams) {
      SimSourceDesc src;
      src.source_id = cam.source_id;
      src.source_type = "camera";
      src.alias = cam.friendly_name.empty() ? cam.source_id : cam.friendly_name;
      src.modality = "video";
      src.stream_id = cam.source_id + ".video";
      src.nominal_rate_hz = 30.0;
      src.is_camera = true;
      src.is_virtual_camera = looks_like_virtual_camera(
          src.alias.empty() ? cam.friendly_name : src.alias);
      src.stable_device_key = cam.stable_device_key;
      src.vendor = cam.vendor;
      src.model = cam.model;
      src.serial = cam.stable_device_key;
      src.camera_symbolic_link = cam.symbolic_link;
      src.plugin_id = camera_workers_ ? "camera.gstreamer" : "camera.mf";
      src.data_schema_id = "video.segment_index/1";
      sources_.push_back(std::move(src));
    }
  } else {
    sources_.push_back({"sim.camera.sagittal", "sim.camera", "Camera_Sagittal",
                        "video", "sim.camera.sagittal.video", 60.0, true, false,
                        false, false, false, "sim-camera-sagittal",
                        "CaptureSuite Sim", "SyntheticCamera", "SIM-CAM-001", "",
                        "sim.builtin", "video.segment_index/1"});
  }

  sources_.push_back({"sim.emg.main", "sim.emg", "Sim_EMG_Main", "emg",
                      "sim.emg.main.batch", 2000.0, true, false, false, false,
                      false, "sim-emg-main", "CaptureSuite Sim", "EmgArray",
                      "SIM-EMG-001", "", "sim.builtin", "emg.batch/1"});
  sources_.push_back({"sim.imu.upper", "sim.imu", "Sim_IMU_UpperBody", "imu",
                      "sim.imu.upper.frame", 100.0, true, false, false, false,
                      false, "sim-imu-upper", "CaptureSuite Sim", "ImuSuit",
                      "SIM-IMU-001", "", "sim.builtin", "imu.frame/1"});
  sources_.push_back({"sim.radar.1", "sim.radar", "Radar_Front_Left", "radar",
                      "sim.radar.1.frame", 30.0, true, false, false, false,
                      false, "sim-radar-1", "CaptureSuite Sim", "RadarModule",
                      "SIM-RDR-001", "", "sim.builtin", "radar.frame/1"});
  sources_.push_back({"sim.radar.2", "sim.radar", "Radar_Front_Right", "radar",
                      "sim.radar.2.frame", 30.0, true, false, false, false,
                      false, "sim-radar-2", "CaptureSuite Sim", "RadarModule",
                      "SIM-RDR-002", "", "sim.builtin", "radar.frame/1"});
  sources_.push_back({"sim.custom.forceplate", "sim.forceplate", "ForcePlate_A",
                      "force", "sim.custom.forceplate.samples", 1000.0, true,
                      false, false, false, false, "sim-force-a",
                      "CaptureSuite Sim", "ForcePlate", "SIM-FP-001", "",
                      "sim.builtin", "generic.numeric_batch/1"});
  sources_.push_back({"sim.replay.demo", "sim.replay", "Replay_Demo", "mixed",
                      "sim.replay.demo.samples", 120.0, true, true, false, false,
                      false, "sim-replay-demo", "CaptureSuite Sim", "Replay",
                      "SIM-RPL-001", "", "sim.builtin",
                      "generic.numeric_batch/1"});

  if (radar_workers_) {
    std::vector<capture::v1::SourceInstance> radar_instances;
    std::string enum_err;
    if (radar_workers_->enumerate(radar_instances, enum_err)) {
      for (const auto& inst : radar_instances) {
        const auto mod_it = inst.metadata().find("modality");
        const std::string modality =
            mod_it != inst.metadata().end() ? mod_it->second : "";
        if (inst.source_type() != "radar" && modality != "radar" &&
            modality != "radar_doppler") {
          continue;
        }
        SimSourceDesc src;
        src.source_id = inst.source_id();
        src.source_type = "radar";
        src.alias =
            inst.alias().empty() ? inst.source_id() : inst.alias();
        src.modality = "radar";
        src.stream_id = inst.source_id() + ".frame";
        src.nominal_rate_hz = 20.0;
        if (!inst.streams().empty()) {
          const auto& stream = inst.streams(0);
          if (!stream.modality().empty()) {
            src.modality = stream.modality();
          }
          if (stream.nominal_rate_hz() > 0) {
            src.nominal_rate_hz = stream.nominal_rate_hz();
          }
          if (!stream.stream_id().empty()) {
            src.stream_id = stream.stream_id();
          }
          if (!stream.data_schema_id().empty()) {
            src.data_schema_id = stream.data_schema_id();
          }
        }
        src.is_radar = true;
        if (!inst.plugin_id().empty()) {
          src.plugin_id = inst.plugin_id();
        } else {
          src.plugin_id = "radar.ifx";
        }
        if (src.data_schema_id.empty()) {
          src.data_schema_id = src.modality == "radar_doppler"
                                   ? "radar.doppler/1"
                                   : "radar.frame/1";
        }
        if (!inst.physical_devices().empty()) {
          const auto& phys = inst.physical_devices(0);
          src.stable_device_key = phys.stable_device_key();
          src.vendor = phys.vendor().empty() ? "Infineon" : phys.vendor();
          src.model = phys.model();
          src.serial = phys.serial();
        } else {
          src.vendor = "Infineon";
        }
        sources_.push_back(std::move(src));
      }
    } else if (!enum_err.empty()) {
      capture::log::warn("radar_enumerate_failed", enum_err);
    }
  }

  // Only one physical camera is selected by default. Selecting every MF device
  // opened Iriun/DroidCam/Camo + built-in alongside the Brio and lit every LED.
  std::string default_camera_id;
  int best_camera_score = -1000;
  for (const auto& src : sources_) {
    const int score = camera_default_score(src);
    if (score > best_camera_score) {
      best_camera_score = score;
      default_camera_id = src.source_id;
    }
  }

  std::string default_radar_id;
  bool has_real_radar = false;
  for (const auto& src : sources_) {
    if (src.is_radar) {
      has_real_radar = true;
      if (default_radar_id.empty()) {
        default_radar_id = src.source_id;
      }
    }
  }

  for (const auto& src : sources_) {
    SourceFsm fsm;
    fsm.apply(SourceEvent::Discover);
    bool default_selected =
        !src.is_replay && src.source_type != "sim.forceplate" &&
        src.source_id != "sim.radar.2";
    if (src.is_camera) {
      default_selected = (src.source_id == default_camera_id);
    }
    if (has_real_radar) {
      if (src.source_id == "sim.radar.1") {
        default_selected = false;
      } else if (src.is_radar) {
        default_selected = (src.source_id == default_radar_id);
      }
    }
    fsm.set_selected(default_selected);
    fsms_.emplace(src.source_id, std::move(fsm));
    preview_cfg_[src.source_id] = make_preview_desc(src);
    preview_slots_[src.source_id] = std::make_unique<PreviewSlot>();
  }
}

PreviewDescriptorData SimEngine::make_preview_desc(const SimSourceDesc& src) const {
  PreviewDescriptorData d;
  d.source_id = src.source_id;
  d.stream_id = src.stream_id;
  d.enabled = true;
  d.selected_channel = 0;
  if (src.modality == "video") {
    d.kind = PreviewKind::ImageThumbnail;
    d.max_payload_bytes = 256 * 1024;
    d.max_rate_hz = 15;
    d.content_type = "image/rgb24";
  } else if (src.modality == "emg") {
    d.kind = PreviewKind::TraceBlock;
    d.max_payload_bytes = 32 * 1024;
    d.max_rate_hz = 20;
    d.content_type = "application/x-capture-trace";
    d.available_channels = {"ch0", "ch1", "ch2", "ch3",
                            "ch4", "ch5", "ch6", "ch7"};
  } else if (src.modality == "imu") {
    d.kind = PreviewKind::Orientation;
    d.max_payload_bytes = 64;
    d.max_rate_hz = 30;
    d.content_type = "application/x-capture-orientation";
    d.available_channels = {"pelvis", "sternum", "head", "l_upper",
                            "r_upper", "l_fore", "r_fore"};
  } else if (src.modality == "radar") {
    d.kind = PreviewKind::Matrix2D;
    // Fits the worker's 128×128 float HD range-Doppler view.
    d.max_payload_bytes = 64 * 1024;
    d.max_rate_hz = 5;
    d.content_type = "application/x-capture-matrix";
  } else if (src.modality == "radar_doppler") {
    d.kind = PreviewKind::TraceBlock;
    d.max_payload_bytes = 4 * 1024;
    d.max_rate_hz = 5;
    d.content_type = "application/x-capture-trace";
  } else if (src.modality == "force") {
    d.kind = PreviewKind::TraceSingle;
    d.max_payload_bytes = 4 * 1024;
    d.max_rate_hz = 20;
    d.content_type = "application/x-capture-trace";
    d.available_channels = {"Fz"};
  } else {
    d.kind = PreviewKind::ScalarSeries;
    d.max_payload_bytes = 512;
    d.max_rate_hz = 10;
    d.content_type = "application/x-capture-scalar";
  }
  return d;
}

void SimEngine::reset_sources_for_new_session() {
  for (auto& [id, fsm] : fsms_) {
    (void)id;
    const bool selected = fsm.selected();
    fsm = SourceFsm{};
    fsm.apply(SourceEvent::Discover);
    fsm.set_selected(selected);
  }
  drop_remaining_.clear();
  gap_counts_.clear();
  measured_rate_.clear();
  samples_in_window_.clear();
  window_start_ns_.clear();
  alerts_.clear();
}

SourceFsm& SimEngine::source_fsm(const std::string& source_id) {
  return fsms_.at(source_id);
}

const SourceFsm& SimEngine::source_fsm(const std::string& source_id) const {
  return fsms_.at(source_id);
}

SessionState SimEngine::session_state() const {
  std::lock_guard lock(mu_);
  return session_fsm_.state();
}

bool SimEngine::create_session(std::string session_id, std::string& error) {
  return create_session(std::move(session_id), package_parent_.string(), error);
}

bool SimEngine::create_session(std::string session_id, std::string package_parent,
                               std::string& error) {
  std::lock_guard lock(mu_);
  if (session_fsm_.state() == SessionState::Recording ||
      session_fsm_.state() == SessionState::Arming ||
      session_fsm_.state() == SessionState::Stopping) {
    error = "cannot create session while active";
    return false;
  }
  // Leave read-only review attach before opening a writable package.
  review_mode_ = false;
  review_package_path_.clear();
  review_lanes_.clear();
  if (session_fsm_.state() == SessionState::Finalized ||
      session_fsm_.state() == SessionState::Failed ||
      session_fsm_.state() == SessionState::Preparing) {
    session_fsm_ = SessionFsm{};
  }
  const auto tr = session_fsm_.apply(SessionEvent::CreateSession);
  if (!tr.ok) {
    error = tr.message;
    return false;
  }
  session_id_ = std::move(session_id);
  if (!package_parent.empty()) {
    package_parent_ = package_parent;
  }
  std::error_code ec;
  std::filesystem::create_directories(package_parent_, ec);

  capture::storage::PackageOptions opts;
  opts.parent_dir = package_parent_;
  opts.session_id = session_id_;
  opts.session_name = session_id_;
  opts.rotate_bytes = rotate_bytes_;
  opts.descriptor_set_path = descriptor_set_path_;
  if (opts.descriptor_set_path.empty()) {
    opts.descriptor_set_path =
        std::filesystem::path("build") / "generated" / "capture_v1.desc";
  }

  package_ = std::make_shared<capture::storage::SessionPackage>();
  if (!package_->create(opts, error)) {
    package_.reset();
    capture::log::error("session_create_failed", error);
    return false;
  }
  store_.clear();
  checkpoints_.clear();
  annotations_.clear();
  sync_anchors_.clear();
  alerts_.clear();
  alert_events_.clear();
  config_json_.clear();
  clock_.clear_t0();
  t0_wall_utc_.clear();
  sequence_counter_ = 0;
  reset_sources_for_new_session();
  ensure_preview_running_unlocked();
  capture::log::set_session_id(session_id_);
  capture::log::set_session_log_dir(package_->root() / "logs");
  capture::log::info("session_created", "session package created",
                     {{"package_path", package_->root().string()}});
  return true;
}

std::string SimEngine::session_id() const {
  std::lock_guard lock(mu_);
  return session_id_;
}

std::string SimEngine::package_path() const {
  std::lock_guard lock(mu_);
  if (package_) {
    return package_->root().string();
  }
  if (review_mode_ && !review_package_path_.empty()) {
    return review_package_path_.string();
  }
  return "";
}

bool SimEngine::open_session(const std::string& package_path, bool& recovered,
                             std::string& error) {
  recovered = false;
  auto result = capture::storage::recover_session(package_path);
  if (!result.ok) {
    error = result.error;
    std::lock_guard lock(mu_);
    session_fsm_.apply(SessionEvent::FatalError);
    return false;
  }
  recovered = result.recovered;

  const std::filesystem::path root(package_path);
  nlohmann::json manifest;
  {
    std::ifstream in(root / "manifest.json");
    if (!in) {
      error = "missing manifest.json after recover";
      return false;
    }
    try {
      in >> manifest;
    } catch (const std::exception& ex) {
      error = std::string("manifest parse failed: ") + ex.what();
      return false;
    }
  }

  std::vector<CheckpointEvent> checkpoints;
  std::vector<AnnotationEvent> annotations;
  std::vector<LaneViewData> lanes;
  const auto events_dir = root / "events";
  auto load_array = [](const std::filesystem::path& path) -> nlohmann::json {
    std::ifstream in(path);
    if (!in) {
      return nlohmann::json::array();
    }
    nlohmann::json j;
    try {
      in >> j;
    } catch (...) {
      return nlohmann::json::array();
    }
    if (j.is_array()) {
      return j;
    }
    return nlohmann::json::array();
  };
  auto as_i64 = [](const nlohmann::json& row, const char* a, const char* b,
                   int64_t fallback = 0) -> int64_t {
    for (const char* key : {a, b}) {
      if (!row.contains(key)) {
        continue;
      }
      const auto& v = row.at(key);
      if (v.is_number_integer()) {
        return v.get<int64_t>();
      }
      if (v.is_number_unsigned()) {
        return static_cast<int64_t>(v.get<uint64_t>());
      }
      if (v.is_string()) {
        try {
          return std::stoll(v.get<std::string>());
        } catch (...) {
        }
      }
    }
    return fallback;
  };
  auto as_str = [](const nlohmann::json& row, const char* a, const char* b,
                   const std::string& fallback = "") -> std::string {
    for (const char* key : {a, b}) {
      if (row.contains(key) && row.at(key).is_string()) {
        return row.at(key).get<std::string>();
      }
    }
    return fallback;
  };
  for (const auto& row : load_array(events_dir / "checkpoints.json")) {
    CheckpointEvent cp;
    cp.checkpoint_id = as_str(row, "checkpointId", "checkpoint_id");
    cp.name = as_str(row, "name", "name");
    cp.original_timestamp_ns =
        as_i64(row, "originalTimestampNs", "original_timestamp_ns");
    cp.effective_timestamp_ns =
        as_i64(row, "effectiveTimestampNs", "effective_timestamp_ns",
               cp.original_timestamp_ns);
    checkpoints.push_back(std::move(cp));
  }
  for (const auto& row : load_array(events_dir / "annotations.json")) {
    AnnotationEvent a;
    a.annotation_id = as_str(row, "annotationId", "annotation_id");
    a.text = as_str(row, "text", "text");
    a.timestamp_ns = as_i64(row, "timestampNs", "timestamp_ns");
    annotations.push_back(std::move(a));
  }

  std::vector<std::string> source_ids;
  if (manifest.contains("sourceIds") && manifest["sourceIds"].is_array()) {
    for (const auto& sid : manifest["sourceIds"]) {
      source_ids.push_back(sid.get<std::string>());
    }
  }
  const auto sources_root = root / "sources";
  if (source_ids.empty() && std::filesystem::is_directory(sources_root)) {
    for (const auto& entry : std::filesystem::directory_iterator(sources_root)) {
      if (entry.is_directory()) {
        source_ids.push_back(entry.path().filename().string());
      }
    }
  }
  for (const auto& sid : source_ids) {
    LaneViewData lane;
    lane.source_id = sid;
    lane.alias = sid;
    lane.lifecycle = SourceLifecycle::Discovered;
    const auto gap_path = sources_root / sid / "health" / "gaps.jsonl";
    if (std::filesystem::is_regular_file(gap_path)) {
      std::ifstream gin(gap_path);
      std::string line;
      while (std::getline(gin, line)) {
        if (line.empty()) {
          continue;
        }
        try {
          auto row = nlohmann::json::parse(line);
          GapRecord g;
          g.cause = as_str(row, "cause", "cause", "unknown");
          g.start_session_time_ns =
              as_i64(row, "startSessionTimeNs", "start_session_time_ns");
          if (row.contains("endSessionTimeNs") ||
              row.contains("end_session_time_ns")) {
            g.end_session_time_ns =
                as_i64(row, "endSessionTimeNs", "end_session_time_ns", -1);
          }
          g.estimated_lost_count =
              as_i64(row, "estimatedLostCount", "estimated_lost_count");
          lane.gaps.push_back(g);
          if (lane.stream_id.empty()) {
            lane.stream_id =
                as_str(row, "streamId", "stream_id", sid + ".stream");
          }
        } catch (...) {
        }
      }
    }
    if (lane.stream_id.empty()) {
      lane.stream_id = sid + ".stream";
    }
    lanes.push_back(std::move(lane));
  }

  std::lock_guard lock(mu_);
  session_fsm_ = SessionFsm{};
  package_.reset();
  review_mode_ = true;
  review_package_path_ = root;
  review_lanes_ = std::move(lanes);
  session_id_ = manifest.value("sessionId", "");
  if (session_id_.empty() && manifest.contains("identity")) {
    session_id_ = manifest["identity"].value("sessionId", "");
  }
  t0_wall_utc_ = manifest.value("t0WallUtc", "");
  checkpoints_ = std::move(checkpoints);
  annotations_ = std::move(annotations);
  sync_anchors_.clear();
  alerts_.clear();
  return true;
}

bool SimEngine::select_sources(const std::vector<std::string>& source_ids,
                               std::string& error) {
  std::lock_guard lock(mu_);
  if (session_fsm_.state() == SessionState::Recording ||
      session_fsm_.state() == SessionState::Arming) {
    error = "source selection locked while recording";
    return false;
  }
  for (const auto& id : source_ids) {
    if (fsms_.find(id) == fsms_.end()) {
      error = "unknown source: " + id;
      return false;
    }
  }
  for (auto& [id, fsm] : fsms_) {
    (void)id;
    fsm.set_selected(false);
  }
  for (const auto& id : source_ids) {
    fsms_.at(id).set_selected(true);
  }
  ensure_preview_running_unlocked();
  return true;
}

std::vector<std::string> SimEngine::selected_source_ids() const {
  std::lock_guard lock(mu_);
  std::vector<std::string> ids;
  for (const auto& src : sources_) {
    if (fsms_.at(src.source_id).selected()) {
      ids.push_back(src.source_id);
    }
  }
  return ids;
}

bool SimEngine::open_camera_unlocked(const SimSourceDesc& src, std::string& error) {
  if (!src.is_camera) {
    return true;
  }
  if (camera_workers_) {
    return camera_workers_->has_worker(src.source_id) ||
           camera_workers_->spawn_for_source(src.source_id, error);
  }
  auto& cam = cameras_[src.source_id];
  if (!cam) {
    cam = std::make_unique<CameraCapture>();
  }
  if (cam->is_open()) {
    return true;
  }
  CameraDeviceInfo info;
  info.source_id = src.source_id;
  info.stable_device_key = src.stable_device_key;
  info.friendly_name = src.alias;
  info.vendor = src.vendor;
  info.model = src.model;
  info.symbolic_link = src.camera_symbolic_link;
  if (!cam->open(info, error)) {
    return false;
  }
  return true;
}

void SimEngine::drain_camera_workers() {
  if (!camera_workers_) {
    return;
  }
  std::shared_ptr<capture::storage::SessionPackage> pkg;
  {
    std::lock_guard lock(mu_);
    pkg = package_;
  }
  camera_workers_->poll(
      [&](const capture::v1::SegmentSealed& sealed) {
        if (!pkg) {
          return;
        }
        capture::storage::SealedSegmentInfo info;
        info.relative_path = sealed.path();
        info.size_bytes = sealed.size_bytes();
        info.hash_blake3_hex = sealed.hash_blake3_hex();
        info.start_session_time_ns = sealed.start_session_time_ns();
        info.end_session_time_ns = sealed.end_session_time_ns();
        info.actual_count = sealed.actual_count();
        info.segment_index = static_cast<int>(sealed.segment_index());
        info.source_id = sealed.source_id();
        info.stream_id = sealed.stream_id();
        pkg->record_external_segment(info);
      },
      [&](PreviewFrameData frame) {
        std::lock_guard lock(mu_);
        auto it = preview_slots_.find(frame.source_id);
        if (it != preview_slots_.end() && it->second) {
          it->second->publish(std::move(frame));
        }
      },
      [&](const capture::v1::OverloadEvent& ov) {
        std::lock_guard lock(mu_);
        gap_counts_[ov.stream_id()] += 1;
        push_alert("WARNING", ov.source_id(), "OVERLOAD_DROP",
                   "camera record queue overrun");
        if (pkg) {
          std::string err;
          pkg->journal_event(
              "OVERLOAD", ov.session_time_ns(), ov.source_id(), ov.stream_id(),
              "{\"cause\":\"OVERLOAD_DROP\",\"dropped\":" +
                  std::to_string(ov.dropped_count()) + "}",
              err);
        }
      });
}

void SimEngine::drain_radar_workers() {
  if (!radar_workers_) {
    return;
  }
  std::shared_ptr<capture::storage::SessionPackage> pkg;
  {
    std::lock_guard lock(mu_);
    pkg = package_;
  }
  radar_workers_->poll(
      [&](const capture::v1::SegmentSealed& sealed) {
        if (!pkg) {
          return;
        }
        capture::storage::SealedSegmentInfo info;
        info.relative_path = sealed.path();
        info.size_bytes = sealed.size_bytes();
        info.hash_blake3_hex = sealed.hash_blake3_hex();
        info.start_session_time_ns = sealed.start_session_time_ns();
        info.end_session_time_ns = sealed.end_session_time_ns();
        info.actual_count = sealed.actual_count();
        info.segment_index = static_cast<int>(sealed.segment_index());
        info.source_id = sealed.source_id();
        info.stream_id = sealed.stream_id();
        pkg->record_external_segment(info);
      },
      [&](PreviewFrameData frame) {
        std::lock_guard lock(mu_);
        auto it = preview_slots_.find(frame.source_id);
        if (it != preview_slots_.end() && it->second) {
          it->second->publish(std::move(frame));
        }
      },
      [&](const capture::v1::OverloadEvent& ov) {
        std::lock_guard lock(mu_);
        gap_counts_[ov.stream_id()] += 1;
        push_alert("WARNING", ov.source_id(), "OVERLOAD_DROP",
                   "radar record queue overrun");
        if (pkg) {
          std::string err;
          pkg->journal_event(
              "OVERLOAD", ov.session_time_ns(), ov.source_id(), ov.stream_id(),
              "{\"cause\":\"OVERLOAD_DROP\",\"dropped\":" +
                  std::to_string(ov.dropped_count()) + "}",
              err);
        }
      });
}

void SimEngine::prepare_selected_sources() {
  std::vector<std::string> worker_cameras;
  std::vector<std::string> worker_radars;
  {
    std::lock_guard lock(mu_);
    for (const auto& src : sources_) {
      auto& fsm = fsms_.at(src.source_id);
      if (!fsm.selected() || fsm.lifecycle() != SourceLifecycle::Discovered) {
        continue;
      }
      if (src.is_camera && camera_workers_) {
        worker_cameras.push_back(src.source_id);
      }
      if (src.is_radar && radar_workers_) {
        worker_radars.push_back(src.source_id);
      }
    }
  }
  // Spawn workers in parallel. A dead virtual camera can sit on the connect
  // timeout; serialising that across every MF device blocked StartAllReady for
  // minutes. Live cameras (Brio, built-in) finish in ~1–2 s.
  std::unordered_map<std::string, std::string> spawn_errors;
  {
    std::mutex err_mu;
    std::vector<std::thread> threads;
    threads.reserve(worker_cameras.size());
    for (const auto& id : worker_cameras) {
      threads.emplace_back([&, id] {
        std::string err;
        if (!camera_workers_->spawn_for_source(id, err)) {
          std::lock_guard lock(err_mu);
          spawn_errors[id] = std::move(err);
        }
      });
    }
    for (auto& t : threads) {
      t.join();
    }
  }
  std::unordered_map<std::string, std::string> radar_spawn_errors;
  {
    std::mutex err_mu;
    std::vector<std::thread> threads;
    threads.reserve(worker_radars.size());
    for (const auto& id : worker_radars) {
      threads.emplace_back([&, id] {
        std::string err;
        if (!radar_workers_->spawn_for_source(id, err)) {
          std::lock_guard lock(err_mu);
          radar_spawn_errors[id] = std::move(err);
        }
      });
    }
    for (auto& t : threads) {
      t.join();
    }
  }
  for (const auto& id : worker_cameras) {
    if (spawn_errors.count(id)) {
      continue;
    }
    // Push daemon-side config into the worker so Start uses the same document
    // (CONFIGURATION_UI.md: daemon validates, worker is device truth).
    std::string cfg = "{}";
    {
      std::lock_guard lock(mu_);
      auto cfg_it = config_json_.find(id);
      if (cfg_it != config_json_.end() && !cfg_it->second.empty()) {
        cfg = cfg_it->second;
      }
    }
    capture::v1::ApplyConfigReply reply;
    std::string err;
    if (!camera_workers_->apply_config(id, cfg, reply, err)) {
      spawn_errors[id] = std::move(err);
    } else if (!reply.effective_json().empty()) {
      std::lock_guard lock(mu_);
      config_json_[id] = reply.effective_json();
    }
  }
  for (const auto& id : worker_radars) {
    if (radar_spawn_errors.count(id)) {
      continue;
    }
    std::string cfg = "{}";
    {
      std::lock_guard lock(mu_);
      auto cfg_it = config_json_.find(id);
      if (cfg_it != config_json_.end() && !cfg_it->second.empty()) {
        cfg = cfg_it->second;
      }
    }
    capture::v1::ApplyConfigReply reply;
    std::string err;
    if (!radar_workers_->apply_config(id, cfg, reply, err)) {
      radar_spawn_errors[id] = std::move(err);
    } else if (!reply.effective_json().empty()) {
      std::lock_guard lock(mu_);
      config_json_[id] = reply.effective_json();
    }
  }

  std::lock_guard lock(mu_);
  for (auto& src : sources_) {
    auto& fsm = fsms_.at(src.source_id);
    if (!fsm.selected()) {
      continue;
    }
    auto advance = [&](SourceEvent ev) {
      if (fsm.lifecycle() != SourceLifecycle::Failed &&
          fsm.lifecycle() != SourceLifecycle::Recording) {
        fsm.apply(ev);
      }
    };
    if (fsm.lifecycle() == SourceLifecycle::Discovered) {
      if (src.is_camera) {
        if (camera_workers_) {
          auto eit = spawn_errors.find(src.source_id);
          if (eit != spawn_errors.end()) {
            fsm.apply(SourceEvent::ConnectFail);
            fsm.set_selected(false);
            push_alert("WARNING", src.source_id, "CAMERA_WORKER_SPAWN_FAILED",
                       eit->second);
            continue;
          }
        } else {
          std::string err;
          if (!open_camera_unlocked(src, err)) {
            fsm.apply(SourceEvent::ConnectFail);
            fsm.set_selected(false);
            push_alert("WARNING", src.source_id, "CAMERA_OPEN_FAILED", err);
            continue;
          }
        }
      } else if (src.is_radar && radar_workers_) {
        auto eit = radar_spawn_errors.find(src.source_id);
        if (eit != radar_spawn_errors.end()) {
          fsm.apply(SourceEvent::ConnectFail);
          fsm.set_selected(false);
          push_alert("WARNING", src.source_id, "RADAR_WORKER_SPAWN_FAILED",
                      eit->second);
          continue;
        }
      }
      advance(SourceEvent::Connect);
      advance(SourceEvent::ApplyConfig);
      advance(SourceEvent::Validate);
      advance(SourceEvent::MarkReady);
    }
  }
}

bool SimEngine::start_selected(std::string& error) {
  prepare_selected_sources();
  {
    std::lock_guard lock(mu_);
    if (session_fsm_.state() != SessionState::Preparing) {
      error = "session not in PREPARING";
      return false;
    }
    if (!package_) {
      error = "no session package";
      return false;
    }
    bool any_ready = false;
    for (const auto& src : sources_) {
      const auto& fsm = fsms_.at(src.source_id);
      if (fsm.selected() && fsm.lifecycle() == SourceLifecycle::Ready) {
        any_ready = true;
        break;
      }
    }
    if (!any_ready) {
      error = "no selected sources are READY";
      return false;
    }

    auto tr = session_fsm_.apply(SessionEvent::StartSelected);
    if (!tr.ok) {
      error = tr.message;
      return false;
    }

    int armed = 0;
    for (auto& src : sources_) {
      auto& fsm = fsms_.at(src.source_id);
      if (!fsm.selected()) {
        continue;
      }
      if (fsm.apply(SourceEvent::Arm).ok) {
        ++armed;
      }
    }
    if (armed == 0) {
      session_fsm_.apply(SessionEvent::ArmTimeoutNone);
      error = "ARM_FAILED";
      return false;
    }

    auto t0 = clock_.establish_t0();
    t0_wall_utc_ = t0.wall.iso_utc;
    store_.clear();
    drop_remaining_.clear();
    rehearsal_ = false;

    std::vector<capture::storage::PackageStreamDesc> streams;
    for (const auto& src : sources_) {
      auto& fsm = fsms_.at(src.source_id);
      if (!fsm.selected()) {
        continue;
      }
      store_.ensure_stream(src.stream_id, src.source_id, src.modality,
                           src.nominal_rate_hz);
      capture::storage::PackageStreamDesc desc{
          src.source_id,   src.stream_id,   src.modality,
          src.alias,       src.source_type, src.nominal_rate_hz};
      // Camera/radar workers write their own segments; do not open a daemon
      // MCAP that would race the worker on the same path.
      desc.external_segments =
          (src.is_camera && camera_workers_ != nullptr) ||
          (src.is_radar && radar_workers_ != nullptr);
      streams.push_back(std::move(desc));
      fsm.apply(SourceEvent::Start);
      if (src.is_camera && !camera_workers_) {
        auto it = cameras_.find(src.source_id);
        if (it != cameras_.end() && it->second) {
          std::string cam_err;
          if (!it->second->is_running() && !it->second->start(cam_err)) {
            push_alert("WARNING", src.source_id, "CAMERA_START_FAILED", cam_err);
          }
        }
      }
    }
    if (!package_->begin_recording(streams, t0.qpc_ticks, t0.qpc_frequency,
                                   t0.wall.iso_utc, t0.uncertainty_ns, error)) {
      return false;
    }
    session_fsm_.apply(SessionEvent::ArmCompleteAll);
    ensure_preview_running_unlocked();
  }

  if (camera_workers_) {
    std::string session;
    std::string pkg_path;
    int64_t t0_qpc_ns = 0;
    std::vector<std::string> cam_ids;
    {
      std::lock_guard lock(mu_);
      session = session_id_;
      pkg_path = package_ ? package_->root().string() : "";
      if (clock_.has_t0()) {
        const auto& t0 = clock_.t0();
        t0_qpc_ns =
            capture::SessionClock::qpc_delta_to_ns(t0.qpc_ticks, t0.qpc_frequency);
      }
      for (const auto& src : sources_) {
        if (src.is_camera && fsms_.at(src.source_id).selected()) {
          cam_ids.push_back(src.source_id);
        }
      }
    }
    for (const auto& id : cam_ids) {
      std::string cfg = "{}";
      {
        std::lock_guard lock(mu_);
        auto cfg_it = config_json_.find(id);
        if (cfg_it != config_json_.end() && !cfg_it->second.empty()) {
          cfg = cfg_it->second;
        }
      }
      capture::v1::ApplyConfigReply applied;
      std::string cam_err;
      if (!camera_workers_->apply_config(id, cfg, applied, cam_err)) {
        std::lock_guard lock(mu_);
        push_alert("WARNING", id, "CAMERA_WORKER_CONFIG_FAILED", cam_err);
      }
      capture::v1::StartRequest req;
      req.set_source_id(id);
      req.set_session_id(session);
      req.set_session_package_path(pkg_path);
      req.set_session_t0_qpc_ns(t0_qpc_ns);
      if (!camera_workers_->start_capture(id, req, cam_err)) {
        std::lock_guard lock(mu_);
        push_alert("WARNING", id, "CAMERA_WORKER_START_FAILED", cam_err);
        // FSM already entered Recording before the worker Start RPC; mark the
        // source failed so the UI does not show a healthy camera with no frames.
        auto fit = fsms_.find(id);
        if (fit != fsms_.end()) {
          fit->second.apply(SourceEvent::Unrecoverable);
          fit->second.set_selected(false);
        }
      }
    }
  }

  if (radar_workers_) {
    std::string session;
    std::string pkg_path;
    int64_t t0_qpc_ns = 0;
    std::vector<std::string> radar_ids;
    {
      std::lock_guard lock(mu_);
      session = session_id_;
      pkg_path = package_ ? package_->root().string() : "";
      if (clock_.has_t0()) {
        const auto& t0 = clock_.t0();
        t0_qpc_ns =
            capture::SessionClock::qpc_delta_to_ns(t0.qpc_ticks, t0.qpc_frequency);
      }
      for (const auto& src : sources_) {
        if (src.is_radar && fsms_.at(src.source_id).selected()) {
          radar_ids.push_back(src.source_id);
        }
      }
    }
    for (const auto& id : radar_ids) {
      std::string cfg = "{}";
      {
        std::lock_guard lock(mu_);
        auto cfg_it = config_json_.find(id);
        if (cfg_it != config_json_.end() && !cfg_it->second.empty()) {
          cfg = cfg_it->second;
        }
      }
      capture::v1::ApplyConfigReply applied;
      std::string radar_err;
      if (!radar_workers_->apply_config(id, cfg, applied, radar_err)) {
        std::lock_guard lock(mu_);
        push_alert("WARNING", id, "RADAR_WORKER_CONFIG_FAILED", radar_err);
      }
      capture::v1::StartRequest req;
      req.set_source_id(id);
      req.set_session_id(session);
      req.set_session_package_path(pkg_path);
      req.set_session_t0_qpc_ns(t0_qpc_ns);
      if (!radar_workers_->start_capture(id, req, radar_err)) {
        std::lock_guard lock(mu_);
        push_alert("WARNING", id, "RADAR_WORKER_START_FAILED", radar_err);
        auto fit = fsms_.find(id);
        if (fit != fsms_.end()) {
          fit->second.apply(SourceEvent::Unrecoverable);
          fit->second.set_selected(false);
        }
      }
    }
  }

  recording_ = true;
  worker_ = std::thread([this] { recording_loop(); });
  capture::log::info("session_started", "recording started");
  return true;
}

std::string SimEngine::request_stop_token() {
  std::lock_guard lock(mu_);
  auto token = make_id("stop");
  session_fsm_.issue_stop_token(token);
  return token;
}

bool SimEngine::stop(const std::string& confirmation_token, std::string& error) {
  {
    std::lock_guard lock(mu_);
    if (!session_fsm_.consume_stop_token(confirmation_token)) {
      error = "invalid or missing stop confirmation token";
      return false;
    }
    auto tr = session_fsm_.apply(SessionEvent::Stop);
    if (!tr.ok) {
      error = tr.message;
      return false;
    }
    for (auto& src : sources_) {
      auto& fsm = fsms_.at(src.source_id);
      if (fsm.lifecycle() == SourceLifecycle::Recording) {
        fsm.apply(SourceEvent::Stop);
      }
      if (src.is_camera && !camera_workers_) {
        auto it = cameras_.find(src.source_id);
        if (it != cameras_.end() && it->second) {
          it->second->stop();
        }
      }
    }
  }
  if (camera_workers_) {
    std::vector<std::string> cam_ids;
    {
      std::lock_guard lock(mu_);
      for (const auto& src : sources_) {
        if (src.is_camera) {
          cam_ids.push_back(src.source_id);
        }
      }
    }
    // Filter and stop outside the engine lock: has_worker/stop_capture take
    // the bridge lock, and preview drain takes bridge→engine (ABBA risk).
    cam_ids.erase(std::remove_if(cam_ids.begin(), cam_ids.end(),
                                 [&](const std::string& id) {
                                   return !camera_workers_->has_worker(id);
                                 }),
                  cam_ids.end());
    std::vector<std::thread> stoppers;
    stoppers.reserve(cam_ids.size());
    for (const auto& id : cam_ids) {
      stoppers.emplace_back([this, id] {
        std::string cam_err;
        camera_workers_->stop_capture(id, cam_err);
      });
    }
    for (auto& t : stoppers) {
      t.join();
    }
    drain_camera_workers();
  }
  if (radar_workers_) {
    std::vector<std::string> radar_ids;
    {
      std::lock_guard lock(mu_);
      for (const auto& src : sources_) {
        if (src.is_radar) {
          radar_ids.push_back(src.source_id);
        }
      }
    }
    radar_ids.erase(std::remove_if(radar_ids.begin(), radar_ids.end(),
                                   [&](const std::string& id) {
                                     return !radar_workers_->has_worker(id);
                                   }),
                    radar_ids.end());
    std::vector<std::thread> stoppers;
    stoppers.reserve(radar_ids.size());
    for (const auto& id : radar_ids) {
      stoppers.emplace_back([this, id] {
        std::string radar_err;
        radar_workers_->stop_capture(id, radar_err);
      });
    }
    for (auto& t : stoppers) {
      t.join();
    }
    drain_radar_workers();
  }
  stop_recording_thread();
  std::shared_ptr<capture::storage::SessionPackage> pkg;
  {
    std::lock_guard lock(mu_);
    for (auto& src : sources_) {
      auto& fsm = fsms_.at(src.source_id);
      if (fsm.lifecycle() == SourceLifecycle::Stopping) {
        fsm.apply(SourceEvent::DrainComplete);
      }
    }
    pkg = package_;
  }
  // Hashing and manifest writes happen unlocked, so status RPCs keep answering
  // while a large tail segment finalizes.
  if (pkg && !pkg->finalize(error)) {
    capture::log::error("session_finalize_failed", error);
    return false;
  }
  {
    std::lock_guard lock(mu_);
    session_fsm_.apply(SessionEvent::DrainComplete);
  }
  capture::log::info("session_finalized", "recording stopped and package sealed");
  capture::log::clear_session_id();
  capture::log::set_session_log_dir({});
  return true;
}

bool SimEngine::finalize_session(std::string& error) {
  std::shared_ptr<capture::storage::SessionPackage> pkg;
  {
    std::lock_guard lock(mu_);
    if (session_fsm_.state() != SessionState::Preparing) {
      error = "finalize only valid from PREPARING (use Stop while recording)";
      return false;
    }
    pkg = package_;
  }
  if (pkg && !pkg->finalize(error)) {
    return false;
  }
  std::lock_guard lock(mu_);
  return session_fsm_.apply(SessionEvent::FinalizeSession).ok;
}

CheckpointEvent SimEngine::create_checkpoint(std::string name,
                                             std::string created_via) {
  CheckpointEvent cp;
  std::shared_ptr<capture::storage::SessionPackage> pkg;
  {
    std::lock_guard lock(mu_);
    cp.checkpoint_id = make_id("cp");
    cp.original_timestamp_ns = clock_.has_t0() ? clock_.session_now_ns() : 0;
    cp.effective_timestamp_ns = cp.original_timestamp_ns;
    cp.name = name.empty()
                  ? ("Section " + std::to_string(checkpoints_.size() + 1))
                  : std::move(name);
    cp.created_via = std::move(created_via);
    checkpoints_.push_back(cp);
    pkg = package_;
  }
  if (pkg) {
    std::string err;
    pkg->add_checkpoint(cp.checkpoint_id, cp.original_timestamp_ns, cp.name,
                        cp.created_via, err);
  }
  return cp;
}

bool SimEngine::update_checkpoint(const std::string& checkpoint_id,
                                  const std::string* name,
                                  const std::string* notes,
                                  const int64_t* effective_timestamp_ns,
                                  const std::string& reason,
                                  CheckpointEvent& out, std::string& error) {
  std::lock_guard lock(mu_);
  auto it = std::find_if(checkpoints_.begin(), checkpoints_.end(),
                         [&](const CheckpointEvent& c) {
                           return c.checkpoint_id == checkpoint_id;
                         });
  if (it == checkpoints_.end()) {
    error = "unknown checkpoint";
    return false;
  }
  if (name) {
    it->name = *name;
  }
  if (notes) {
    it->notes = *notes;
  }
  if (effective_timestamp_ns) {
    it->effective_timestamp_ns = *effective_timestamp_ns;
    it->timestamp_modified = true;
  }
  (void)reason;
  out = *it;
  return true;
}

AnnotationEvent SimEngine::annotate(std::string text, std::string created_via) {
  AnnotationEvent a;
  std::shared_ptr<capture::storage::SessionPackage> pkg;
  {
    std::lock_guard lock(mu_);
    a.annotation_id = make_id("ann");
    a.timestamp_ns = clock_.has_t0() ? clock_.session_now_ns() : 0;
    a.text = std::move(text);
    a.created_via = std::move(created_via);
    annotations_.push_back(a);
    pkg = package_;
  }
  if (pkg) {
    std::string err;
    pkg->add_annotation(a.annotation_id, a.timestamp_ns, a.text, a.created_via,
                        err);
  }
  return a;
}

SyncAnchorEvent SimEngine::add_sync_anchor(std::string mechanism,
                                           std::string created_via) {
  SyncAnchorEvent s;
  std::shared_ptr<capture::storage::SessionPackage> pkg;
  {
    std::lock_guard lock(mu_);
    s.sync_anchor_id = make_id("sync");
    s.timestamp_ns = clock_.has_t0() ? clock_.session_now_ns() : 0;
    s.mechanism = std::move(mechanism);
    s.created_via = std::move(created_via);
    sync_anchors_.push_back(s);
    pkg = package_;
  }
  if (pkg) {
    std::string err;
    pkg->add_sync_anchor(s.sync_anchor_id, s.timestamp_ns, s.mechanism,
                         s.created_via, err);
  }
  return s;
}

void SimEngine::push_alert(std::string level, std::string source_id,
                           std::string code, std::string message) {
  AlertData a;
  a.alert_id = make_id("alert");
  a.level = std::move(level);
  a.source_id = std::move(source_id);
  a.code = std::move(code);
  a.message = std::move(message);
  a.session_time_ns = clock_.has_t0() ? clock_.session_now_ns() : 0;
  alerts_.push_back(a);
  alert_events_.push_back(a);
}

bool SimEngine::acknowledge_alert(const std::string& alert_id, AlertData& out,
                                  std::string& error) {
  std::lock_guard lock(mu_);
  auto it = std::find_if(alerts_.begin(), alerts_.end(),
                         [&](const AlertData& a) { return a.alert_id == alert_id; });
  if (it == alerts_.end()) {
    error = "unknown alert";
    return false;
  }
  it->acknowledged = true;
  out = *it;
  alert_events_.push_back(*it);
  capture::log::info("alert_acknowledged", out.message,
                     {{"alert_id", alert_id}, {"code", out.code}});
  return true;
}

std::vector<AlertData> SimEngine::alert_events_from(std::size_t cursor) const {
  std::lock_guard lock(mu_);
  if (cursor >= alert_events_.size()) {
    return {};
  }
  return {alert_events_.begin() + static_cast<std::ptrdiff_t>(cursor),
          alert_events_.end()};
}

std::size_t SimEngine::alert_event_count() const {
  std::lock_guard lock(mu_);
  return alert_events_.size();
}

namespace {

bool validate_against_schema(const nlohmann::json& schema,
                             const nlohmann::json& document,
                             std::string& error) {
  if (!document.is_object()) {
    error = "configuration must be a JSON object";
    return false;
  }
  const auto& props = schema.value("properties", nlohmann::json::object());
  if (!props.is_object()) {
    error = "schema has no properties";
    return false;
  }
  if (schema.contains("required") && schema["required"].is_array()) {
    for (const auto& req : schema["required"]) {
      if (!req.is_string()) {
        continue;
      }
      if (!document.contains(req.get<std::string>())) {
        error = "missing required field: " + req.get<std::string>();
        return false;
      }
    }
  }
  for (const auto& [name, value] : document.items()) {
    if (!props.contains(name)) {
      error = "unknown field: " + name;
      return false;
    }
    const auto& prop = props.at(name);
    const std::string typ = prop.value("type", "");
    if (typ == "boolean" && !value.is_boolean()) {
      error = name + ": expected boolean";
      return false;
    }
    if (typ == "string" && !value.is_string()) {
      error = name + ": expected string";
      return false;
    }
    if (typ == "integer" && !value.is_number_integer()) {
      error = name + ": expected integer";
      return false;
    }
    if (typ == "number" && !value.is_number()) {
      error = name + ": expected number";
      return false;
    }
    if (typ == "array" && !value.is_array()) {
      error = name + ": expected array";
      return false;
    }
    if (prop.contains("enum") && prop["enum"].is_array()) {
      bool found = false;
      for (const auto& allowed : prop["enum"]) {
        if (allowed == value) {
          found = true;
          break;
        }
      }
      if (!found) {
        error = name + ": value not in enum";
        return false;
      }
    }
    if ((typ == "integer" || typ == "number") && value.is_number()) {
      const double num = value.get<double>();
      if (prop.contains("minimum") && num < prop["minimum"].get<double>()) {
        error = name + ": below minimum";
        return false;
      }
      if (prop.contains("maximum") && num > prop["maximum"].get<double>()) {
        error = name + ": above maximum";
        return false;
      }
    }
  }
  return true;
}

}  // namespace

bool SimEngine::get_config_schema(const std::string& source_id,
                                  std::string& schema_json,
                                  std::string& error) {
  bool is_camera_worker = false;
  bool is_radar_worker = false;
  {
    std::lock_guard lock(mu_);
    auto it = std::find_if(
        sources_.begin(), sources_.end(),
        [&](const SimSourceDesc& s) { return s.source_id == source_id; });
    if (it == sources_.end()) {
      error = "unknown source";
      return false;
    }
    is_camera_worker = it->is_camera && camera_workers_ != nullptr;
    is_radar_worker = it->is_radar && radar_workers_ != nullptr;
  }
  if (is_camera_worker) {
    capture::v1::GetConfigSchemaReply reply;
    if (!camera_workers_->get_config_schema(source_id, reply, error)) {
      return false;
    }
    schema_json = reply.schema_json();
    // Keep daemon snapshot defaults aligned with worker-reported current.
    if (!reply.effective_json().empty()) {
      std::lock_guard lock(mu_);
      if (config_json_.find(source_id) == config_json_.end()) {
        config_json_[source_id] = reply.effective_json();
      }
    }
    return true;
  }
  if (is_radar_worker) {
    capture::v1::GetConfigSchemaReply reply;
    if (!radar_workers_->get_config_schema(source_id, reply, error)) {
      return false;
    }
    schema_json = reply.schema_json();
    if (!reply.effective_json().empty()) {
      std::lock_guard lock(mu_);
      if (config_json_.find(source_id) == config_json_.end()) {
        config_json_[source_id] = reply.effective_json();
      }
    }
    return true;
  }

  std::lock_guard lock(mu_);
  auto it = std::find_if(
      sources_.begin(), sources_.end(),
      [&](const SimSourceDesc& s) { return s.source_id == source_id; });
  if (it == sources_.end()) {
    error = "unknown source";
    return false;
  }
  nlohmann::json schema;
  schema["$schema"] = "https://json-schema.org/draft/2020-12/schema";
  schema["type"] = "object";
  schema["title"] = it->alias.empty() ? it->source_id : it->alias;
  if (it->modality == "emg") {
    schema["schema_revision"] = "sim.emg/1";
    schema["properties"] = {
        {"gain",
         {{"type", "number"},
          {"minimum", 0.1},
          {"maximum", 10.0},
          {"default", 1.0},
          {"title", "Gain"},
          {"x-capture-units", "x"},
          {"x-capture-group", "Signal"},
          {"x-capture-order", 1}}},
        {"channel_count",
         {{"type", "integer"},
          {"minimum", 1},
          {"maximum", 16},
          {"default", 16},
          {"title", "Channels"},
          {"x-capture-group", "Signal"},
          {"x-capture-order", 2}}},
        {"firmware_id",
         {{"type", "string"},
          {"default", "sim-emg"},
          {"title", "Firmware id"},
          {"readOnly", true},
          {"x-capture-group", "Device"},
          {"x-capture-order", 1}}},
    };
  } else if (it->modality == "imu") {
    schema["schema_revision"] = "sim.imu/1";
    schema["properties"] = {
        {"output_rate_hz",
         {{"type", "integer"},
          {"enum", {60, 100, 120}},
          {"default", 100},
          {"title", "Output rate"},
          {"x-capture-units", "Hz"},
          {"x-capture-group", "Stream"},
          {"x-capture-order", 1},
          {"x-capture-enum-labels",
           {{"60", "60 Hz"}, {"100", "100 Hz"}, {"120", "120 Hz"}}},
          {"x-capture-restart-required", true}}},
    };
  } else if (it->modality == "radar") {
    schema["schema_revision"] = "sim.radar/1";
    schema["properties"] = {
        {"frame_rate_hz",
         {{"type", "number"},
          {"minimum", 1},
          {"maximum", 60},
          {"default", 30},
          {"title", "Frame rate"},
          {"x-capture-units", "Hz"},
          {"x-capture-group", "Stream"},
          {"x-capture-order", 1}}},
        {"chirp_bandwidth_mhz",
         {{"type", "number"},
          {"minimum", 100},
          {"maximum", 4000},
          {"default", 2000},
          {"title", "Chirp bandwidth"},
          {"x-capture-units", "MHz"},
          {"x-capture-group", "RF"},
          {"x-capture-order", 1},
          {"x-capture-advanced", true}}},
    };
  } else if (it->modality == "video") {
    // Worker-backed cameras answer from the worker's own schema above, so this
    // is always the built-in Media Foundation path.
    schema["schema_revision"] = "camera/1";
    schema["properties"] = {
        {"exposure_auto",
         {{"type", "boolean"},
          {"default", true},
          {"title", "Auto exposure"},
          {"x-capture-group", "Exposure"},
          {"x-capture-order", 1}}},
        {"preview_enabled",
         {{"type", "boolean"},
          {"default", true},
          {"title", "Preview enabled"},
          {"x-capture-group", "Preview"},
          {"x-capture-order", 1}}},
    };
    if (camera_workers_) {
      schema["properties"]["preview_max_rate_hz"] = {
          {"type", "number"},
          {"minimum", 1},
          {"maximum", 30},
          {"default", 10},
          {"title", "Preview max rate"},
          {"x-capture-units", "Hz"},
          {"x-capture-group", "Preview"},
          {"x-capture-order", 2}};
      schema["properties"]["encoder_preference"] = {
          {"type", "string"},
          {"enum", {"auto", "nvh264enc", "qsvh264enc", "amfh264enc", "mfh264enc",
                    "x264enc"}},
          {"default", "auto"},
          {"title", "Encoder preference"},
          {"x-capture-group", "Encode"},
          {"x-capture-order", 1},
          {"x-capture-restart-required", true},
          {"description",
           "Preference only; unavailable encoders fall back at arm time."}};
    }
  } else {
    schema["schema_revision"] = "sim.generic/1";
    schema["properties"] = nlohmann::json::object();
  }
  // Reflect stored values as defaults so a fresh form matches device state.
  auto cfg_it = config_json_.find(source_id);
  if (cfg_it != config_json_.end()) {
    try {
      const auto current = nlohmann::json::parse(cfg_it->second);
      if (current.is_object() && schema.contains("properties")) {
        for (auto& [name, prop] : schema["properties"].items()) {
          if (current.contains(name)) {
            prop["default"] = current.at(name);
          }
        }
      }
    } catch (...) {
    }
  }
  schema_json = schema.dump();
  return true;
}

bool SimEngine::apply_config(const std::string& source_id,
                             const std::string& config_json,
                             std::string& effective_json,
                             std::vector<std::string>& coerced_fields,
                             std::string& schema_revision,
                             std::string& error) {
  coerced_fields.clear();
  schema_revision.clear();
  std::string schema_json;
  if (!get_config_schema(source_id, schema_json, error)) {
    return false;
  }
  nlohmann::json schema;
  try {
    schema = nlohmann::json::parse(schema_json);
  } catch (const std::exception& ex) {
    error = std::string("schema parse failed: ") + ex.what();
    return false;
  }
  schema_revision = schema.value("schema_revision", "");

  bool is_camera_worker = false;
  bool is_radar_worker = false;
  {
    std::lock_guard lock(mu_);
    if (session_fsm_.state() == SessionState::Recording ||
        session_fsm_.state() == SessionState::Arming) {
      error = "INVALID_STATE";
      return false;
    }
    auto it = std::find_if(
        sources_.begin(), sources_.end(),
        [&](const SimSourceDesc& s) { return s.source_id == source_id; });
    if (it == sources_.end()) {
      error = "unknown source";
      return false;
    }
    is_camera_worker = it->is_camera && camera_workers_ != nullptr;
    is_radar_worker = it->is_radar && radar_workers_ != nullptr;
  }

  nlohmann::json requested;
  try {
    requested = nlohmann::json::parse(config_json.empty() ? "{}" : config_json);
  } catch (const std::exception& ex) {
    error = std::string("invalid JSON: ") + ex.what();
    return false;
  }
  // Strip read-only fields from the apply document before validation.
  if (schema.contains("properties") && schema["properties"].is_object()) {
    for (const auto& [name, prop] : schema["properties"].items()) {
      if (prop.value("readOnly", false)) {
        requested.erase(name);
      }
    }
  }
  if (!validate_against_schema(schema, requested, error)) {
    return false;
  }

  // Camera workers own device truth (CONFIGURATION_UI.md): validate here,
  // then forward and store the worker's effective document.
  if (is_camera_worker) {
    capture::v1::ApplyConfigReply reply;
    std::string bridge_err;
    if (!camera_workers_->apply_config(source_id, requested.dump(), reply,
                                       bridge_err)) {
      error = bridge_err.empty() ? "camera worker ApplyConfig failed"
                                 : bridge_err;
      return false;
    }
    std::lock_guard lock(mu_);
    config_json_[source_id] = reply.effective_json().empty()
                                  ? requested.dump()
                                  : reply.effective_json();
    if (!reply.schema_revision().empty()) {
      schema_revision = reply.schema_revision();
    }
    auto& fsm = fsms_.at(source_id);
    if (fsm.lifecycle() == SourceLifecycle::Connected ||
        fsm.lifecycle() == SourceLifecycle::Discovered) {
      fsm.apply(SourceEvent::ApplyConfig);
    }
    effective_json = config_json_[source_id];
    capture::log::info("config_changed", "camera worker configuration applied",
                       {{"source_id", source_id}});
    return true;
  }
  if (is_radar_worker) {
    capture::v1::ApplyConfigReply reply;
    std::string bridge_err;
    if (!radar_workers_->apply_config(source_id, requested.dump(), reply,
                                      bridge_err)) {
      error = bridge_err.empty() ? "radar worker ApplyConfig failed"
                                 : bridge_err;
      return false;
    }
    std::lock_guard lock(mu_);
    config_json_[source_id] = reply.effective_json().empty()
                                  ? requested.dump()
                                  : reply.effective_json();
    if (!reply.schema_revision().empty()) {
      schema_revision = reply.schema_revision();
    }
    auto& fsm = fsms_.at(source_id);
    if (fsm.lifecycle() == SourceLifecycle::Connected ||
        fsm.lifecycle() == SourceLifecycle::Discovered) {
      fsm.apply(SourceEvent::ApplyConfig);
    }
    effective_json = config_json_[source_id];
    capture::log::info("config_changed", "radar worker configuration applied",
                       {{"source_id", source_id}});
    return true;
  }

  std::lock_guard lock(mu_);
  auto it = std::find_if(
      sources_.begin(), sources_.end(),
      [&](const SimSourceDesc& s) { return s.source_id == source_id; });
  if (it == sources_.end()) {
    error = "unknown source";
    return false;
  }

  nlohmann::json effective = requested;
  // Honest device-side coercion within the legal schema set: radar chirp
  // bandwidth snaps to the nearest 100 MHz step the sim "hardware" supports.
  if (it->modality == "radar" && effective.contains("chirp_bandwidth_mhz") &&
      effective["chirp_bandwidth_mhz"].is_number()) {
    const double raw = effective["chirp_bandwidth_mhz"].get<double>();
    const double snapped = std::round(raw / 100.0) * 100.0;
    if (snapped != raw) {
      effective["chirp_bandwidth_mhz"] = snapped;
      coerced_fields.push_back("chirp_bandwidth_mhz");
    }
  }

  config_json_[source_id] = effective.dump();
  auto& fsm = fsms_.at(source_id);
  if (fsm.lifecycle() == SourceLifecycle::Connected ||
      fsm.lifecycle() == SourceLifecycle::Discovered) {
    fsm.apply(SourceEvent::ApplyConfig);
  }
  effective_json = config_json_[source_id];
  capture::log::info("config_changed", "configuration applied",
                     {{"source_id", source_id}});
  return true;
}

std::string SimEngine::config_snapshot(const std::string& source_id) const {
  std::lock_guard lock(mu_);
  auto it = config_json_.find(source_id);
  return it == config_json_.end() ? "{}" : it->second;
}

bool SimEngine::start_all_ready(std::vector<std::string>& started_source_ids,
                                std::string& error) {
  started_source_ids.clear();
  {
    std::lock_guard lock(mu_);
    if (session_fsm_.state() != SessionState::Preparing) {
      error = "session not in PREPARING";
      return false;
    }
    // Select the usual default sims. Cameras keep whatever the operator (or
    // discovery defaults) already chose — do not forcibly enable every MF
    // device, including soft/virtual cameras that are present but idle.
    bool has_real_radar = false;
    for (const auto& src : sources_) {
      if (src.is_radar) {
        has_real_radar = true;
        break;
      }
    }
    for (auto& src : sources_) {
      auto& fsm = fsms_.at(src.source_id);
      if (fsm.lifecycle() == SourceLifecycle::Failed ||
          fsm.lifecycle() == SourceLifecycle::Unavailable) {
        fsm.set_selected(false);
        continue;
      }
      if (src.is_camera) {
        continue;
      }
      if (has_real_radar && src.source_id == "sim.radar.1") {
        continue;
      }
      if (!src.is_replay && src.source_type != "sim.forceplate" &&
          src.source_id != "sim.radar.2") {
        fsm.set_selected(true);
      }
    }
  }
  if (!start_selected(error)) {
    return false;
  }
  {
    std::lock_guard lock(mu_);
    for (const auto& src : sources_) {
      if (fsms_.at(src.source_id).lifecycle() == SourceLifecycle::Recording) {
        started_source_ids.push_back(src.source_id);
      }
    }
  }
  capture::log::info("start_all_ready", "started all preparable sources",
                     {{"count", std::to_string(started_source_ids.size())}});
  return true;
}

bool SimEngine::disconnect_source(const std::string& source_id, std::string& error) {
  std::shared_ptr<capture::storage::SessionPackage> pkg;
  std::string gap_source_id;
  std::string gap_stream_id;
  int64_t gap_start_ns = 0;
  {
    std::lock_guard lock(mu_);
    auto it = fsms_.find(source_id);
    if (it == fsms_.end()) {
      error = "unknown source";
      return false;
    }
    auto tr = it->second.apply(SourceEvent::DeviceLost);
    if (!tr.ok) {
      error = tr.message;
      return false;
    }
    if (!tr.open_disconnect_gap) {
      return true;
    }
    GapRecord gap;
    gap.cause = "DISCONNECT";
    gap.start_session_time_ns = clock_.has_t0() ? clock_.session_now_ns() : 0;
    const auto& src = *std::find_if(
        sources_.begin(), sources_.end(),
        [&](const SimSourceDesc& s) { return s.source_id == source_id; });
    store_.open_gap(src.stream_id, gap);
    gap_counts_[src.stream_id] += 1;
    push_alert("WARNING", source_id, "DISCONNECT", "source disconnected");
    pkg = package_;
    gap_source_id = src.source_id;
    gap_stream_id = src.stream_id;
    gap_start_ns = gap.start_session_time_ns;
  }
  if (pkg) {
    pkg->open_gap(gap_source_id, gap_stream_id, "DISCONNECT", gap_start_ns, error);
  }
  capture::log::warn("gap_opened", "source disconnected",
                     {{"source_id", gap_source_id},
                      {"stream_id", gap_stream_id},
                      {"cause", "DISCONNECT"}});
  return true;
}

bool SimEngine::reconnect_source(const std::string& source_id, std::string& error) {
  std::shared_ptr<capture::storage::SessionPackage> pkg;
  std::string gap_stream_id;
  int64_t gap_end_ns = 0;
  {
    std::lock_guard lock(mu_);
    auto it = fsms_.find(source_id);
    if (it == fsms_.end()) {
      error = "unknown source";
      return false;
    }
    auto tr = it->second.apply(SourceEvent::Reconnected);
    if (!tr.ok) {
      error = tr.message;
      return false;
    }
    if (!tr.close_gap) {
      return true;
    }
    const auto& src = *std::find_if(
        sources_.begin(), sources_.end(),
        [&](const SimSourceDesc& s) { return s.source_id == source_id; });
    gap_end_ns = clock_.has_t0() ? clock_.session_now_ns() : 0;
    store_.close_open_gaps(src.stream_id, gap_end_ns);
    pkg = package_;
    gap_stream_id = src.stream_id;
  }
  if (pkg) {
    pkg->close_gap(gap_stream_id, gap_end_ns, error);
  }
  return true;
}

bool SimEngine::inject_fault(const std::string& source_id,
                             const std::string& fault_type, int64_t drop_count,
                             std::string& error) {
  if (fault_type == "disconnect") {
    return disconnect_source(source_id, error);
  }
  if (fault_type == "reconnect") {
    return reconnect_source(source_id, error);
  }
  if (fault_type == "drop_burst") {
    std::lock_guard lock(mu_);
    if (fsms_.find(source_id) == fsms_.end()) {
      error = "unknown source";
      return false;
    }
    drop_remaining_[source_id] = std::max<int64_t>(1, drop_count);
    return true;
  }
  error = "unknown fault_type";
  return false;
}

bool SimEngine::rescan_sources(std::string& error) {
  {
    std::lock_guard lock(mu_);
    if (session_fsm_.state() == SessionState::Recording ||
        session_fsm_.state() == SessionState::Arming ||
        session_fsm_.state() == SessionState::Stopping) {
      error = "cannot rescan while session is active";
      return false;
    }
  }

  if (rehearsal_active()) {
    if (!stop_rehearsal(error)) {
      return false;
    }
  }

  std::vector<std::string> prev_selected;
  std::unordered_set<std::string> prev_selected_stable;
  std::unordered_map<std::string, std::string> prev_config;
  {
    std::lock_guard lock(mu_);
    for (const auto& src : sources_) {
      auto it = fsms_.find(src.source_id);
      if (it == fsms_.end() || !it->second.selected()) {
        continue;
      }
      prev_selected.push_back(src.source_id);
      if (!src.stable_device_key.empty()) {
        prev_selected_stable.insert(src.stable_device_key);
      }
    }
    prev_config = config_json_;
  }

  // Release vendor USB handles before rediscovery (hung LTR11/TR13C workers
  // otherwise block Identify for tens of seconds).
  if (camera_workers_) {
    camera_workers_->force_stop_all();
  }
  if (radar_workers_) {
    radar_workers_->force_stop_all();
  }

  {
    std::lock_guard lock(mu_);
    ensure_default_sources();
    config_json_.clear();

    std::unordered_set<std::string> restore;
    for (const auto& id : prev_selected) {
      if (fsms_.find(id) != fsms_.end()) {
        restore.insert(id);
      }
    }
    if (restore.empty() && !prev_selected_stable.empty()) {
      for (const auto& src : sources_) {
        if (!src.stable_device_key.empty() &&
            prev_selected_stable.count(src.stable_device_key) > 0) {
          restore.insert(src.source_id);
        }
      }
    }
    if (!restore.empty()) {
      for (auto& [id, fsm] : fsms_) {
        fsm.set_selected(restore.count(id) > 0);
      }
    }
    for (const auto& [id, cfg] : prev_config) {
      if (fsms_.find(id) != fsms_.end()) {
        config_json_[id] = cfg;
      }
    }
    const auto count = sources_.size();
    capture::log::info(
        "sources_rescanned", "re-enumerated cameras and radars",
        {{"source_count", std::to_string(count)},
         {"restored_selection", std::to_string(prev_selected.size())}});
  }
  return true;
}

std::vector<PreflightCheckData> SimEngine::run_preflight(
    const std::vector<std::string>& source_ids, bool& ok, std::string& error) {
  (void)error;
  std::lock_guard lock(mu_);
  std::vector<std::string> ids = source_ids;
  if (ids.empty()) {
    for (const auto& src : sources_) {
      if (fsms_.at(src.source_id).selected()) {
        ids.push_back(src.source_id);
      }
    }
  }
  std::vector<PreflightCheckData> checks;
  ok = true;

  PreflightCheckData disk;
  disk.check_id = "disk.free";
  disk.name = "Disk free space";
  capture::storage::DiskWatchdog wd(package_parent_);
  const int64_t free_b = wd.free_bytes();
  if (free_b < 0) {
    disk.status = "warn";
    disk.message = "could not measure free disk space";
    disk.overridable = true;
  } else if (free_b < capture::storage::kDiskReserveBytes) {
    disk.status = "fail";
    disk.message = "free space below 10 GiB hard floor";
    disk.overridable = false;
    ok = false;
  } else {
    disk.status = "ok";
    disk.message = "free bytes=" + std::to_string(free_b);
  }
  checks.push_back(disk);

  PreflightCheckData sess;
  sess.check_id = "session.package";
  sess.name = "Session package";
  if (!package_) {
    sess.status = "fail";
    sess.message = "no session created";
    ok = false;
  } else {
    sess.status = "ok";
    sess.message = package_->root().string();
  }
  checks.push_back(sess);

  if (ids.empty()) {
    PreflightCheckData none;
    none.check_id = "sources.selected";
    none.name = "Selected sources";
    none.status = "fail";
    none.message = "no sources selected";
    ok = false;
    checks.push_back(none);
  }

  for (const auto& id : ids) {
    auto sit = std::find_if(sources_.begin(), sources_.end(),
                            [&](const SimSourceDesc& s) { return s.source_id == id; });
    if (sit == sources_.end()) {
      PreflightCheckData c;
      c.check_id = "source." + id;
      c.name = id;
      c.status = "fail";
      c.message = "unknown source";
      ok = false;
      checks.push_back(c);
      continue;
    }
    PreflightCheckData c;
    c.check_id = "source." + id;
    c.name = sit->alias;
    if (sit->is_camera) {
      if (camera_workers_) {
        PreflightCheckData w;
        w.check_id = "camera.worker." + id;
        w.name = "Camera worker (" + sit->alias + ")";
        std::string err;
        if (!CameraWorkerBridge::resolve_worker_exe().empty() &&
            CameraWorkerBridge::gstreamer_available()) {
          // Spawn outside would block under lock; report availability here and
          // require prepare/start for device open.
          const std::string enc = camera_workers_->preferred_encoder();
          w.status = "ok";
          w.message = enc.empty()
                          ? "GStreamer worker available; encoder probed at arm"
                          : ("GStreamer worker; preferred encoder=" + enc);
        } else {
          w.status = "fail";
          w.message = "camera worker or GStreamer missing";
          w.overridable = false;
          ok = false;
        }
        checks.push_back(w);

        c.status = "ok";
        c.message = "camera will record via out-of-process GStreamer worker";
      } else {
        std::string err;
        if (!open_camera_unlocked(*sit, err)) {
          c.status = "fail";
          c.message = err;
          ok = false;
        } else {
          c.status = "ok";
          c.message = "camera openable; encoding deferred (timing-only record)";
        }
      }
    } else if (sit->is_radar && radar_workers_) {
      PreflightCheckData w;
      w.check_id = "radar.worker." + id;
      w.name = "Radar worker (" + sit->alias + ")";
      if (!RadarWorkerBridge::resolve_worker_exe().empty()) {
        w.status = "ok";
        w.message = "IFX radar worker available; board probed at prepare";
      } else {
        w.status = "fail";
        w.message = "capture_worker_radar.exe not found";
        w.overridable = false;
        ok = false;
      }
      checks.push_back(w);

      c.status = "ok";
      c.message = "radar will record via out-of-process IFX worker";
    } else {
      c.status = "ok";
      c.message = "simulated source ready";
    }
    checks.push_back(c);
  }
  return checks;
}

bool SimEngine::start_rehearsal(const std::vector<std::string>& source_ids,
                                std::string& error) {
  std::vector<std::string> ids;
  std::vector<std::string> worker_cams;
  std::vector<std::string> worker_radars;
  std::string session;
  std::string pkg_path;
  int64_t t0_qpc_ns = 0;
  {
    std::lock_guard lock(mu_);
    if (session_fsm_.state() == SessionState::Recording ||
        session_fsm_.state() == SessionState::Arming) {
      error = "cannot rehearse while recording";
      return false;
    }
    ids = source_ids;
    if (ids.empty()) {
      for (const auto& src : sources_) {
        if (fsms_.at(src.source_id).selected()) {
          ids.push_back(src.source_id);
        }
      }
    }
    if (ids.empty()) {
      error = "no sources for rehearsal";
      return false;
    }
    session = session_id_;
    pkg_path = package_ ? package_->root().string() : "";
    if (clock_.has_t0()) {
      const auto& t0 = clock_.t0();
      t0_qpc_ns =
          capture::SessionClock::qpc_delta_to_ns(t0.qpc_ticks, t0.qpc_frequency);
    }
    for (const auto& id : ids) {
      auto sit = std::find_if(
          sources_.begin(), sources_.end(),
          [&](const SimSourceDesc& s) { return s.source_id == id; });
      if (sit != sources_.end() && sit->is_camera && camera_workers_) {
        worker_cams.push_back(id);
      }
      if (sit != sources_.end() && sit->is_radar && radar_workers_) {
        worker_radars.push_back(id);
      }
    }
  }

  if (camera_workers_) {
    // Stop every camera pipeline first so toggling selection cannot leave a
    // previously rehearsed device open with its LED on and no UI tile.
    std::vector<std::string> all_cams;
    {
      std::lock_guard lock(mu_);
      for (const auto& src : sources_) {
        if (src.is_camera) {
          all_cams.push_back(src.source_id);
        }
      }
    }
    for (const auto& id : all_cams) {
      std::string err;
      camera_workers_->stop_capture(id, err);
    }
    if (!worker_cams.empty()) {
      if (pkg_path.empty()) {
        error = "create a session before rehearsing cameras";
        return false;
      }
      for (const auto& id : worker_cams) {
        std::string err;
        if (!camera_workers_->spawn_for_source(id, err)) {
          std::lock_guard lock(mu_);
          push_alert("WARNING", id, "CAMERA_WORKER_SPAWN_FAILED", err);
          continue;
        }
        std::string cfg = "{}";
        {
          std::lock_guard lock(mu_);
          auto cfg_it = config_json_.find(id);
          if (cfg_it != config_json_.end() && !cfg_it->second.empty()) {
            cfg = cfg_it->second;
          }
        }
        capture::v1::ApplyConfigReply applied;
        if (!camera_workers_->apply_config(id, cfg, applied, err)) {
          std::lock_guard lock(mu_);
          push_alert("WARNING", id, "CAMERA_WORKER_CONFIG_FAILED", err);
        }
        capture::v1::StartRequest req;
        req.set_source_id(id);
        req.set_session_id(session.empty() ? "rehearsal" : session);
        req.set_session_package_path(pkg_path);
        req.set_session_t0_qpc_ns(t0_qpc_ns);
        if (!camera_workers_->start_capture(id, req, err)) {
          std::lock_guard lock(mu_);
          push_alert("WARNING", id, "CAMERA_WORKER_START_FAILED", err);
          continue;
        }
      }
    }
  }

  if (radar_workers_) {
    std::vector<std::string> all_radars;
    {
      std::lock_guard lock(mu_);
      for (const auto& src : sources_) {
        if (src.is_radar) {
          all_radars.push_back(src.source_id);
        }
      }
    }
    for (const auto& id : all_radars) {
      std::string err;
      radar_workers_->stop_capture(id, err);
    }
    if (!worker_radars.empty()) {
      if (pkg_path.empty()) {
        error = "create a session before rehearsing radar";
        return false;
      }
      for (const auto& id : worker_radars) {
        std::string err;
        if (!radar_workers_->spawn_for_source(id, err)) {
          std::lock_guard lock(mu_);
          push_alert("WARNING", id, "RADAR_WORKER_SPAWN_FAILED", err);
          continue;
        }
        std::string cfg = "{}";
        {
          std::lock_guard lock(mu_);
          auto cfg_it = config_json_.find(id);
          if (cfg_it != config_json_.end() && !cfg_it->second.empty()) {
            cfg = cfg_it->second;
          }
        }
        capture::v1::ApplyConfigReply applied;
        if (!radar_workers_->apply_config(id, cfg, applied, err)) {
          std::lock_guard lock(mu_);
          push_alert("WARNING", id, "RADAR_WORKER_CONFIG_FAILED", err);
        }
        capture::v1::StartRequest req;
        req.set_source_id(id);
        req.set_session_id(session.empty() ? "rehearsal" : session);
        req.set_session_package_path(pkg_path);
        req.set_session_t0_qpc_ns(t0_qpc_ns);
        if (!radar_workers_->start_capture(id, req, err)) {
          std::lock_guard lock(mu_);
          push_alert("WARNING", id, "RADAR_WORKER_START_FAILED", err);
          continue;
        }
      }
    }
  }

  std::lock_guard lock(mu_);
  for (const auto& id : ids) {
    auto sit = std::find_if(sources_.begin(), sources_.end(),
                            [&](const SimSourceDesc& s) { return s.source_id == id; });
    if (sit == sources_.end()) {
      error = "unknown source: " + id;
      return false;
    }
    auto& fsm = fsms_.at(id);
    fsm.set_selected(true);
    if (fsm.lifecycle() == SourceLifecycle::Discovered) {
      if (sit->is_camera && !camera_workers_) {
        std::string err;
        if (!open_camera_unlocked(*sit, err)) {
          error = err;
          return false;
        }
        auto& cam = cameras_[id];
        if (!cam) {
          error = "camera backend missing";
          return false;
        }
        if (!cam->start(err)) {
          error = err;
          return false;
        }
      }
      fsm.apply(SourceEvent::Connect);
      fsm.apply(SourceEvent::ApplyConfig);
      fsm.apply(SourceEvent::Validate);
      fsm.apply(SourceEvent::MarkReady);
    }
  }
  rehearsal_ = true;
  ensure_preview_running_unlocked();
  return true;
}

bool SimEngine::stop_rehearsal(std::string& error) {
  (void)error;
  std::vector<std::string> worker_cams;
  std::vector<std::string> worker_radars;
  {
    std::lock_guard lock(mu_);
    rehearsal_ = false;
    for (auto& [id, cam] : cameras_) {
      (void)id;
      if (cam && !recording_.load()) {
        cam->stop();
      }
    }
    if (camera_workers_ && !recording_.load()) {
      for (const auto& src : sources_) {
        if (src.is_camera) {
          worker_cams.push_back(src.source_id);
        }
      }
    }
    if (radar_workers_ && !recording_.load()) {
      for (const auto& src : sources_) {
        if (src.is_radar) {
          worker_radars.push_back(src.source_id);
        }
      }
    }
  }
  // Rehearsal is not a sealed record path — prefer force-stop so a hung
  // radar/camera worker (USB wedge) cannot block Stop Rehearse / Rescan for
  // the full StopCapture RPC timeout.
  if (!worker_cams.empty() && camera_workers_) {
    camera_workers_->force_stop_all();
  }
  if (!worker_radars.empty() && radar_workers_) {
    radar_workers_->force_stop_all();
  }
  return true;
}

bool SimEngine::rehearsal_active() const {
  return rehearsal_.load();
}

std::vector<PreviewDescriptorData> SimEngine::list_preview_descriptors(
    const std::vector<std::string>& source_ids) const {
  std::lock_guard lock(mu_);
  std::vector<PreviewDescriptorData> out;
  for (const auto& src : sources_) {
    if (!source_ids.empty() &&
        std::find(source_ids.begin(), source_ids.end(), src.source_id) ==
            source_ids.end()) {
      continue;
    }
    auto it = preview_cfg_.find(src.source_id);
    if (it != preview_cfg_.end()) {
      out.push_back(it->second);
    }
  }
  return out;
}

bool SimEngine::set_preview_config(const std::string& source_id,
                                   const bool* enabled,
                                   const uint32_t* selected_channel,
                                   PreviewDescriptorData& out,
                                   std::string& error) {
  std::lock_guard lock(mu_);
  auto it = preview_cfg_.find(source_id);
  if (it == preview_cfg_.end()) {
    error = "unknown source";
    return false;
  }
  if (enabled) {
    it->second.enabled = *enabled;
  }
  if (selected_channel) {
    it->second.selected_channel = *selected_channel;
  }
  out = it->second;
  return true;
}

std::vector<PreviewFrameData> SimEngine::take_preview_frames() {
  return latest_preview_frames();
}

std::vector<PreviewFrameData> SimEngine::latest_preview_frames() const {
  std::lock_guard lock(mu_);
  std::vector<PreviewFrameData> out;
  for (const auto& [id, slot] : preview_slots_) {
    PreviewFrameData frame;
    bool have = slot && slot->copy_latest(frame);
    auto cam = cameras_.find(id);
    if (cam != cameras_.end() && cam->second) {
      PreviewFrameData cam_frame;
      if (cam->second->copy_preview(cam_frame)) {
        cam_frame.session_time_ns =
            clock_.has_t0() ? clock_.session_now_ns() : 0;
        frame = std::move(cam_frame);
        have = true;
      }
    }
    if (have) {
      out.push_back(std::move(frame));
    }
  }
  return out;
}

HealthSnapshotData SimEngine::make_health(const SimSourceDesc& src) const {
  HealthSnapshotData h;
  h.source_id = src.source_id;
  const auto& fsm = fsms_.at(src.source_id);
  h.lifecycle = fsm.lifecycle();
  h.health = fsm.health();
  h.connected = fsm.lifecycle() != SourceLifecycle::Unavailable &&
                fsm.lifecycle() != SourceLifecycle::Discovered &&
                fsm.lifecycle() != SourceLifecycle::Failed;
  h.expected_rate_hz = src.nominal_rate_hz;
  auto rit = measured_rate_.find(src.source_id);
  h.measured_rate_hz = rit != measured_rate_.end() ? rit->second : 0;
  if (src.is_camera) {
    if (camera_workers_) {
      const auto wh = camera_workers_->health(src.source_id);
      if (wh.measured_rate_hz > 0) {
        h.measured_rate_hz = wh.measured_rate_hz;
      }
      h.dropped_count = wh.dropped_count;
      h.dropped_last_10s = wh.dropped_last_10s;
      h.data_arriving = wh.data_arriving;
      if (!wh.write_ok) {
        h.write_ok = false;
      }
      if (!wh.current_segment.empty()) {
        h.current_segment = wh.current_segment;
      }
      if (!wh.process_alive || wh.last_error_code == "WORKER_EXITED") {
        h.last_error_code = "WORKER_EXITED";
        h.last_error_message = wh.last_error_message.empty()
                                   ? "camera worker process exited"
                                   : wh.last_error_message;
        h.health = SourceHealth::Error;
        h.write_ok = false;
        h.data_arriving = false;
      } else if (!wh.last_error_code.empty()) {
        h.last_error_code = wh.last_error_code;
        h.last_error_message = wh.last_error_message;
        h.health = SourceHealth::Warning;
      }
    } else {
      auto cit = cameras_.find(src.source_id);
      if (cit != cameras_.end() && cit->second) {
        h.measured_rate_hz = cit->second->measured_rate_hz();
        const auto err = cit->second->last_error();
        if (!err.empty()) {
          h.last_error_code = "CAMERA";
          h.last_error_message = err;
        }
      }
    }
  }
  if (src.is_radar && radar_workers_) {
    const auto wh = radar_workers_->health(src.source_id);
    if (wh.measured_rate_hz > 0) {
      h.measured_rate_hz = wh.measured_rate_hz;
    }
    h.dropped_count = wh.dropped_count;
    h.dropped_last_10s = wh.dropped_last_10s;
    h.data_arriving = wh.data_arriving;
    if (!wh.write_ok) {
      h.write_ok = false;
    }
    if (!wh.current_segment.empty()) {
      h.current_segment = wh.current_segment;
    }
    if (!wh.process_alive || wh.last_error_code == "WORKER_EXITED") {
      h.last_error_code = "WORKER_EXITED";
      h.last_error_message = wh.last_error_message.empty()
                                 ? "radar worker process exited"
                                 : wh.last_error_message;
      h.health = SourceHealth::Error;
      h.write_ok = false;
      h.data_arriving = false;
    } else if (!wh.last_error_code.empty()) {
      h.last_error_code = wh.last_error_code;
      h.last_error_message = wh.last_error_message;
      h.health = SourceHealth::Warning;
    }
  }
  if (h.health != SourceHealth::Error) {
    h.data_arriving = h.measured_rate_hz > 0.1;
    h.write_ok = !(package_ && package_->writes_blocked());
  }
  if (package_ && h.current_segment.empty()) {
    h.current_segment = "mcap";
  }
  h.session_time_ns = clock_.has_t0() ? clock_.session_now_ns() : 0;
  auto snap = store_.snapshot(src.stream_id);
  h.gap_count = static_cast<int32_t>(snap.gaps.size());
  auto git = gap_counts_.find(src.stream_id);
  if (git != gap_counts_.end()) {
    h.gap_count = static_cast<int32_t>(
        std::max<int64_t>(h.gap_count, git->second));
  }
  for (const auto& gap : snap.gaps) {
    if (gap.end_session_time_ns < 0) {
      h.has_open_gap = true;
      h.open_gap_cause = gap.cause;
      h.open_gap_start_ns = gap.start_session_time_ns;
      break;
    }
  }
  if (fsm.health() == SourceHealth::Error) {
    h.health = SourceHealth::Error;
  }
  return h;
}

std::vector<HealthSnapshotData> SimEngine::health_snapshots() const {
  std::lock_guard lock(mu_);
  std::vector<HealthSnapshotData> out;
  for (const auto& src : sources_) {
    out.push_back(make_health(src));
  }
  return out;
}

DiskStatusData SimEngine::disk_status() const {
  std::lock_guard lock(mu_);
  DiskStatusData d;
  capture::storage::DiskWatchdog wd(package_parent_);
  d.free_bytes = wd.free_bytes();
  d.reserve_bytes = capture::storage::kDiskReserveBytes;
  d.writers_blocked = package_ && package_->writes_blocked();
  if (d.free_bytes >= 0 && d.free_bytes <= d.reserve_bytes) {
    d.headroom_level = "CRITICAL";
  } else if (d.free_bytes >= 0 &&
             d.free_bytes < d.reserve_bytes + 5LL * 1024 * 1024 * 1024) {
    d.headroom_level = "WARNING";
  } else {
    d.headroom_level = "INFO";
  }
  return d;
}

SessionViewData SimEngine::session_view() const {
  SessionViewData v;
  std::shared_ptr<capture::storage::SessionPackage> pkg;
  {
    std::lock_guard lock(mu_);
    v.session_id = session_id_;
    v.state = session_fsm_.state();
    v.elapsed_session_ns = clock_.has_t0() ? clock_.session_now_ns() : 0;
    v.t0_wall_clock_utc = t0_wall_utc_;
    v.checkpoints = checkpoints_;
    v.annotations = annotations_;
    v.sync_anchors = sync_anchors_;
    v.alerts = alerts_;
    v.rehearsal_active = rehearsal_.load();
    if (review_mode_) {
      v.package_path = review_package_path_.string();
      v.lanes = review_lanes_;
      int64_t max_ns = 0;
      for (const auto& lane : v.lanes) {
        for (const auto& g : lane.gaps) {
          max_ns = (std::max)(max_ns, g.start_session_time_ns);
          if (g.end_session_time_ns >= 0) {
            max_ns = (std::max)(max_ns, g.end_session_time_ns);
          }
        }
      }
      for (const auto& cp : v.checkpoints) {
        max_ns = (std::max)(max_ns, cp.effective_timestamp_ns);
      }
      v.elapsed_session_ns = max_ns;
      return v;
    }
    {
      capture::storage::DiskWatchdog wd(package_parent_);
      v.disk.free_bytes = wd.free_bytes();
      v.disk.reserve_bytes = capture::storage::kDiskReserveBytes;
      v.disk.writers_blocked = package_ && package_->writes_blocked();
      v.disk.headroom_level = "INFO";
      if (v.disk.free_bytes >= 0 && v.disk.free_bytes <= v.disk.reserve_bytes) {
        v.disk.headroom_level = "CRITICAL";
      } else if (v.disk.free_bytes >= 0 &&
                 v.disk.free_bytes <
                     v.disk.reserve_bytes + 5LL * 1024 * 1024 * 1024) {
        v.disk.headroom_level = "WARNING";
      }
    }
    for (const auto& src : sources_) {
      LaneViewData lane;
      lane.source_id = src.source_id;
      lane.stream_id = src.stream_id;
      lane.modality = src.modality;
      lane.alias = src.alias;
      lane.lifecycle = fsms_.at(src.source_id).lifecycle();
      auto snap = store_.snapshot(src.stream_id);
      lane.gaps = snap.gaps;
      if (!snap.samples.empty()) {
        lane.first_sample_session_ns = snap.samples.front().session_time_ns;
        lane.last_sample_session_ns = snap.samples.back().session_time_ns;
      }
      v.lanes.push_back(std::move(lane));
    }
    pkg = package_;
  }
  // sample_count reaches into the package's own lock, so query it unlocked.
  if (pkg) {
    v.package_path = pkg->root().string();
    for (auto& lane : v.lanes) {
      lane.sample_count = pkg->sample_count(lane.stream_id);
    }
  }
  // External workers own the open segment; integrity lags until SegmentSealed.
  {
    std::lock_guard lock(mu_);
    for (auto& lane : v.lanes) {
      for (const auto& src : sources_) {
        if (src.stream_id != lane.stream_id) {
          continue;
        }
        int64_t live = 0;
        if (src.is_radar && radar_workers_) {
          live = radar_workers_->health(src.source_id).recorded_sample_count;
        } else if (src.is_camera && camera_workers_) {
          live = camera_workers_->health(src.source_id).recorded_sample_count;
        }
        if (live > lane.sample_count) {
          lane.sample_count = live;
        }
        break;
      }
    }
  }
  return v;
}

bool SimEngine::is_recording() const { return recording_.load(); }

int64_t SimEngine::session_elapsed_ns() const {
  std::lock_guard lock(mu_);
  if (!clock_.has_t0()) {
    return 0;
  }
  return clock_.session_now_ns();
}

RecordingStats SimEngine::recording_stats() const {
  RecordingStats stats;
  std::shared_ptr<capture::storage::SessionPackage> pkg;
  {
    std::lock_guard lock(mu_);
    stats.state = session_fsm_.state();
    stats.elapsed_session_ns = clock_.has_t0() ? clock_.session_now_ns() : 0;
    stats.checkpoint_count = static_cast<int64_t>(checkpoints_.size());
    stats.annotation_count = static_cast<int64_t>(annotations_.size());
    stats.sync_anchor_count = static_cast<int64_t>(sync_anchors_.size());
    for (const auto& stream_id : store_.stream_ids()) {
      auto snap = store_.snapshot(stream_id);
      StreamStats ss;
      ss.stream_id = snap.stream_id;
      ss.source_id = snap.source_id;
      ss.sample_count = static_cast<int64_t>(snap.samples.size());
      ss.gap_count = static_cast<int64_t>(snap.gaps.size());
      auto git = gap_counts_.find(stream_id);
      if (git != gap_counts_.end()) {
        ss.gap_count = std::max(ss.gap_count, git->second);
      }
      for (const auto& gap : snap.gaps) {
        if (gap.end_session_time_ns < 0) {
          ++ss.open_gap_count;
        }
      }
      stats.total_samples += ss.sample_count;
      stats.streams.push_back(std::move(ss));
    }
    pkg = package_;
  }
  if (pkg) {
    stats.package_path = pkg->root().string();
    stats.total_samples = 0;
    for (auto& ss : stats.streams) {
      ss.sample_count = pkg->sample_count(ss.stream_id);
      stats.total_samples += ss.sample_count;
    }
  }
  {
    std::lock_guard lock(mu_);
    stats.total_samples = 0;
    for (auto& ss : stats.streams) {
      for (const auto& src : sources_) {
        if (src.stream_id != ss.stream_id) {
          continue;
        }
        int64_t live = 0;
        if (src.is_radar && radar_workers_) {
          live = radar_workers_->health(src.source_id).recorded_sample_count;
        } else if (src.is_camera && camera_workers_) {
          live = camera_workers_->health(src.source_id).recorded_sample_count;
        }
        if (live > ss.sample_count) {
          ss.sample_count = live;
        }
        break;
      }
      stats.total_samples += ss.sample_count;
    }
  }
  return stats;
}

void SimEngine::stop_recording_thread() {
  recording_ = false;
  if (worker_.joinable()) {
    worker_.join();
  }
}

void SimEngine::stop_preview_thread() {
  preview_running_ = false;
  if (preview_worker_.joinable()) {
    preview_worker_.join();
  }
}

void SimEngine::ensure_preview_running_unlocked() {
  if (preview_running_.load()) {
    return;
  }
  preview_running_ = true;
  if (preview_worker_.joinable()) {
    preview_worker_.join();
  }
  preview_worker_ = std::thread([this] { preview_loop(); });
}

void SimEngine::publish_camera_preview_unlocked(const SimSourceDesc& src,
                                                int64_t session_ns) {
  auto cfg_it = preview_cfg_.find(src.source_id);
  if (cfg_it == preview_cfg_.end() || !cfg_it->second.enabled) {
    return;
  }
  auto cam = cameras_.find(src.source_id);
  if (cam == cameras_.end() || !cam->second) {
    return;
  }
  // The in-process grabber only keeps a latest-wins snapshot, so the preview
  // stream has to pull from it; unlike the worker path nothing pushes here.
  PreviewFrameData frame;
  if (!cam->second->copy_preview(frame)) {
    return;
  }
  auto& last = camera_preview_seq_[src.source_id];
  if (frame.sequence != 0 && frame.sequence == last) {
    return;
  }
  last = frame.sequence;
  frame.source_id = src.source_id;
  frame.session_time_ns = session_ns;
  auto slot = preview_slots_.find(src.source_id);
  if (slot != preview_slots_.end() && slot->second) {
    slot->second->publish(std::move(frame));
  }
}

void SimEngine::generate_sim_preview_unlocked(const SimSourceDesc& src,
                                              int64_t session_ns) {
  auto cfg_it = preview_cfg_.find(src.source_id);
  if (cfg_it == preview_cfg_.end() || !cfg_it->second.enabled) {
    return;
  }
  if (src.is_camera) {
    return;  // real camera path fills slots
  }
  if (src.is_radar && radar_workers_) {
    return;  // radar worker sends MATRIX_2D preview
  }
  const auto& cfg = cfg_it->second;
  PreviewFrameData f;
  f.source_id = src.source_id;
  f.stream_id = src.stream_id;
  f.kind = cfg.kind;
  f.session_time_ns = session_ns;
  f.sequence = ++preview_seq_[src.source_id];
  f.selected_channel = cfg.selected_channel;

  if (cfg.kind == PreviewKind::ImageThumbnail) {
    f.width = 320;
    f.height = 240;
    f.pixel_format = "rgb24";
    f.image.resize(static_cast<size_t>(f.width) * f.height * 3);
    for (uint32_t y = 0; y < f.height; ++y) {
      for (uint32_t x = 0; x < f.width; ++x) {
        const size_t i = (static_cast<size_t>(y) * f.width + x) * 3;
        const float t = static_cast<float>(f.sequence) * 0.05f;
        f.image[i] = static_cast<uint8_t>(80 + 40 * std::sin(t + x * 0.05f));
        f.image[i + 1] = static_cast<uint8_t>(100 + 50 * std::sin(t * 0.7f + y * 0.04f));
        f.image[i + 2] = static_cast<uint8_t>(140 + 60 * std::sin(t * 1.3f));
      }
    }
  } else if (cfg.kind == PreviewKind::TraceBlock ||
             cfg.kind == PreviewKind::TraceSingle ||
             cfg.kind == PreviewKind::ScalarSeries ||
             cfg.kind == PreviewKind::VectorProfile) {
    const uint32_t channels =
        cfg.kind == PreviewKind::TraceBlock
            ? 8
            : (cfg.kind == PreviewKind::VectorProfile ? 1 : 1);
    const uint32_t points =
        cfg.kind == PreviewKind::ScalarSeries
            ? 64
            : (cfg.kind == PreviewKind::VectorProfile ? 256 : 256);
    f.channel_count = channels;
    f.points_per_channel = points;
    f.display_min = -1.f;
    f.display_max = 1.f;
    f.units = src.modality == "emg" ? "mV" : "a.u.";
    f.decimated_from_rate_hz = src.nominal_rate_hz;
    f.samples.resize(static_cast<size_t>(channels) * points);
    for (uint32_t c = 0; c < channels; ++c) {
      f.channel_names.push_back(cfg.available_channels.empty()
                                    ? ("ch" + std::to_string(c))
                                    : cfg.available_channels[c % cfg.available_channels.size()]);
      for (uint32_t p = 0; p < points; ++p) {
        const float phase = (f.sequence + p) * 0.08f + c * 0.4f;
        f.samples[static_cast<size_t>(c) * points + p] =
            std::sin(phase) * 0.7f + hash_noise(f.sequence + p, static_cast<int>(c)) * 0.1f;
      }
    }
  } else if (cfg.kind == PreviewKind::Orientation) {
    const double t = f.sequence * 0.02;
    f.qw = std::cos(t * 0.5);
    f.qx = 0;
    f.qy = std::sin(t * 0.5);
    f.qz = 0;
    f.accel_magnitude = 9.81 + 0.2 * std::sin(t * 3);
    f.gyro_magnitude = 0.1 + 0.05 * std::cos(t * 2);
  } else if (cfg.kind == PreviewKind::Matrix2D) {
    if (!try_load_ifx_radar_preview(f, src.source_id)) {
      f.rows = 64;
      f.cols = 128;
      f.display_min = 0;
      f.display_max = 1;
      f.samples.resize(static_cast<size_t>(f.rows) * f.cols);
      for (uint32_t r = 0; r < f.rows; ++r) {
        for (uint32_t c = 0; c < f.cols; ++c) {
          const float v =
              0.5f + 0.5f * std::sin((r + f.sequence) * 0.1f) *
                         std::cos((c + f.sequence * 0.3f) * 0.05f);
          f.samples[static_cast<size_t>(r) * f.cols + c] = v;
        }
      }
    }
  }
  if (auto it = preview_slots_.find(src.source_id); it != preview_slots_.end() &&
                                                     it->second) {
    it->second->publish(std::move(f));
  }
}

void SimEngine::supervise_external_workers() {
  if (!recording_.load() && !rehearsal_.load()) {
    return;
  }
  std::vector<std::string> dead;
  {
    std::lock_guard lock(mu_);
    for (const auto& src : sources_) {
      if (!fsms_.at(src.source_id).selected()) {
        continue;
      }
      if (fsms_.at(src.source_id).health() == SourceHealth::Error) {
        continue;  // already DeviceLost
      }
      if (src.is_camera && camera_workers_ &&
          camera_workers_->has_worker(src.source_id) &&
          camera_workers_->worker_died(src.source_id)) {
        dead.push_back(src.source_id);
      }
      if (src.is_radar && radar_workers_ &&
          radar_workers_->has_worker(src.source_id) &&
          radar_workers_->worker_died(src.source_id)) {
        dead.push_back(src.source_id);
      }
    }
  }
  for (const auto& id : dead) {
    std::string err;
    if (!disconnect_source(id, err)) {
      capture::log::warn("supervise_disconnect_failed", err,
                         {{"source_id", id}});
    }
    // Drop the dead worker slot so a later Start/Rescan can respawn.
    if (camera_workers_ && camera_workers_->has_worker(id)) {
      camera_workers_->force_stop_worker(id);
    }
    if (radar_workers_ && radar_workers_->has_worker(id)) {
      radar_workers_->force_stop_worker(id);
    }
  }
}

void SimEngine::preview_loop() {
  using clock = std::chrono::steady_clock;
  auto next = clock::now();
  while (preview_running_.load()) {
    next += std::chrono::milliseconds(50);  // 20 Hz tick; per-source rates gated below
    drain_camera_workers();
    drain_radar_workers();
    supervise_external_workers();
    {
      std::lock_guard lock(mu_);
      const int64_t session_ns = clock_.has_t0() ? clock_.session_now_ns() : 0;
      const bool live = recording_.load() || rehearsal_.load() ||
                        session_fsm_.state() == SessionState::Preparing;
      if (live) {
        for (const auto& src : sources_) {
          auto& fsm = fsms_.at(src.source_id);
          if (!fsm.selected()) {
            continue;
          }
          auto cfg = preview_cfg_.find(src.source_id);
          if (cfg == preview_cfg_.end() || !cfg->second.enabled) {
            continue;
          }
          // Simple rate gate using sequence and max_rate_hz.
          const double rate = std::max(1.0, cfg->second.max_rate_hz);
          const int64_t every = static_cast<int64_t>(std::lround(20.0 / rate));
          if (every > 1 && (preview_seq_[src.source_id] % every) != 0 &&
              preview_seq_[src.source_id] != 0) {
            // still bump for cameras via generate skip
          }
          if (src.is_camera) {
            if (!camera_workers_) {
              auto cit = cameras_.find(src.source_id);
              if (cit != cameras_.end() && cit->second) {
                if (!cit->second->is_running() &&
                    (rehearsal_.load() || recording_.load())) {
                  std::string err;
                  cit->second->start(err);
                }
                publish_camera_preview_unlocked(src, session_ns);
              }
            }
            continue;
          }
          if (src.is_radar && radar_workers_) {
            continue;
          }
          // Synthetic modalities: show preview whenever selected in a live
          // session (Preparing/Rehearse/Record), not only after Arm/Ready.
          if (fsm.selected()) {
            generate_sim_preview_unlocked(src, session_ns);
          }
        }
      }
    }
    std::this_thread::sleep_until(next);
  }
}

void SimEngine::recording_loop() {
  using clock = std::chrono::steady_clock;
  struct Pending {
    std::string stream_id;
    capture::storage::SamplePoint point;
  };
  std::vector<Pending> pending;
  auto next = clock::now();
  auto last_disk = clock::now();
  while (recording_.load()) {
    next += std::chrono::milliseconds(10);
    pending.clear();
    drain_camera_workers();
    drain_radar_workers();
    std::shared_ptr<capture::storage::SessionPackage> pkg;
    bool poll_disk_due = false;
    {
      std::lock_guard lock(mu_);
      if (!clock_.has_t0()) {
        break;
      }
      pkg = package_;
      if (pkg && clock::now() - last_disk > std::chrono::seconds(5)) {
        poll_disk_due = true;
        last_disk = clock::now();
      }
      const int64_t session_ns = clock_.session_now_ns();
      const int64_t host_ns = clock_.now_monotonic_ns();
      for (const auto& src : sources_) {
        auto& fsm = fsms_.at(src.source_id);
        if (fsm.lifecycle() != SourceLifecycle::Recording) {
          continue;
        }
        if (fsm.health() == SourceHealth::Error) {
          continue;
        }

        if (src.is_camera) {
          // Out-of-process workers write MKV + timing MCAP themselves.
          if (camera_workers_) {
            continue;
          }
          auto cit = cameras_.find(src.source_id);
          if (cit == cameras_.end() || !cit->second) {
            continue;
          }
          auto timings = cit->second->drain_timings();
          for (const auto& t : timings) {
            SampleRecord sample;
            sample.sequence = t.sequence;
            sample.session_time_ns = session_ns;
            sample.host_arrival_ns = t.host_arrival_ns;
            sample.quality_flags = 0;
            store_.append_sample(src.stream_id, sample);
            capture::storage::SamplePoint pt;
            pt.sequence = sample.sequence;
            pt.session_time_ns = sample.session_time_ns;
            pt.host_arrival_ns = sample.host_arrival_ns;
            pt.quality_flags = sample.quality_flags;
            pending.push_back({src.stream_id, pt});
            ++samples_in_window_[src.source_id];
          }
          continue;
        }

        if (src.is_radar && radar_workers_) {
          continue;
        }

        auto drop_it = drop_remaining_.find(src.source_id);
        if (drop_it != drop_remaining_.end() && drop_it->second > 0) {
          --drop_it->second;
          continue;
        }
        int produce = 1;
        if (src.nominal_rate_hz >= 200) {
          produce = static_cast<int>(src.nominal_rate_hz / 100.0);
        }
        if (src.modality == "emg") {
          // One EmgBatch message covering `produce` samples × channels.
          SampleRecord sample;
          sample.sequence = ++sequence_counter_;
          sample.session_time_ns = session_ns;
          sample.host_arrival_ns = host_ns;
          sample.quality_flags = 0;
          store_.append_sample(src.stream_id, sample);
          capture::storage::SamplePoint pt;
          pt.sequence = sample.sequence;
          pt.session_time_ns = sample.session_time_ns;
          pt.host_arrival_ns = sample.host_arrival_ns;
          pt.quality_flags = sample.quality_flags;
          const auto& chans = preview_cfg_.count(src.source_id)
                                  ? preview_cfg_.at(src.source_id).available_channels
                                  : std::vector<std::string>{};
          const int channel_count =
              chans.empty() ? 8 : static_cast<int>(chans.size());
          fill_sim_emg_payload(pt, channel_count, produce, sample.sequence);
          pending.push_back({src.stream_id, std::move(pt)});
          samples_in_window_[src.source_id] += produce;
        } else {
          for (int i = 0; i < produce; ++i) {
            SampleRecord sample;
            sample.sequence = ++sequence_counter_;
            sample.session_time_ns = session_ns;
            sample.host_arrival_ns = host_ns;
            sample.quality_flags = 0;
            store_.append_sample(src.stream_id, sample);
            capture::storage::SamplePoint pt;
            pt.sequence = sample.sequence;
            pt.session_time_ns = sample.session_time_ns;
            pt.host_arrival_ns = sample.host_arrival_ns;
            pt.quality_flags = sample.quality_flags;
            if (src.modality == "imu") {
              const auto& sensors =
                  preview_cfg_.count(src.source_id)
                      ? preview_cfg_.at(src.source_id).available_channels
                      : std::vector<std::string>{"pelvis", "sternum", "head",
                                                 "l_upper", "r_upper", "l_fore",
                                                 "r_fore"};
              fill_sim_imu_payload(pt, sensors);
            }
            pending.push_back({src.stream_id, std::move(pt)});
            ++samples_in_window_[src.source_id];
          }
        }
        auto& wstart = window_start_ns_[src.source_id];
        if (wstart == 0) {
          wstart = host_ns;
        }
        if (host_ns - wstart >= 1000000000LL) {
          measured_rate_[src.source_id] =
              samples_in_window_[src.source_id] * 1e9 /
              static_cast<double>(host_ns - wstart);
          samples_in_window_[src.source_id] = 0;
          wstart = host_ns;
        }
      }
    }
    // Storage I/O happens with no engine lock held, so a stalled volume delays
    // only this thread's writes, never a control RPC.
    if (pkg) {
      if (poll_disk_due) {
        pkg->poll_disk();
      }
      if (!pkg->writes_blocked()) {
        std::string err;
        for (const auto& p : pending) {
          pkg->write_sample(p.stream_id, p.point, err);
        }
      }
    }
    std::this_thread::sleep_until(next);
  }
}

}  // namespace capture::daemon
