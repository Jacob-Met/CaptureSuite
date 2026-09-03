// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/recovery.hpp"

#include "capture/storage/atomic_file.hpp"
#include "capture/storage/hash.hpp"
#include "capture/storage/journal.hpp"

#include <mcap/mcap.hpp>
#include <nlohmann/json.hpp>

#define WIN32_LEAN_AND_MEAN
#include <Windows.h>

#include <fstream>
#include <iomanip>
#include <sstream>
#include <vector>

namespace capture::storage {
namespace {

using json = nlohmann::json;

std::string wall_now_utc() {
  SYSTEMTIME st{};
  GetSystemTime(&st);
  std::ostringstream oss;
  oss << std::setfill('0') << std::setw(4) << st.wYear << '-' << std::setw(2)
      << st.wMonth << '-' << std::setw(2) << st.wDay << 'T' << std::setw(2)
      << st.wHour << ':' << std::setw(2) << st.wMinute << ':' << std::setw(2)
      << st.wSecond << '.' << std::setw(3) << st.wMilliseconds << 'Z';
  return oss.str();
}

bool truncate_file(const std::filesystem::path& path, int64_t new_size,
                   std::string& error) {
  HANDLE h = CreateFileW(path.wstring().c_str(), GENERIC_WRITE, 0, nullptr,
                         OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (h == INVALID_HANDLE_VALUE) {
    error = "CreateFile for truncate failed";
    return false;
  }
  LARGE_INTEGER li{};
  li.QuadPart = new_size;
  if (!SetFilePointerEx(h, li, nullptr, FILE_BEGIN) || !SetEndOfFile(h)) {
    error = "SetEndOfFile failed";
    CloseHandle(h);
    return false;
  }
  CloseHandle(h);
  return true;
}

// Scan MCAP for last fully-parsed record end offset (crash-tolerant).
int64_t mcap_valid_end_offset(const std::filesystem::path& path,
                              std::string& error) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    error = "cannot open mcap";
    return -1;
  }
  // Magic: 0x89 MCAP0\r\n
  char magic[8];
  in.read(magic, 8);
  if (in.gcount() < 8 || magic[1] != 'M' || magic[2] != 'C' || magic[3] != 'A' ||
      magic[4] != 'P') {
    error = "bad mcap magic";
    return -1;
  }

  // Prefer library reader when summary exists; else scan opcodes.
  mcap::McapReader reader;
  auto status = reader.open(path.string());
  if (status.ok()) {
    // If readable via indexed view, file is intact enough — keep full size.
    reader.close();
    return static_cast<int64_t>(std::filesystem::file_size(path));
  }

  // Manual forward scan of records: [opcode:1][len:8][payload][crc optional]
  in.clear();
  in.seekg(8);
  int64_t last_good = 8;
  while (in) {
    const auto record_start = static_cast<int64_t>(in.tellg());
    uint8_t opcode = 0;
    uint64_t len = 0;
    in.read(reinterpret_cast<char*>(&opcode), 1);
    if (in.gcount() < 1) {
      break;
    }
    in.read(reinterpret_cast<char*>(&len), 8);
    if (in.gcount() < 8) {
      break;
    }
    // Skip payload
    in.seekg(static_cast<std::streamoff>(len), std::ios::cur);
    if (!in) {
      break;
    }
    last_good = static_cast<int64_t>(in.tellg());
    if (opcode == 0x02) {  // Footer — complete file
      break;
    }
    (void)record_start;
  }
  return last_good;
}

}  // namespace

