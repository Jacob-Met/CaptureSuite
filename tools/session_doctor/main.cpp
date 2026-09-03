// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/recovery.hpp"

#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>

int main(int argc, char** argv) {
  if (argc < 2 || std::strcmp(argv[1], "--help") == 0) {
    std::printf("Usage: session_doctor <path-to-session.mmsession>\n");
    return argc < 2 ? 1 : 0;
  }
  const std::filesystem::path root = argv[1];
  auto result = capture::storage::recover_session(root);
  if (!result.ok) {
    std::fprintf(stderr, "recovery failed: %s\n", result.error.c_str());
    return 2;
  }
  std::printf("state=%s recovered=%s report=%s\n", result.state.c_str(),
              result.recovered ? "true" : "false", result.report_path.c_str());
  return 0;
}
