// SPDX-License-Identifier: GPL-3.0-only
#include "capture/storage/journal.hpp"

#include <sqlite3.h>

#include <cstring>

namespace capture::storage {

Journal::~Journal() { close(); }

bool Journal::open(const std::filesystem::path& db_path, std::string& error) {
  close();
  if (sqlite3_open(db_path.string().c_str(), &db_) != SQLITE_OK) {
    error = db_ ? sqlite3_errmsg(db_) : "sqlite3_open failed";
    close();
    return false;
  }
  char* err = nullptr;
  const char* pragmas =
      "PRAGMA journal_mode=WAL;"
      "PRAGMA synchronous=FULL;";
  if (sqlite3_exec(db_, pragmas, nullptr, nullptr, &err) != SQLITE_OK) {
    error = err ? err : "pragma failed";
    sqlite3_free(err);
    close();
    return false;
  }
  const char* ddl =
      "CREATE TABLE IF NOT EXISTS events ("
      "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
      "  session_time_ns INTEGER NOT NULL,"
      "  wall_utc TEXT NOT NULL,"
      "  kind TEXT NOT NULL,"
      "  source_id TEXT NOT NULL DEFAULT '',"
      "  stream_id TEXT NOT NULL DEFAULT '',"
      "  payload_json TEXT NOT NULL DEFAULT '{}'"
      ");";
  if (sqlite3_exec(db_, ddl, nullptr, nullptr, &err) != SQLITE_OK) {
    error = err ? err : "create table failed";
    sqlite3_free(err);
    close();
    return false;
  }
  return true;
}

void Journal::close() {
  if (db_) {
    sqlite3_close(db_);
    db_ = nullptr;
  }
}

bool Journal::append(int64_t session_time_ns, std::string_view wall_utc,
                     std::string_view kind, std::string_view source_id,
                     std::string_view stream_id, std::string_view payload_json,
                     std::string& error) {
  if (!db_) {
    error = "journal not open";
    return false;
  }
  const char* sql =
      "INSERT INTO events(session_time_ns, wall_utc, kind, source_id, stream_id, "
      "payload_json) VALUES(?,?,?,?,?,?);";
  sqlite3_stmt* stmt = nullptr;
  if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) {
    error = sqlite3_errmsg(db_);
    return false;
  }
  sqlite3_bind_int64(stmt, 1, session_time_ns);
  sqlite3_bind_text(stmt, 2, wall_utc.data(), static_cast<int>(wall_utc.size()),
                    SQLITE_TRANSIENT);
  sqlite3_bind_text(stmt, 3, kind.data(), static_cast<int>(kind.size()),
                    SQLITE_TRANSIENT);
  sqlite3_bind_text(stmt, 4, source_id.data(), static_cast<int>(source_id.size()),
                    SQLITE_TRANSIENT);
  sqlite3_bind_text(stmt, 5, stream_id.data(), static_cast<int>(stream_id.size()),
                    SQLITE_TRANSIENT);
  sqlite3_bind_text(stmt, 6, payload_json.data(),
                    static_cast<int>(payload_json.size()), SQLITE_TRANSIENT);
  const int rc = sqlite3_step(stmt);
  sqlite3_finalize(stmt);
  if (rc != SQLITE_DONE) {
    error = sqlite3_errmsg(db_);
    return false;
  }
  return true;
}

std::vector<JournalEvent> Journal::read_all(std::string& error) const {
  std::vector<JournalEvent> out;
  if (!db_) {
    error = "journal not open";
    return out;
  }
  const char* sql =
      "SELECT id, session_time_ns, wall_utc, kind, source_id, stream_id, "
      "payload_json FROM events ORDER BY id ASC;";
  sqlite3_stmt* stmt = nullptr;
  if (sqlite3_prepare_v2(db_, sql, -1, &stmt, nullptr) != SQLITE_OK) {
    error = sqlite3_errmsg(db_);
    return out;
  }
  while (sqlite3_step(stmt) == SQLITE_ROW) {
    JournalEvent ev;
    ev.id = sqlite3_column_int64(stmt, 0);
    ev.session_time_ns = sqlite3_column_int64(stmt, 1);
    ev.wall_utc =
        reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
    ev.kind = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 3));
    ev.source_id =
        reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));
    ev.stream_id =
        reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5));
    ev.payload_json =
        reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
    out.push_back(std::move(ev));
  }
  sqlite3_finalize(stmt);
  return out;
}

}  // namespace capture::storage
