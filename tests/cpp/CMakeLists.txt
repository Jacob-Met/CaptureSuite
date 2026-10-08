# SPDX-License-Identifier: GPL-3.0-only
find_package(Catch2 CONFIG REQUIRED)

set(CAPTURE_PORTABLE_TESTS
  test_clock.cpp
  test_env.cpp
  test_framing.cpp
  test_session_fsm.cpp
  test_source_fsm.cpp
  test_logging.cpp
  test_storage_posix.cpp
)
if(WIN32)
  add_executable(capture_core_tests
    ${CAPTURE_PORTABLE_TESTS}
    test_sim_engine.cpp
    test_session_package.cpp
    test_recovery.cpp
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
else()
  # Non-Windows: portable subset only (daemon-backed tests need Win32).
  add_executable(capture_core_tests ${CAPTURE_PORTABLE_TESTS})
endif()
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

if(TARGET session_doctor)
  add_test(NAME capture_session_doctor_portable
    COMMAND ${CMAKE_COMMAND}
      "-DSESSION_DOCTOR=$<TARGET_FILE:session_doctor>"
      "-DSOURCE_DIR=${CMAKE_SOURCE_DIR}"
      "-DTEST_ROOT=${CMAKE_CURRENT_BINARY_DIR}/portable-session-doctor"
      -P ${CMAKE_SOURCE_DIR}/tests/cmake/portable_storage/session_doctor.cmake)
endif()

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  # Exercise actual file I/O with write/fsync/close failures, without adding
  # test-only hooks to the production storage API.
  add_executable(capture_atomic_file_posix_tests
    test_atomic_file_posix.cpp
    ${CMAKE_SOURCE_DIR}/libs/cpp/capture_storage/src/atomic_file.cpp
  )
  target_include_directories(capture_atomic_file_posix_tests PRIVATE
    ${CMAKE_SOURCE_DIR}/libs/cpp/capture_storage/include
  )
  target_link_options(capture_atomic_file_posix_tests PRIVATE
    "-Wl,--wrap=write" "-Wl,--wrap=fsync" "-Wl,--wrap=close")
  capture_set_warnings(capture_atomic_file_posix_tests)
  add_test(NAME capture_atomic_file_posix_durability
           COMMAND capture_atomic_file_posix_tests)
  add_executable(capture_atomic_file_posix_identity_tests
    test_atomic_file_posix_identity.cpp
    ${CMAKE_SOURCE_DIR}/libs/cpp/capture_storage/src/atomic_file.cpp
  )
  target_include_directories(capture_atomic_file_posix_identity_tests PRIVATE
    ${CMAKE_SOURCE_DIR}/libs/cpp/capture_storage/include
  )
  target_link_options(capture_atomic_file_posix_identity_tests PRIVATE
    "-Wl,--wrap=openat,--wrap=write,--wrap=fsync,--wrap=close,--wrap=renameat")
  capture_set_warnings(capture_atomic_file_posix_identity_tests)
  add_test(NAME capture_atomic_file_posix_identity
           COMMAND capture_atomic_file_posix_identity_tests)
endif()