RecoveryResult recover_session(const std::filesystem::path& package_root) {
  RecoveryResult result;
  std::string err;
  const auto manifest_path = package_root / "manifest.json";
  auto text = read_text_file(manifest_path, err);
  if (text.empty()) {
    result.error = err.empty() ? "missing manifest" : err;
    return result;
  }
  json manifest = json::parse(text, nullptr, false);
  if (manifest.is_discarded()) {
    result.error = "manifest parse failed";
    return result;
  }
  const std::string state = manifest.value("state", "");
  if (state == "finalized" || state == "finalized_recovered") {
    result.ok = true;
    result.recovered = false;
    result.state = state;
    return result;
  }

  Journal journal;
  if (!journal.open(package_root / "journal.sqlite", err)) {
    result.error = err;
    result.state = "failed";
    return result;
  }

  json report;
  report["session_id"] = manifest.value("sessionId", "");
  report["trusted"] = json::array();
  report["truncated"] = json::array();
  report["missing"] = json::array();
  report["unexpected"] = json::array();

  // Load integrity if present.
  json integrity = {{"sessionId", report["session_id"]},
                    {"sessionSchemaVersion", "1.0.0"},
                    {"files", json::array()}};
  const auto integrity_path = package_root / "integrity.json";
  if (std::filesystem::exists(integrity_path)) {
    auto itext = read_text_file(integrity_path, err);
    auto parsed = json::parse(itext, nullptr, false);
    if (!parsed.is_discarded()) {
      integrity = parsed;
    }
  }

  // Find all .mcap files under sources/
  std::vector<std::filesystem::path> mcaps;
  if (std::filesystem::exists(package_root / "sources")) {
    for (auto& p : std::filesystem::recursive_directory_iterator(
             package_root / "sources")) {
      if (p.is_regular_file() && p.path().extension() == ".mcap") {
        mcaps.push_back(p.path());
      }
    }
  }

  int64_t last_session_ns = 0;
  for (const auto& ev : journal.read_all(err)) {
    if (ev.session_time_ns > last_session_ns) {
      last_session_ns = ev.session_time_ns;
    }
  }

  for (const auto& path : mcaps) {
    const auto rel = std::filesystem::relative(path, package_root).generic_string();
    bool sealed = false;
    if (integrity.contains("files")) {
      for (const auto& f : integrity["files"]) {
        if (f.value("path", "") == rel && f.value("status", "") == "sealed") {
          sealed = true;
          report["trusted"].push_back(rel);
          break;
        }
      }
    }
    if (sealed) {
      continue;
    }

    const auto size = static_cast<int64_t>(std::filesystem::file_size(path));
    std::string scan_err;
    const int64_t valid_end = mcap_valid_end_offset(path, scan_err);
    if (valid_end < 0) {
      report["missing"].push_back(rel);
      journal.append(last_session_ns, wall_now_utc(), "RECOVERY_INTENT", "", "",
                     json({{"path", rel}, {"error", scan_err}}).dump(), err);
      continue;
    }

    const bool was_truncated = valid_end < size;
    if (was_truncated) {
      journal.append(
          last_session_ns, wall_now_utc(), "RECOVERY_INTENT", "", "",
          json({{"path", rel},
                {"current_size", size},
                {"truncate_to", valid_end}})
              .dump(),
          err);
      if (!truncate_file(path, valid_end, err)) {
        result.error = err;
        result.state = "failed";
        return result;
      }
      journal.append(last_session_ns, wall_now_utc(), "RECOVERY_COMPLETE", "",
                     "", json({{"path", rel}, {"new_size", valid_end}}).dump(),
                     err);
      report["truncated"].push_back(rel);

      const auto gaps =
          path.parent_path().parent_path().parent_path() / "health" / "gaps.jsonl";
      std::filesystem::create_directories(gaps.parent_path());
      std::ofstream gout(gaps, std::ios::app);
      if (gout) {
        gout << json({{"cause", "UNKNOWN"},
                      {"start_session_time_ns", last_session_ns},
                      {"end_session_time_ns", last_session_ns},
                      {"note", "truncated_recovered"}})
                    .dump()
             << "\n";
      }
      journal.append(last_session_ns, wall_now_utc(), "GAP_OPENED", "", "",
                     json({{"cause", "UNKNOWN"}, {"path", rel}}).dump(), err);
      journal.append(last_session_ns, wall_now_utc(), "GAP_CLOSED", "", "", "{}",
                     err);
    } else {
      report["trusted"].push_back(rel);
    }

    std::string hash_err;
    const auto hash = blake3_file_hex(path, hash_err);
    const int64_t final_size = was_truncated ? valid_end : size;
    json entry = {{"path", rel},
                  {"sizeBytes", std::to_string(final_size)},
                  {"hashBlake3Hex", hash},
                  {"status", was_truncated ? "truncated_recovered" : "sealed"},
                  {"actualCount", "0"},
                  {"expectedCount", "0"},
                  {"startSessionTimeNs", "0"},
                  {"endSessionTimeNs", std::to_string(last_session_ns)}};
    bool replaced = false;
    if (integrity.contains("files")) {
      for (auto& f : integrity["files"]) {
        if (f.value("path", "") == rel) {
          f = entry;
          replaced = true;
          break;
        }
      }
    }
    if (!replaced) {
      integrity["files"].push_back(entry);
    }
  }

  journal.append(last_session_ns, wall_now_utc(), "RECOVERY_COMPLETE", "", "",
                 json({{"scope", "package"}}).dump(), err);

  std::string safe = "report_" + wall_now_utc() + ".json";
  for (char& c : safe) {
    if (c == ':') {
      c = '-';
    }
  }
  const auto report_path = package_root / "recovery" / safe;
  std::filesystem::create_directories(package_root / "recovery");
  report["state"] = "finalized_recovered";
  if (!atomic_write_text(report_path, report.dump(2), err)) {
    result.error = err;
    result.state = "failed";
    return result;
  }
  if (!atomic_write_text(integrity_path, integrity.dump(2), err)) {
    result.error = err;
    result.state = "failed";
    return result;
  }

  manifest["state"] = "finalized_recovered";
  manifest["finalizedUtc"] = wall_now_utc();
  if (!atomic_write_text(manifest_path, manifest.dump(2), err)) {
    result.error = err;
    result.state = "failed";
    return result;
  }
  journal.append(last_session_ns, wall_now_utc(), "FINALIZED", "", "",
                 json({{"recovered", true}}).dump(), err);
  journal.close();

  result.ok = true;
  result.recovered = true;
  result.state = "finalized_recovered";
  result.report_path = report_path.string();
  return result;
}

}  // namespace capture::storage
