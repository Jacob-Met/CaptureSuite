// SPDX-License-Identifier: GPL-3.0-only
#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

struct sqlite3;

namespace capture::storage {

struct JournalEvent {
  int64_t id = 0;
  int64_t session_time_ns = 0;
  std::string wall_utc;
  std::string kind;
  std::string source_id;
  std::string stream_id;
  std::string payload_json;
};

class Journal {
 public:
  Journal() = default;
  ~Journal();

  Journal(const Journal&) = delete;
  Journal& operator=(const Journal&) = delete;

  bool open(const std::filesystem::path& db_path, std::string& error);
  void close();
  bool is_open() const { return db_ != nullptr; }

  bool append(int64_t session_time_ns, std::string_view wall_utc,
              std::string_view kind, std::string_view source_id,
              std::string_view stream_id, std::string_view payload_json,
              std::string& error);

  std::vector<JournalEvent> read_all(std::string& error) const;

 private:
  sqlite3* db_ = nullptr;
};

}  // namespace capture::storage
