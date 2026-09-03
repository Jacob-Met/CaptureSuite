// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <unordered_map>

namespace capture::log {

// Structured JSON Lines logger (OPERATIONS.md). One rotating file per process.

struct Options {
  std::string component = "daemon";
  std::filesystem::path log_dir;  // empty → %LOCALAPPDATA%\CaptureSuite\logs
  std::size_t max_file_bytes = 64ULL * 1024 * 1024;
  std::size_t max_files = 5;
  bool also_stderr = true;
};

void init(const Options& opts);
void shutdown();

void set_session_id(std::string session_id);
void clear_session_id();
std::string session_id();

// Redirect the rotating file into a session package's logs/ directory while a
// session is open. Pass an empty path to return to the process default directory.
void set_session_log_dir(const std::filesystem::path& dir);

using Fields = std::unordered_map<std::string, std::string>;

void trace(std::string_view event, std::string_view msg, const Fields& fields = {});
void debug(std::string_view event, std::string_view msg, const Fields& fields = {});
void info(std::string_view event, std::string_view msg, const Fields& fields = {});
void warn(std::string_view event, std::string_view msg, const Fields& fields = {});
void error(std::string_view event, std::string_view msg, const Fields& fields = {});
void critical(std::string_view event, std::string_view msg, const Fields& fields = {});

int64_t qpc_ns_now();

}  // namespace capture::log
