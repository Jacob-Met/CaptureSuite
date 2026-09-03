// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include "capture_daemon/external_worker_bridge.hpp"

#include <filesystem>
#include <string>
#include <unordered_map>
#include <vector>

namespace capture::daemon {

struct RegisteredPlugin {
  ExternalWorkerPluginSpec spec;
  std::filesystem::path manifest_path;
  std::filesystem::path plugin_dir;
  std::string display_name;
  std::string plugin_version = "0.1.0";
  std::string isolation = "per_source";  // per_source | shared | in_process
  bool hardware = true;
  bool enable_by_default = true;
  std::string license;
  std::string homepage;
  std::vector<std::string> requires_env;
  std::vector<std::string> path_prepend;
  std::unordered_map<std::string, std::string> runtime_env;
  std::unordered_map<std::string, std::string> capabilities;
  // Computed at scan time.
  bool enabled = false;
  std::string disabled_reason;
};

// Scans plugin.json trees and merges built-in camera/radar/sim fallbacks.
class PluginRegistry {
 public:
  static PluginRegistry& instance();

  void rescan();
  const std::vector<RegisteredPlugin>& plugins() const { return plugins_; }

  const RegisteredPlugin* find(const std::string& plugin_id) const;
  ExternalWorkerPluginSpec spec_for(const std::string& plugin_id) const;

 private:
  PluginRegistry() = default;
  void load_directory(const std::filesystem::path& dir);
  void load_manifest_file(const std::filesystem::path& path);
  void ensure_builtins();
  void evaluate_enablement(RegisteredPlugin& plugin) const;

  std::vector<RegisteredPlugin> plugins_;
  bool scanned_ = false;
};

}  // namespace capture::daemon
