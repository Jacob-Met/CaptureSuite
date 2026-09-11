# SPDX-License-Identifier: GPL-3.0-only
find_package(Catch2 CONFIG REQUIRED)

add_executable(capture_core_tests
  test_clock.cpp
  test_env.cpp
  test_framing.cpp
  test_session_fsm.cpp
  test_source_fsm.cpp
  test_sim_engine.cpp
  test_session_package.cpp
  test_recovery.cpp
  test_logging.cpp
  test_worker_host.cpp
  ${CMAKE_SOURCE_DIR}/daemon/src/sim_engine.cpp
  ${CMAKE_SOURCE_DIR}/daemon/src/camera_capture.cpp
  ${CMAKE_SOURCE_DIR}/daemon/src/external_worker_bridge.cpp
  ${CMAKE_SOURCE_DIR}/daemon/src/camera_worker_bridge.cpp
  ${CMAKE_SOURCE_DIR}/daemon/src/radar_worker_bridge.cpp
  ${CMAKE_SOURCE_DIR}/daemon/src/plugin_registry.cpp
  ${CMAKE_SOURCE_DIR}/daemon/src/handshake.cpp
  ${CMAKE_SOURCE_DIR}/daemon/src/process_security.cpp
  ${CMAKE_SOURCE_DIR}/daemon/src/worker_host.cpp
)
target_include_directories(capture_core_tests PRIVATE
  ${CMAKE_SOURCE_DIR}/daemon/include
)
target_link_libraries(capture_core_tests PRIVATE
  capture_core
  capture_proto
  capture_storage
  Catch2::Catch2WithMain
)
if(WIN32)
  target_link_libraries(capture_core_tests PRIVATE
    ole32 mfplat mf mfreadwrite mfuuid Advapi32
  )
endif()
capture_set_warnings(capture_core_tests)

if(TARGET capture_worker_stub)
  add_dependencies(capture_core_tests capture_worker_stub)
  # Raw string so Windows backslashes in the build path stay literal.
  target_compile_definitions(capture_core_tests PRIVATE
    "CAPTURE_BINARY_DIR=R\"(${CMAKE_BINARY_DIR})\""
  )
endif()

if(TARGET capture_worker_camera)
  add_dependencies(capture_core_tests capture_worker_camera)
  target_compile_definitions(capture_core_tests PRIVATE
    CAPTURE_HAS_CAMERA_WORKER=1
  )
endif()

include(CTest)
include(Catch)
catch_discover_tests(capture_core_tests)

# POSIX/macOS worker-host portability can be qualified independently of the
# Windows-only daemon/control/camera sources. This target intentionally covers
# only the E-lane substrate: process ownership, Unix worker channel, Hello and
# Identify against the generic stub worker.
if(NOT WIN32 AND TARGET capture_worker_stub)
  add_executable(capture_worker_host_posix_tests
    test_worker_host_posix.cpp
    ${CMAKE_SOURCE_DIR}/daemon/src/handshake.cpp
    ${CMAKE_SOURCE_DIR}/daemon/src/process_security.cpp
    ${CMAKE_SOURCE_DIR}/daemon/src/worker_host_posix.cpp
  )
  target_include_directories(capture_worker_host_posix_tests PRIVATE
    ${CMAKE_SOURCE_DIR}/daemon/include
  )
  target_link_libraries(capture_worker_host_posix_tests PRIVATE
    capture_core
    capture_proto
    Catch2::Catch2WithMain
  )
  add_dependencies(capture_worker_host_posix_tests capture_worker_stub)
  target_compile_definitions(capture_worker_host_posix_tests PRIVATE
    "CAPTURE_BINARY_DIR=R\"(${CMAKE_BINARY_DIR})\""
  )
  capture_set_warnings(capture_worker_host_posix_tests)
  catch_discover_tests(capture_worker_host_posix_tests)
endif()
