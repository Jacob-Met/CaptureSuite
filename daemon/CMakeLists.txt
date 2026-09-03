# SPDX-License-Identifier: GPL-3.0-only
if(NOT TARGET capture_proto)
  message(WARNING "capture_proto unavailable — skipping capture_daemon")
  return()
endif()

add_executable(capture_daemon
  src/main.cpp
  src/sim_engine.cpp
  src/camera_capture.cpp
  src/external_worker_bridge.cpp
  src/camera_worker_bridge.cpp
  src/radar_worker_bridge.cpp
  src/plugin_registry.cpp
  src/handshake.cpp
  src/control_server.cpp
  src/process_security.cpp
  src/worker_host.cpp
)
target_include_directories(capture_daemon PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(capture_daemon PRIVATE
  capture_core
  capture_proto
  capture_storage
)
if(WIN32)
  target_link_libraries(capture_daemon PRIVATE
    Rpcrt4 Advapi32 ole32 mfplat mf mfreadwrite mfuuid
  )
endif()
capture_set_warnings(capture_daemon)
