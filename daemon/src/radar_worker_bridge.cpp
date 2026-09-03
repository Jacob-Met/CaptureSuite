// SPDX-License-Identifier: GPL-3.0-only
#include "capture_daemon/radar_worker_bridge.hpp"

#include <cstdlib>
#include <filesystem>

namespace capture::daemon {

std::filesystem::path RadarWorkerBridge::resolve_ifx_runtime_dir() {
  auto env_dup = [](const char* name) -> std::string {
    char* v = nullptr;
    size_t len = 0;
    if (_dupenv_s(&v, &len, name) != 0 || v == nullptr) {
      return {};
    }
    std::string out(v);
    free(v);
    return out;
  };
  for (const char* var :
       {"IFX_RADAR_SDK_ROOT", "CAPTURE_IFX_RADAR_SDK_ROOT"}) {
    const std::string root = env_dup(var);
    if (root.empty()) {
      continue;
    }
    const auto runtime = std::filesystem::path(root) / "libs" / "win32_x64";
    if (std::filesystem::exists(runtime)) {
      return runtime;
    }
  }
  if (const char* profile = std::getenv("USERPROFILE")) {
    const auto runtime =
        std::filesystem::path(profile) / "Infineon" / "Tools" /
        "radar_sdk_3.6.5" / "radar_sdk" / "libs" / "win32_x64";
    if (std::filesystem::exists(runtime)) {
      return runtime;
    }
  }
  return {};
}

}  // namespace capture::daemon
