// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/plugin_registry.hpp"

#include "capture/logging.hpp"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cstdlib>
#include <fstream>

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

std::string expand_env(std::string s) {
  // Minimal ${VAR} expansion for path_prepend entries.
  for (;;) {
    const auto start = s.find("${");
    if (start == std::string::npos) {
      break;
    }
    const auto end = s.find('}', start);
    if (end == std::string::npos) {
      break;
    }
    const std::string key = s.substr(start + 2, end - start - 2);
    const std::string val = env_dup(key.c_str());
    s.replace(start, end - start + 1, val);
  }
  return s;
}

RegisteredPlugin builtin_sim() {
  RegisteredPlugin p;
  p.spec.plugin_id = "sim.builtin";
  p.spec.family = "sim";
  p.display_name = "Built-in Simulator";
  p.plugin_version = "0.1.0";
  p.isolation = "in_process";
  p.hardware = false;
  p.enable_by_default = true;
  p.license = "GPL-3.0-only";
  p.capabilities["families"] = "sim";
  p.capabilities["hardware"] = "0";
  p.enabled = true;
  return p;
}

}  // namespace

PluginRegistry& PluginRegistry::instance() {
  static PluginRegistry reg;
  if (!reg.scanned_) {
    reg.rescan();
  }
  return reg;
}

void PluginRegistry::rescan() {
  plugins_.clear();
  const auto dir = exe_dir();
  load_directory(dir / "plugins");
  load_directory(dir / ".." / "plugins");
  load_directory(dir / ".." / ".." / "plugins");

  const std::string local = env_dup("LOCALAPPDATA");
  if (!local.empty()) {
    load_directory(std::filesystem::path(local) / "CaptureSuite" / "plugins");
  }

  const std::string extra = env_dup("CAPTURE_PLUGIN_PATH");
  if (!extra.empty()) {
    size_t start = 0;
    while (start <= extra.size()) {
      const size_t semi = extra.find(';', start);
      const auto piece = extra.substr(
          start, semi == std::string::npos ? std::string::npos : semi - start);
      if (!piece.empty()) {
        load_directory(piece);
      }
      if (semi == std::string::npos) {
        break;
      }
      start = semi + 1;
    }
  }

  ensure_builtins();
  for (auto& p : plugins_) {
    evaluate_enablement(p);
  }
  scanned_ = true;
  capture::log::info("plugin_registry", "plugins scanned",
                     {{"count", std::to_string(plugins_.size())}});
}

void PluginRegistry::load_directory(const std::filesystem::path& dir) {
  std::error_code ec;
  if (!std::filesystem::is_directory(dir, ec)) {
    return;
  }
  for (const auto& entry : std::filesystem::directory_iterator(dir, ec)) {
    if (ec) {
      break;
    }
    if (!entry.is_directory()) {
      continue;
    }
    const auto manifest = entry.path() / "plugin.json";
    if (std::filesystem::exists(manifest)) {
      load_manifest_file(manifest);
    }
  }
}

void PluginRegistry::load_manifest_file(const std::filesystem::path& path) {
  std::ifstream in(path);
  if (!in) {
    return;
  }
  nlohmann::json j;
  try {
    in >> j;
  } catch (const std::exception& ex) {
    capture::log::warn("plugin_registry",
                       std::string("invalid plugin.json: ") + ex.what(),
                       {{"path", path.string()}});
    return;
  }

  RegisteredPlugin p;
  p.manifest_path = path;
  p.plugin_dir = path.parent_path();
  p.spec.plugin_id = j.value("plugin_id", "");
  if (p.spec.plugin_id.empty()) {
    return;
  }
  // Last write wins for duplicate ids.
  plugins_.erase(std::remove_if(plugins_.begin(), plugins_.end(),
                                [&](const RegisteredPlugin& x) {
                                  return x.spec.plugin_id == p.spec.plugin_id;
                                }),
                 plugins_.end());

  p.plugin_version = j.value("plugin_version", "0.1.0");
  p.spec.family = j.value("family", "unknown");
  p.display_name = j.value("display_name", p.spec.plugin_id);
  p.spec.exe_name = j.value("executable", "");
  p.isolation = j.value("isolation", "per_source");
  p.enable_by_default = j.value("enable_by_default", true);
  p.spec.enable_env = j.value("enable_env", "");
  p.spec.exe_env = j.value("exe_env", "");
  p.hardware = j.value("hardware", true);
  p.license = j.value("license", "");
  p.homepage = j.value("homepage", "");
  p.spec.workers_subdir = p.plugin_dir.filename().string();

  if (j.contains("requires") && j["requires"].is_object()) {
    const auto& req = j["requires"];
    p.spec.require_gstreamer = req.value("gstreamer", false);
    if (req.contains("env") && req["env"].is_array()) {
      for (const auto& e : req["env"]) {
        if (e.is_string()) {
          p.requires_env.push_back(e.get<std::string>());
        }
      }
    }
  }
  if (j.contains("runtime") && j["runtime"].is_object()) {
    const auto& rt = j["runtime"];
    if (rt.contains("path_prepend") && rt["path_prepend"].is_array()) {
      for (const auto& pe : rt["path_prepend"]) {
        if (pe.is_string()) {
          p.path_prepend.push_back(expand_env(pe.get<std::string>()));
        }
      }
    }
    if (rt.contains("env") && rt["env"].is_object()) {
      for (auto it = rt["env"].begin(); it != rt["env"].end(); ++it) {
        if (it.value().is_string()) {
          p.runtime_env[it.key()] = it.value().get<std::string>();
        }
      }
    }
  }
  if (j.contains("capabilities") && j["capabilities"].is_object()) {
    for (auto it = j["capabilities"].begin(); it != j["capabilities"].end();
         ++it) {
      if (it.value().is_string()) {
        p.capabilities[it.key()] = it.value().get<std::string>();
      }
    }
  }
  if (j.contains("timeouts_ms") && j["timeouts_ms"].is_object()) {
    const auto& t = j["timeouts_ms"];
    if (t.contains("spawn")) {
      p.spec.spawn_timeout = std::chrono::milliseconds(t["spawn"].get<int>());
    }
    if (t.contains("connect")) {
      p.spec.connect_timeout =
          std::chrono::milliseconds(t["connect"].get<int>());
    }
    if (t.contains("start")) {
      p.spec.start_timeout = std::chrono::milliseconds(t["start"].get<int>());
    }
    if (t.contains("stop")) {
      p.spec.stop_timeout = std::chrono::milliseconds(t["stop"].get<int>());
    }
    if (t.contains("enumerate")) {
      p.spec.enumerate_timeout =
          std::chrono::milliseconds(t["enumerate"].get<int>());
    }
  }

  // Prefer executable next to the manifest.
  if (!p.spec.exe_name.empty()) {
    const auto local_exe = p.plugin_dir / p.spec.exe_name;
    if (std::filesystem::exists(local_exe)) {
      p.spec.exe_env.clear();  // path resolved via workers_subdir + exe_name
    }
  }

  plugins_.push_back(std::move(p));
}

