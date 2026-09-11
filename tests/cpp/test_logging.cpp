// SPDX-License-Identifier: GPL-3.0-only
#include "capture/logging.hpp"

#include <catch2/catch_test_macros.hpp>
#include <nlohmann/json.hpp>

#include <filesystem>
#include <fstream>
#include <string>

TEST_CASE("structured log emits required JSON fields", "[logging]") {
  const auto dir =
      std::filesystem::temp_directory_path() / "capturesuite_log_test";
  std::filesystem::remove_all(dir);
  std::filesystem::create_directories(dir);

  capture::log::Options opts;
  opts.component = "daemon";
  opts.log_dir = dir;
  opts.also_stderr = false;
  capture::log::init(opts);
  capture::log::set_session_id("sess-1");
  capture::log::info("unit_test", "hello",
                     {{"source_id", "sim.emg.main"}, {"stream_id", "sim.emg.main.raw"}});
  capture::log::shutdown();

  const auto path = dir / "daemon.log";
  REQUIRE(std::filesystem::exists(path));
  std::ifstream in(path);
  std::string line;
  REQUIRE(std::getline(in, line));
  auto j = nlohmann::json::parse(line);
  REQUIRE(j["event"] == "unit_test");
  REQUIRE(j["msg"] == "hello");
  REQUIRE(j["level"] == "info");
  REQUIRE(j["component"] == "daemon");
  REQUIRE(j["session_id"] == "sess-1");
  REQUIRE(j["source_id"] == "sim.emg.main");
  REQUIRE(j["stream_id"] == "sim.emg.main.raw");
  REQUIRE(j.contains("ts_utc"));
  REQUIRE(j.contains("qpc_ns"));
  REQUIRE(j.contains("pid"));
  REQUIRE(j["qpc_ns"].get<int64_t>() > 0);
  REQUIRE(j["pid"].get<int64_t>() > 0);

  std::error_code ec;
  std::filesystem::remove_all(dir, ec);
}
