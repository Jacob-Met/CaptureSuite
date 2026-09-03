// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/external_worker_bridge.hpp"

#include "capture_daemon/plugin_registry.hpp"
#include "capture/logging.hpp"

#include <cctype>
#include <cstdlib>

#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

namespace capture::daemon {
namespace {

std::filesystem::path exe_dir() {
  wchar_t buf[MAX_PATH];
  const DWORD n = GetModuleFileNameW(nullptr, buf, MAX_PATH);
  if (n == 0 || n >= MAX_PATH) {
    return {};
  }
  return std::filesystem::path(buf).parent_path();
}

std::string env_dup(const char* name) {
  char* v = nullptr;
  size_t len = 0;
  if (_dupenv_s(&v, &len, name) != 0 || v == nullptr) {
    return {};
  }
  std::string out(v);
  free(v);
  return out;
}

bool process_alive(const SpawnedWorker& worker) {
  if (worker.process == nullptr || worker.process == INVALID_HANDLE_VALUE) {
    return false;
  }
  const DWORD wait = WaitForSingleObject(worker.process, 0);
  return wait == WAIT_TIMEOUT;
}

}  // namespace

PreviewFrameData external_preview_from_proto(
    const capture::v1::PreviewFrame& in) {
  PreviewFrameData out;
  out.source_id = in.source_id();
  out.stream_id = in.stream_id();
  out.session_time_ns = in.session_time_ns();
  out.sequence = in.sequence();
  out.dropped_since_last = in.dropped_since_last();
  out.selected_channel = in.selected_channel();
  if (in.has_matrix()) {
    out.kind = PreviewKind::Matrix2D;
    const auto& mat = in.matrix();
    out.rows = mat.rows();
    out.cols = mat.cols();
    out.display_min = mat.display_min();
    out.display_max = mat.display_max();
    out.row_axis = mat.row_axis();
    out.col_axis = mat.col_axis();
    out.samples.assign(mat.values().begin(), mat.values().end());
  } else if (in.has_trace()) {
    const auto& tr = in.trace();
    out.kind = in.kind() == capture::v1::PREVIEW_KIND_TRACE_SINGLE
                   ? PreviewKind::TraceSingle
                   : PreviewKind::TraceBlock;
    out.channel_count = tr.channel_count();
    out.points_per_channel = tr.points_per_channel();
    out.display_min = tr.display_min();
    out.display_max = tr.display_max();
    out.units = tr.units();
    out.decimated_from_rate_hz = tr.decimated_from_rate_hz();
    out.channel_names.assign(tr.channel_names().begin(),
                             tr.channel_names().end());
    out.samples.assign(tr.samples().begin(), tr.samples().end());
  } else if (in.has_image()) {
    out.kind = PreviewKind::ImageThumbnail;
    const auto& img = in.image();
    out.image.assign(img.data().begin(), img.data().end());
    out.width = img.width();
    out.height = img.height();
    out.pixel_format = img.pixel_format().empty() ? "jpeg" : img.pixel_format();
  } else if (in.has_orientation()) {
    out.kind = PreviewKind::Orientation;
    const auto& o = in.orientation();
    out.qw = o.qw();
    out.qx = o.qx();
    out.qy = o.qy();
    out.qz = o.qz();
    out.accel_magnitude = o.accel_magnitude();
    out.gyro_magnitude = o.gyro_magnitude();
  }
  return out;
}

ExternalWorkerPluginSpec camera_worker_plugin_spec_builtin() {
  ExternalWorkerPluginSpec s;
  s.plugin_id = "camera.gstreamer";
  s.family = "camera";
  s.enable_env = "CAPTURE_USE_CAMERA_WORKER";
  s.exe_env = "CAPTURE_CAMERA_WORKER_EXE";
  s.exe_name = "capture_worker_camera.exe";
  s.workers_subdir = "camera";
  s.require_gstreamer = true;
  s.spawn_timeout = std::chrono::milliseconds(25000);
  s.stop_timeout = std::chrono::milliseconds(120000);
  s.overload_code = "OVERLOAD_DROP";
  s.overload_message = "record queue overrun";
  return s;
}

ExternalWorkerPluginSpec radar_worker_plugin_spec_builtin() {
  ExternalWorkerPluginSpec s;
  s.plugin_id = "radar.ifx";
  s.family = "radar";
  s.enable_env = "CAPTURE_USE_RADAR_WORKER";
  s.exe_env = "CAPTURE_RADAR_WORKER_EXE";
  s.exe_name = "capture_worker_radar.exe";
  s.workers_subdir = "radar";
  s.require_gstreamer = false;
  s.spawn_timeout = std::chrono::milliseconds(8000);
  s.enumerate_timeout = std::chrono::milliseconds(20000);
  s.overload_code = "OVERLOAD";
  s.overload_message = "radar FIFO overflow";
  return s;
}

ExternalWorkerPluginSpec camera_worker_plugin_spec() {
  // Lazy: avoid circular init with PluginRegistry::ensure_builtins.
  static bool loading = false;
  if (loading) {
    return camera_worker_plugin_spec_builtin();
  }
  loading = true;
  ExternalWorkerPluginSpec out;
  try {
    const auto& reg = PluginRegistry::instance();
    if (const auto* p = reg.find("camera.gstreamer")) {
      out = p->spec;
      loading = false;
      return out;
    }
  } catch (...) {
  }
  loading = false;
  return camera_worker_plugin_spec_builtin();
}

ExternalWorkerPluginSpec radar_worker_plugin_spec() {
  static bool loading = false;
  if (loading) {
    return radar_worker_plugin_spec_builtin();
  }
  loading = true;
  ExternalWorkerPluginSpec out;
  try {
    const auto& reg = PluginRegistry::instance();
    if (const auto* p = reg.find("radar.ifx")) {
      out = p->spec;
      loading = false;
      return out;
    }
  } catch (...) {
  }
  loading = false;
  return radar_worker_plugin_spec_builtin();
}

ExternalWorkerBridge::ExternalWorkerBridge(std::string instance_id,
                                           ExternalWorkerPluginSpec spec)
    : instance_id_(std::move(instance_id)),
      spec_(std::move(spec)),
      host_(job_, instance_id_) {
  std::string err;
  if (!job_.create(err)) {
    capture::log::error(spec_.family + "_worker_job", err);
  }
}

ExternalWorkerBridge::~ExternalWorkerBridge() { stop_all(); }

std::string ExternalWorkerBridge::sanitize_worker_id(
    const std::string& source_id) const {
  std::string out = spec_.family.substr(0, 3) + "-";
  for (unsigned char c : source_id) {
    if (std::isalnum(c) || c == '.' || c == '_' || c == '-') {
      out.push_back(static_cast<char>(c));
    } else {
      out.push_back('_');
    }
  }
  if (out.size() > 96) {
    out.resize(96);
  }
  return out;
}

bool ExternalWorkerBridge::forced_off(const ExternalWorkerPluginSpec& spec) {
  const std::string v = env_dup(spec.enable_env.c_str());
  return !v.empty() && v[0] == '0';
}

std::filesystem::path ExternalWorkerBridge::resolve_gstreamer_root() {
  const std::string root = env_dup("GSTREAMER_1_0_ROOT_MSVC_X86_64");
  if (!root.empty() && std::filesystem::exists(root)) {
    return root;
  }
  const auto dir = exe_dir();
  const std::filesystem::path candidates[] = {
      dir / ".." / ".." / ".." / "third_party" / "gstreamer" / "gstreamer" /
          "1.0" / "msvc_x86_64",
      dir / ".." / ".." / "third_party" / "gstreamer" / "gstreamer" / "1.0" /
          "msvc_x86_64",
      dir / ".." / "third_party" / "gstreamer" / "gstreamer" / "1.0" /
          "msvc_x86_64",
  };
  for (const auto& c : candidates) {
    std::error_code ec;
    const auto canon = std::filesystem::weakly_canonical(c, ec);
    if (!ec && std::filesystem::exists(canon / "bin")) {
      return canon;
    }
  }
  return {};
}

bool ExternalWorkerBridge::gstreamer_available() {
  return !resolve_gstreamer_root().empty();
}

std::filesystem::path ExternalWorkerBridge::resolve_worker_exe(
    const ExternalWorkerPluginSpec& spec) {
  const std::string override_path = env_dup(spec.exe_env.c_str());
  if (!override_path.empty()) {
    std::filesystem::path p(override_path);
    if (std::filesystem::exists(p)) {
      return p;
    }
  }
  const auto dir = exe_dir();
  const std::filesystem::path candidates[] = {
      dir / spec.exe_name,
      dir / "workers" / spec.workers_subdir / spec.exe_name,
      dir / ".." / "workers" / spec.workers_subdir / spec.exe_name,
      dir / "plugins" / spec.workers_subdir / spec.exe_name,
      dir / ".." / "plugins" / spec.workers_subdir / spec.exe_name,
      dir / ".." / ".." / "plugins" / spec.workers_subdir / spec.exe_name,
  };
  for (const auto& c : candidates) {
    std::error_code ec;
    const auto canon = std::filesystem::weakly_canonical(c, ec);
    if (!ec && std::filesystem::exists(canon)) {
      return canon;
    }
  }
  return {};
}

bool ExternalWorkerBridge::should_enable(const ExternalWorkerPluginSpec& spec) {
  if (forced_off(spec)) {
    return false;
  }
  const std::string v = env_dup(spec.enable_env.c_str());
  if (!v.empty() && v[0] != '0') {
    return true;
  }
  if (spec.skip_auto_in_unit_tests) {
    wchar_t mod[MAX_PATH];
    if (GetModuleFileNameW(nullptr, mod, MAX_PATH) > 0) {
      const std::wstring path(mod);
      if (path.find(L"capture_core_tests") != std::wstring::npos) {
        return false;
      }
    }
  }
  if (resolve_worker_exe(spec).empty()) {
    return false;
  }
  if (spec.require_gstreamer && !gstreamer_available()) {
    return false;
  }
  return true;
}

bool ExternalWorkerBridge::enumerate(
    std::vector<capture::v1::SourceInstance>& out, std::string& error) {
  out.clear();
  const auto exe = resolve_worker_exe();
  if (exe.empty()) {
    error = spec_.exe_name + " not found (set " + spec_.exe_env + ")";
    return false;
  }
  SpawnedWorker worker;
  if (!host_.spawn(exe, spec_.family + "-enum", spec_.plugin_id, worker, error,
                   spec_.enumerate_timeout)) {
    return false;
  }
  out.assign(worker.manifest.sources().begin(),
             worker.manifest.sources().end());
  host_.stop(worker);
  return true;
}

bool ExternalWorkerBridge::spawn_for_source(const std::string& source_id,
                                            std::string& error) {
  {
    std::lock_guard lock(mu_);
    auto it = workers_.find(source_id);
    if (it != workers_.end()) {
      if (process_alive(it->second)) {
        return true;
      }
      // Slot occupied by a dead process (mid-session kill / USB wedge). Clear
      // it so the next arm can reopen the device without a full daemon restart.
      capture::log::warn(spec_.family + "_worker_respawn",
                         "replacing dead worker process",
                         {{"source_id", source_id}});
      host_.stop(it->second);
      workers_.erase(it);
      connected_.erase(source_id);
      health_.erase(source_id);
    }
  }
  const auto exe = resolve_worker_exe();
  if (exe.empty()) {
    error = spec_.exe_name + " not found (set " + spec_.exe_env + ")";
    return false;
  }
  if (spec_.require_gstreamer && !gstreamer_available()) {
    error = "GStreamer not found (set GSTREAMER_1_0_ROOT_MSVC_X86_64)";
    return false;
  }
  SpawnedWorker worker;
  const std::string worker_id = sanitize_worker_id(source_id);
  if (!host_.spawn(exe, worker_id, spec_.plugin_id, worker, error,
                   spec_.spawn_timeout)) {
    return false;
  }
  std::string encoder;
  const auto enc = worker.manifest.capabilities().find("preferred_encoder");
  if (enc != worker.manifest.capabilities().end()) {
    encoder = enc->second;
  }
  std::lock_guard lock(mu_);
  if (workers_.count(source_id)) {
    host_.stop(worker);
    return true;
  }
  if (preferred_encoder_.empty() && !encoder.empty()) {
    preferred_encoder_ = encoder;
  }
  workers_.emplace(source_id, std::move(worker));
  connected_[source_id] = false;
  ExternalWorkerHealth h;
  h.encoder_name = encoder;
  health_[source_id] = std::move(h);
  capture::log::info(spec_.family + "_worker_spawned",
                     spec_.family + " worker ready",
                     {{"source_id", source_id}, {"worker_id", worker_id}});
  return true;
}

bool ExternalWorkerBridge::connect_source(const std::string& source_id,
                                          std::string& error) {
  std::lock_guard lock(mu_);
  auto it = workers_.find(source_id);
  if (it == workers_.end()) {
    error = "no " + spec_.family + " worker for " + source_id;
    return false;
  }
  if (connected_[source_id]) {
    return true;
  }
  capture::v1::ConnectReply reply;
  if (!host_.connect(it->second, source_id, reply, error,
                     spec_.connect_timeout)) {
    return false;
  }
  if (!reply.error().code().empty()) {
    error = reply.error().message().empty() ? reply.error().code()
                                            : reply.error().message();
    return false;
  }
  connected_[source_id] = true;
  auto& h = health_[source_id];
  h.data_arriving = false;
  const auto caps = reply.source().metadata().find("negotiated_caps");
  if (caps != reply.source().metadata().end()) {
    h.current_segment = caps->second;
  }
  return true;
}

bool ExternalWorkerBridge::start_capture(const std::string& source_id,
                                         const capture::v1::StartRequest& req,
                                         std::string& error) {
  if (!connect_source(source_id, error)) {
    return false;
  }
  std::lock_guard lock(mu_);
  auto it = workers_.find(source_id);
  if (it == workers_.end()) {
    error = "no " + spec_.family + " worker for " + source_id;
    return false;
  }
  capture::v1::StartReply reply;
  if (!host_.start_capture(it->second, req, reply, error, spec_.start_timeout)) {
    return false;
  }
  if (!reply.error().code().empty()) {
    error = reply.error().message().empty() ? reply.error().code()
                                            : reply.error().message();
    return false;
  }
  health_[source_id].write_ok = true;
  health_[source_id].process_alive = true;
  return true;
}

bool ExternalWorkerBridge::stop_capture(const std::string& source_id,
                                        std::string& error) {
  SpawnedWorker* worker = nullptr;
  {
    std::lock_guard lock(mu_);
    auto it = workers_.find(source_id);
    if (it == workers_.end()) {
      return true;
    }
    worker = &it->second;
  }
  capture::v1::StopReply reply;
  if (!host_.stop_capture(*worker, source_id, reply, error,
                          spec_.stop_timeout)) {
    return false;
  }
  if (!reply.error().code().empty()) {
    error = reply.error().message();
    return false;
  }
  return true;
}

bool ExternalWorkerBridge::get_config_schema(
    const std::string& source_id, capture::v1::GetConfigSchemaReply& reply,
    std::string& error) {
  if (!spawn_for_source(source_id, error)) {
    return false;
  }
  std::lock_guard lock(mu_);
  auto it = workers_.find(source_id);
  if (it == workers_.end()) {
    error = "no " + spec_.family + " worker for " + source_id;
    return false;
  }
  if (!host_.get_config_schema(it->second, source_id, reply, error)) {
    return false;
  }
  if (!reply.error().code().empty()) {
    error = reply.error().message().empty() ? reply.error().code()
                                            : reply.error().message();
    return false;
  }
  return true;
}

bool ExternalWorkerBridge::apply_config(const std::string& source_id,
                                        const std::string& config_json,
                                        capture::v1::ApplyConfigReply& reply,
                                        std::string& error) {
  if (!spawn_for_source(source_id, error)) {
    return false;
  }
  if (!connect_source(source_id, error)) {
    return false;
  }
  std::lock_guard lock(mu_);
  auto it = workers_.find(source_id);
  if (it == workers_.end()) {
    error = "no " + spec_.family + " worker for " + source_id;
    return false;
  }
  capture::v1::ApplyConfigRequest req;
  req.set_source_id(source_id);
  req.set_configuration(config_json);
  if (!host_.apply_config(it->second, req, reply, error)) {
    return false;
  }
  if (!reply.error().code().empty()) {
    if (reply.error().code() == "RESTART_REQUIRED") {
      error = reply.error().message().empty() ? "RESTART_REQUIRED"
                                              : reply.error().message();
    } else {
      error = reply.error().message().empty() ? reply.error().code()
                                              : reply.error().message();
    }
    return false;
  }
  return true;
}

void ExternalWorkerBridge::stop_all() {
  std::lock_guard lock(mu_);
  for (auto& [id, worker] : workers_) {
    std::string err;
    capture::v1::StopReply reply;
    if (process_alive(worker)) {
      host_.stop_capture(worker, id, reply, err);
    }
    host_.stop(worker);
  }
  workers_.clear();
  connected_.clear();
  health_.clear();
}

void ExternalWorkerBridge::force_stop_all() {
  std::lock_guard lock(mu_);
  for (auto& [id, worker] : workers_) {
    (void)id;
    host_.stop(worker);
  }
  workers_.clear();
  connected_.clear();
  health_.clear();
}

void ExternalWorkerBridge::force_stop_worker(const std::string& source_id) {
  std::lock_guard lock(mu_);
  auto it = workers_.find(source_id);
  if (it == workers_.end()) {
    return;
  }
  host_.stop(it->second);
  workers_.erase(it);
  connected_.erase(source_id);
  health_.erase(source_id);
}

int ExternalWorkerBridge::poll(
    const std::function<void(const capture::v1::SegmentSealed&)>& on_sealed,
    const std::function<void(PreviewFrameData)>& on_preview,
    const std::function<void(const capture::v1::OverloadEvent&)>& on_overload) {
  std::vector<capture::v1::SegmentSealed> sealed_events;
  std::vector<PreviewFrameData> preview_events;
  std::vector<capture::v1::OverloadEvent> overload_events;
  int total = 0;
  {
    std::lock_guard lock(mu_);
    for (auto& [id, worker] : workers_) {
      auto& h = health_[id];
      h.process_alive = process_alive(worker);
      if (!h.process_alive && h.last_error_code.empty()) {
        h.last_error_code = "WORKER_EXITED";
        h.last_error_message = spec_.family + " worker process exited";
        h.write_ok = false;
        h.data_arriving = false;
      }
      total += host_.drain_events(
          worker,
          [&](const capture::v1::SegmentSealed& sealed) {
            sealed_events.push_back(sealed);
          },
          [&](const capture::v1::PreviewFrame& f) {
            preview_events.push_back(external_preview_from_proto(f));
          },
          [&](const capture::v1::HealthSnapshot& hs) {
            h.measured_rate_hz = hs.measured_rate_hz();
            h.dropped_count = hs.dropped_count();
            h.dropped_last_10s = hs.dropped_last_10s();
            h.recorded_sample_count = hs.recorded_sample_count();
            h.data_arriving = hs.data_arriving();
            h.write_ok = hs.write_ok();
            h.current_segment = hs.current_segment();
            if (!hs.last_error().code().empty()) {
              h.last_error_code = hs.last_error().code();
              h.last_error_message = hs.last_error().message();
            }
          },
          [&](const capture::v1::OverloadEvent& ov) {
            h.dropped_count = ov.dropped_count();
            h.write_ok = false;
            h.last_error_code = spec_.overload_code;
            h.last_error_message = spec_.overload_message;
            overload_events.push_back(ov);
          });
    }
  }

  if (on_sealed) {
    for (const auto& sealed : sealed_events) {
      on_sealed(sealed);
    }
  }
  if (on_preview) {
    for (auto& frame : preview_events) {
      on_preview(std::move(frame));
    }
  }
  if (on_overload) {
    for (const auto& ov : overload_events) {
      on_overload(ov);
    }
  }
  return total;
}

bool ExternalWorkerBridge::has_worker(const std::string& source_id) const {
  std::lock_guard lock(mu_);
  return workers_.count(source_id) > 0;
}

ExternalWorkerHealth ExternalWorkerBridge::health(
    const std::string& source_id) const {
  std::lock_guard lock(mu_);
  auto it = health_.find(source_id);
  if (it == health_.end()) {
    return {};
  }
  return it->second;
}

bool ExternalWorkerBridge::worker_died(const std::string& source_id) const {
  std::lock_guard lock(mu_);
  auto it = workers_.find(source_id);
  if (it == workers_.end()) {
    return false;
  }
  auto hit = health_.find(source_id);
  if (hit != health_.end() && !hit->second.process_alive) {
    return true;
  }
  return !process_alive(it->second);
}

}  // namespace capture::daemon
