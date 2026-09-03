// SPDX-License-Identifier: GPL-3.0-only
#include <catch2/catch_test_macros.hpp>

#include "capture/storage/recovery.hpp"
#include "capture_daemon/sim_engine.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <thread>

TEST_CASE("recovery repairs truncated mcap tail", "[storage][recovery]") {
  const auto root =
      std::filesystem::temp_directory_path() / "capturesuite_m3_recovery_test";
  std::filesystem::remove_all(root);
  std::filesystem::create_directories(root);

  capture::daemon::SimEngine engine;
  engine.set_package_parent(root);
  engine.set_rotate_bytes(8 * 1024);
  std::string err;
  REQUIRE(engine.create_session("m3-recovery", err));
  REQUIRE(engine.select_sources({"sim.emg.main", "sim.imu.upper"}, err));
  REQUIRE(engine.start_selected(err));
  std::this_thread::sleep_for(std::chrono::milliseconds(500));
  // Leave package unfinalized: kill recording thread without finalize.
  // Use stop normally first to get sealed data, then corrupt a copy...
  // Instead: stop cleanly, then re-mark manifest recording and truncate tail.
  const auto token = engine.request_stop_token();
  REQUIRE(engine.stop(token, err));
  const auto pkg = std::filesystem::path(engine.package_path());

  std::filesystem::path victim;
  for (auto& p : std::filesystem::recursive_directory_iterator(pkg / "sources")) {
    if (p.path().extension() == ".mcap") {
      victim = p.path();
      break;
    }
  }
  REQUIRE_FALSE(victim.empty());
  const auto original_size = std::filesystem::file_size(victim);
  REQUIRE(original_size > 32);

  // Truncate last 16 bytes to simulate crash before footer.
  {
    std::fstream f(victim, std::ios::binary | std::ios::in | std::ios::out);
    f.seekp(static_cast<std::streamoff>(original_size - 16));
    // shrink via reopen truncate pattern
  }
  {
    std::ifstream in(victim, std::ios::binary);
    std::string data((std::istreambuf_iterator<char>(in)), {});
    data.resize(data.size() - 16);
    std::ofstream out(victim, std::ios::binary | std::ios::trunc);
    out.write(data.data(), static_cast<std::streamsize>(data.size()));
  }

  // Mark unfinalized (only the state field).
  {
    std::ifstream in(pkg / "manifest.json");
    std::string text((std::istreambuf_iterator<char>(in)), {});
    const auto key = std::string("\"state\": \"finalized\"");
    auto pos = text.find(key);
    REQUIRE(pos != std::string::npos);
    text.replace(pos, key.size(), "\"state\": \"recording\"");
    std::ofstream out(pkg / "manifest.json", std::ios::trunc);
    out << text;
  }

  auto result = capture::storage::recover_session(pkg);
  REQUIRE(result.ok);
  REQUIRE(result.recovered);
  REQUIRE(result.state == "finalized_recovered");

  std::ifstream mf(pkg / "manifest.json");
  std::string manifest((std::istreambuf_iterator<char>(mf)), {});
  REQUIRE(manifest.find("finalized_recovered") != std::string::npos);
  REQUIRE(std::filesystem::file_size(victim) <= original_size);
}