void PluginRegistry::ensure_builtins() {
  auto has = [&](const std::string& id) {
    return std::any_of(plugins_.begin(), plugins_.end(),
                       [&](const RegisteredPlugin& p) {
                         return p.spec.plugin_id == id;
                       });
  };
  if (!has("sim.builtin")) {
    plugins_.insert(plugins_.begin(), builtin_sim());
  }
  if (!has("camera.gstreamer")) {
    RegisteredPlugin p;
    p.spec = camera_worker_plugin_spec_builtin();
    p.display_name = "Camera (GStreamer)";
    p.plugin_version = "0.1.0";
    p.isolation = "per_source";
    p.hardware = true;
    p.enable_by_default = true;
    p.capabilities["families"] = "camera";
    p.capabilities["hardware"] = "1";
    p.requires_env.push_back("GSTREAMER_1_0_ROOT_MSVC_X86_64");
    plugins_.push_back(std::move(p));
  }
  if (!has("radar.ifx")) {
    RegisteredPlugin p;
    p.spec = radar_worker_plugin_spec_builtin();
    p.display_name = "Radar (Infineon)";
    p.plugin_version = "0.1.0";
    p.isolation = "per_source";
    p.hardware = true;
    p.enable_by_default = true;
    p.capabilities["families"] = "radar";
    p.capabilities["hardware"] = "1";
    p.capabilities["emits_arrays"] = "1";
    p.requires_env.push_back("IFX_RADAR_SDK_ROOT");
    plugins_.push_back(std::move(p));
  }
}

void PluginRegistry::evaluate_enablement(RegisteredPlugin& plugin) const {
  if (plugin.isolation == "in_process") {
    plugin.enabled = true;
    plugin.disabled_reason.clear();
    return;
  }
  if (!plugin.spec.enable_env.empty()) {
    const std::string v = env_dup(plugin.spec.enable_env.c_str());
    if (!v.empty() && v[0] == '0') {
      plugin.enabled = false;
      plugin.disabled_reason = plugin.spec.enable_env + "=0";
      return;
    }
  }
  if (!plugin.enable_by_default) {
    const std::string v = plugin.spec.enable_env.empty()
                              ? std::string{}
                              : env_dup(plugin.spec.enable_env.c_str());
    if (v.empty() || v[0] == '0') {
      plugin.enabled = false;
      plugin.disabled_reason = "enable_by_default=false";
      return;
    }
  }
  for (const auto& req : plugin.requires_env) {
    if (env_dup(req.c_str()).empty()) {
      // Soft requirement: still enable if exe resolves (dev layouts).
      break;
    }
  }
  if (ExternalWorkerBridge::resolve_worker_exe(plugin.spec).empty() &&
      plugin.isolation != "in_process") {
    // Also try plugin_dir/executable
    if (!plugin.spec.exe_name.empty() && !plugin.plugin_dir.empty()) {
      const auto candidate = plugin.plugin_dir / plugin.spec.exe_name;
      if (!std::filesystem::exists(candidate)) {
        plugin.enabled = false;
        plugin.disabled_reason = "executable not found: " + plugin.spec.exe_name;
        return;
      }
    } else {
      plugin.enabled = false;
      plugin.disabled_reason = "executable not found";
      return;
    }
  }
  if (plugin.spec.require_gstreamer &&
      !ExternalWorkerBridge::gstreamer_available()) {
    plugin.enabled = false;
    plugin.disabled_reason = "GStreamer not found";
    return;
  }
  plugin.enabled = true;
  plugin.disabled_reason.clear();
}

const RegisteredPlugin* PluginRegistry::find(
    const std::string& plugin_id) const {
  for (const auto& p : plugins_) {
    if (p.spec.plugin_id == plugin_id) {
      return &p;
    }
  }
  return nullptr;
}

ExternalWorkerPluginSpec PluginRegistry::spec_for(
    const std::string& plugin_id) const {
  if (const auto* p = find(plugin_id)) {
    return p->spec;
  }
  return {};
}

}  // namespace capture::daemon
