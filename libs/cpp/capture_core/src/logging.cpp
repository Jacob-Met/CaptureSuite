// SPDX-License-Identifier: GPL-3.0-only
#include "capture/logging.hpp"

#include <nlohmann/json.hpp>
#include <spdlog/sinks/rotating_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/spdlog.h>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <mutex>
#include <vector>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>
#else
#include <unistd.h>
#endif

namespace capture::log {
namespace {

std::mutex g_mu;
std::shared_ptr<spdlog::logger> g_logger;
std::string g_component = "daemon";
std::string g_session_id;
std::filesystem::path g_default_dir;
std::filesystem::path g_active_dir;
std::size_t g_max_file_bytes = 64ULL * 1024 * 1024;
std::size_t g_max_files = 5;
bool g_also_stderr = true;
uint32_t g_pid = 0;

std::filesystem::path default_log_dir() {
#ifdef _WIN32
  char* local = nullptr;
  size_t len = 0;
  if (_dupenv_s(&local, &len, "LOCALAPPDATA") == 0 && local != nullptr) {
    std::filesystem::path p =
        std::filesystem::path(local) / "CaptureSuite" / "logs";
    free(local);
    return p;
  }
#endif
  return std::filesystem::temp_directory_path() / "CaptureSuite" / "logs";
}

std::string utc_now_ms() {
  using clock = std::chrono::system_clock;
  const auto now = clock::now();
  const auto secs = clock::to_time_t(now);
  const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                      now.time_since_epoch()) %
                  1000;
  std::tm tm{};
#ifdef _WIN32
  gmtime_s(&tm, &secs);
#else
  gmtime_r(&secs, &tm);
#endif
  char buf[40];
  std::snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02d.%03lldZ",
                tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday, tm.tm_hour,
                tm.tm_min, tm.tm_sec, static_cast<long long>(ms.count()));
  return buf;
}

std::string level_name(spdlog::level::level_enum lvl) {
  switch (lvl) {
    case spdlog::level::trace:
      return "trace";
    case spdlog::level::debug:
      return "debug";
    case spdlog::level::info:
      return "info";
    case spdlog::level::warn:
      return "warn";
    case spdlog::level::err:
      return "error";
    case spdlog::level::critical:
      return "critical";
    default:
      return "info";
  }
}

void rebuild_logger_unlocked() {
  std::error_code ec;
  std::filesystem::create_directories(g_active_dir, ec);
  const auto path = g_active_dir / (g_component + ".log");

  std::vector<spdlog::sink_ptr> sinks;
  sinks.push_back(std::make_shared<spdlog::sinks::rotating_file_sink_mt>(
      path.string(), g_max_file_bytes, g_max_files));
  if (g_also_stderr) {
    auto console = std::make_shared<spdlog::sinks::stderr_color_sink_mt>();
    console->set_level(spdlog::level::warn);
    sinks.push_back(std::move(console));
  }

  auto logger =
      std::make_shared<spdlog::logger>("capture", sinks.begin(), sinks.end());
  logger->set_level(spdlog::level::trace);
  logger->set_pattern("%v");
  logger->flush_on(spdlog::level::warn);
  spdlog::set_default_logger(logger);
  g_logger = std::move(logger);
}

void emit(spdlog::level::level_enum lvl, std::string_view event,
          std::string_view msg, const Fields& fields) {
  std::shared_ptr<spdlog::logger> logger;
  std::string component;
  std::string session;
  uint32_t pid = 0;
  {
    std::lock_guard lock(g_mu);
    logger = g_logger;
    component = g_component;
    session = g_session_id;
    pid = g_pid;
  }
  if (!logger) {
    return;
  }

  nlohmann::json j;
  j["ts_utc"] = utc_now_ms();
  j["qpc_ns"] = qpc_ns_now();
  j["level"] = level_name(lvl);
  j["component"] = component;
  j["pid"] = static_cast<int64_t>(pid);
  j["event"] = event;
  j["msg"] = msg;
  if (session.empty()) {
    j["session_id"] = nullptr;
  } else {
    j["session_id"] = session;
  }
  j["source_id"] = nullptr;
  j["stream_id"] = nullptr;
  j["seq"] = nullptr;

  for (const auto& [k, v] : fields) {
    if (k == "seq") {
      try {
        j["seq"] = std::stoll(v);
      } catch (const std::exception&) {
        j["seq"] = v;
      }
    } else {
      j[k] = v;
    }
  }

  logger->log(lvl, j.dump());
}

}  // namespace

int64_t qpc_ns_now() {
#ifdef _WIN32
  static const LARGE_INTEGER freq = [] {
    LARGE_INTEGER f{};
    QueryPerformanceFrequency(&f);
    return f;
  }();
  LARGE_INTEGER now{};
  QueryPerformanceCounter(&now);
  // Process-relative monotonic ns for cross-process merge when combined with
  // wall clock; absolute QPC ticks converted against frequency.
  unsigned __int64 ticks = static_cast<unsigned __int64>(now.QuadPart);
  unsigned __int64 f = static_cast<unsigned __int64>(freq.QuadPart);
  return static_cast<int64_t>((ticks * 1000000000ull) / f);
#else
  using clock = std::chrono::steady_clock;
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
             clock::now().time_since_epoch())
      .count();
#endif
}

void init(const Options& opts) {
  std::lock_guard lock(g_mu);
  g_component = opts.component.empty() ? "daemon" : opts.component;
  g_max_file_bytes = opts.max_file_bytes;
  g_max_files = opts.max_files;
  g_also_stderr = opts.also_stderr;
  g_default_dir =
      opts.log_dir.empty() ? default_log_dir() : opts.log_dir;
  g_active_dir = g_default_dir;
#ifdef _WIN32
  g_pid = static_cast<uint32_t>(GetCurrentProcessId());
#else
  g_pid = static_cast<uint32_t>(getpid());
#endif
  rebuild_logger_unlocked();
}

void shutdown() {
  std::lock_guard lock(g_mu);
  if (g_logger) {
    g_logger->flush();
    g_logger->sinks().clear();
  }
  spdlog::drop_all();
  spdlog::shutdown();
  g_logger.reset();
}

void set_session_id(std::string session_id) {
  std::lock_guard lock(g_mu);
  g_session_id = std::move(session_id);
}

void clear_session_id() {
  std::lock_guard lock(g_mu);
  g_session_id.clear();
}

std::string session_id() {
  std::lock_guard lock(g_mu);
  return g_session_id;
}

void set_session_log_dir(const std::filesystem::path& dir) {
  std::lock_guard lock(g_mu);
  g_active_dir = dir.empty() ? g_default_dir : dir;
  if (g_logger) {
    rebuild_logger_unlocked();
  }
}

void trace(std::string_view event, std::string_view msg, const Fields& fields) {
  emit(spdlog::level::trace, event, msg, fields);
}
void debug(std::string_view event, std::string_view msg, const Fields& fields) {
  emit(spdlog::level::debug, event, msg, fields);
}
void info(std::string_view event, std::string_view msg, const Fields& fields) {
  emit(spdlog::level::info, event, msg, fields);
}
void warn(std::string_view event, std::string_view msg, const Fields& fields) {
  emit(spdlog::level::warn, event, msg, fields);
}
void error(std::string_view event, std::string_view msg, const Fields& fields) {
  emit(spdlog::level::err, event, msg, fields);
}
void critical(std::string_view event, std::string_view msg,
              const Fields& fields) {
  emit(spdlog::level::critical, event, msg, fields);
}

}  // namespace capture::log
