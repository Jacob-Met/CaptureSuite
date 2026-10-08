# SPDX-License-Identifier: GPL-3.0-only
# Linux shim for vcpkg's `unofficial-sqlite3` -> system libsqlite3.
if(NOT TARGET unofficial::sqlite3::sqlite3)
  find_package(SQLite3 REQUIRED)
  add_library(unofficial::sqlite3::sqlite3 INTERFACE IMPORTED)
  set_target_properties(unofficial::sqlite3::sqlite3 PROPERTIES
    INTERFACE_LINK_LIBRARIES SQLite::SQLite3)
endif()
set(unofficial-sqlite3_FOUND TRUE)
