// SPDX-License-Identifier: GPL-3.0-only
#include <catch2/catch_test_macros.hpp>

#include "capture_daemon/sim_engine.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <thread>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <objbase.h>
#endif

TEST_CASE("session package persists multi-stream recording", "[storage]") {
#ifdef _WIN32
  CoInitializeEx(nullptr, COINIT_MULTITHREADED);
#endif
  const auto root =
      std::filesystem::temp_directory_path() / "capturesuite_m3_pkg_test";
  std::filesystem::remove_all(root);
  std::filesystem::create_directories(root);

  capture::daemon::SimEngine engine;
  engine.set_package_parent(root);
  engine.set_rotate_bytes(256 * 1024);  // rotate sooner for tests
  std::string err;
  REQUIRE(engine.create_session("m3-roundtrip", err));
  REQUIRE_FALSE(engine.package_path().empty());
  REQUIRE(std::filesystem::exists(engine.package_path() + "/manifest.json"));
  REQUIRE(std::filesystem::exists(engine.package_path() + "/journal.sqlite"));

  // Prefer deterministic sim streams; video id varies with real cameras.
  REQUIRE(engine.select_sources({"sim.emg.main", "sim.imu.upper", "sim.radar.1"},
                                err));
  REQUIRE(engine.start_selected(err));
  std::this_thread::sleep_for(std::chrono::milliseconds(400));
  engine.create_checkpoint("A", "test");
  const auto token = engine.request_stop_token();
  REQUIRE(engine.stop(token, err));

  const auto pkg = std::filesystem::path(engine.package_path());
  REQUIRE(std::filesystem::exists(pkg / "manifest.json"));
  REQUIRE(std::filesystem::exists(pkg / "integrity.json"));
  REQUIRE(std::filesystem::exists(pkg / "events" / "checkpoints.json"));

  std::ifstream mf(pkg / "manifest.json");
  std::string manifest((std::istreambuf_iterator<char>(mf)), {});
  REQUIRE(manifest.find("finalized") != std::string::npos);

  bool any_mcap = false;
  for (auto& p : std::filesystem::recursive_directory_iterator(pkg / "sources")) {
    if (p.path().extension() == ".mcap") {
      any_mcap = true;
      REQUIRE(std::filesystem::file_size(p.path()) > 0);
    }
  }
  REQUIRE(any_mcap);
  REQUIRE(engine.recording_stats().total_samples > 0);
#ifdef _WIN32
  CoUninitialize();
#endif
}

TEST_CASE("sim imu/emg mcap messages decode as schema protos", "[storage][imu][emg]") {
#ifdef _WIN32
  CoInitializeEx(nullptr, COINIT_MULTITHREADED);
#endif
  const auto root =
      std::filesystem::temp_directory_path() / "capturesuite_imu_emg_pkg_test";
  std::filesystem::remove_all(root);
  std::filesystem::create_directories(root);

  capture::daemon::SimEngine engine;
  engine.set_package_parent(root);
  std::string err;
  REQUIRE(engine.create_session("imu-emg-schema", err));
  REQUIRE(engine.select_sources({"sim.emg.main", "sim.imu.upper"}, err));
  REQUIRE(engine.start_selected(err));
  std::this_thread::sleep_for(std::chrono::milliseconds(500));
  const auto token = engine.request_stop_token();
  REQUIRE(engine.stop(token, err));

  const auto pkg = std::filesystem::path(engine.package_path());
  auto find_mcap = [&](const char* source_id) -> std::filesystem::path {
    const auto base = pkg / "sources" / source_id;
    for (auto& p : std::filesystem::recursive_directory_iterator(base)) {
      if (p.path().extension() == ".mcap") {
        return p.path();
      }
    }
    return {};
  };
  const auto imu_mcap = find_mcap("sim.imu.upper");
  const auto emg_mcap = find_mcap("sim.emg.main");
  REQUIRE_FALSE(imu_mcap.empty());
  REQUIRE_FALSE(emg_mcap.empty());
  REQUIRE(std::filesystem::file_size(imu_mcap) > 200);
  REQUIRE(std::filesystem::file_size(emg_mcap) > 200);

  // Lightweight magic/size check here; full protobuf decode is covered by
  // tools/probe_sim_imu_emg_record.py against a live daemon.
  std::ifstream imu(imu_mcap, std::ios::binary);
  char magic[8]{};
  imu.read(magic, 8);
  REQUIRE(std::string(magic, 8) == std::string("\x89MCAP0\r\n", 8));
#ifdef _WIN32
  CoUninitialize();
#endif
}
