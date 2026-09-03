// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <filesystem>
#include <string>

namespace capture::storage {

struct RecoveryResult {
  bool ok = false;
  bool recovered = false;  // true if repair ran
  std::string state;       // finalized | finalized_recovered | failed
  std::string report_path;
  std::string error;
};

// Intent-first recovery for unfinalized packages. Never deletes files.
RecoveryResult recover_session(const std::filesystem::path& package_root);

}  // namespace capture::storage
