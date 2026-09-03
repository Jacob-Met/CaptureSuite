# SPDX-License-Identifier: GPL-3.0-only
if(NOT CAPTURE_PROTOBUF_FOUND)
  message(STATUS "Skipping capture_storage (protobuf not found)")
  return()
endif()

find_package(unofficial-mcap CONFIG REQUIRED)
find_package(unofficial-sqlite3 CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)
find_package(blake3 CONFIG REQUIRED)

add_library(capture_storage STATIC
  src/atomic_file.cpp
  src/hash.cpp
  src/journal.cpp
  src/disk_watchdog.cpp
  src/mcap_impl.cpp
  src/mcap_stream_writer.cpp
  src/session_package.cpp
  src/recovery.cpp
)
add_library(capture::storage ALIAS capture_storage)

target_include_directories(capture_storage PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(capture_storage PUBLIC
  capture_core
  capture_proto
  unofficial::mcap::mcap
  unofficial::sqlite3::sqlite3
  nlohmann_json::nlohmann_json
  BLAKE3::blake3
)
# mcap is header-only; avoid Windows dllimport/dllexport on static link.
target_compile_definitions(capture_storage PUBLIC MCAP_PUBLIC=)
capture_set_warnings(capture_storage)
if(MSVC)
  target_compile_options(capture_storage PRIVATE /wd4100 /wd4244 /wd4267)
endif()
