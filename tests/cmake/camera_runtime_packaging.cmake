# SPDX-License-Identifier: GPL-3.0-only
# Execute the camera worker's real post-build staging commands with native
# fixture executables and synthetic DLL payloads. No camera/GStreamer is loaded.
#
# cmake -DWORK_DIR=/absolute/new/scratch/path \
#   -P tests/cmake/camera_runtime_packaging.cmake
cmake_minimum_required(VERSION 3.28)

if(NOT DEFINED CAPTURE_SOURCE_DIR)
  get_filename_component(CAPTURE_SOURCE_DIR "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
endif()
if(NOT DEFINED WORK_DIR OR NOT IS_ABSOLUTE "${WORK_DIR}")
  message(FATAL_ERROR "WORK_DIR must be a new absolute scratch directory")
endif()

set(_fixture "${WORK_DIR}/fixture source")
set(_build "${WORK_DIR}/fixture build")
set(_runtime "${_build}/worker runtime")
set(_package "${_build}/daemon package")
set(_dependencies abseil_dll blake3 libprotobuf lz4 zstd)

function(assert_same source destination)
  if(NOT EXISTS "${destination}")
    message(FATAL_ERROR "Missing packaged file: ${destination}")
  endif()
  file(SHA256 "${source}" _expected)
  file(SHA256 "${destination}" _actual)
  if(NOT _expected STREQUAL _actual)
    message(FATAL_ERROR "Packaged bytes differ: ${destination}")
  endif()
endfunction()

if(VERIFY_ONLY)
  foreach(_destination workers/camera plugins/camera_gstreamer)
    assert_same("${_runtime}/capture_worker_camera.exe"
                "${_package}/${_destination}/capture_worker_camera.exe")
    foreach(_dependency IN LISTS _dependencies)
      assert_same("${_runtime}/${_dependency}.dll"
                  "${_package}/${_destination}/${_dependency}.dll")
    endforeach()
  endforeach()
  assert_same("${_fixture}/plugins/camera_gstreamer/plugin.json"
              "${_package}/plugins/camera_gstreamer/plugin.json")
  message(STATUS "Both camera executable copies retain all five runtime DLLs and exact bytes")
  return()
endif()

if(EXISTS "${WORK_DIR}")
  message(FATAL_ERROR "Refusing to overwrite existing WORK_DIR: ${WORK_DIR}")
endif()
file(MAKE_DIRECTORY "${_fixture}/plugins/camera_gstreamer" "${_runtime}")

# Test the exact production command block rather than restating its copy logic.
# Compilation/linking above this marker requires the Windows GStreamer SDK and
# is intentionally outside this portable packaging regression.
file(READ "${CAPTURE_SOURCE_DIR}/workers/camera/CMakeLists.txt" _camera_cmake)
set(_marker "# Place copies next to capture_daemon for auto-resolve (legacy workers/ + plugins/).")
string(FIND "${_camera_cmake}" "${_marker}" _staging_offset)
if(_staging_offset EQUAL -1)
  message(FATAL_ERROR "Camera staging boundary changed; update the fixture deliberately")
endif()
string(SUBSTRING "${_camera_cmake}" ${_staging_offset} -1 _staging_commands)
file(WRITE "${WORK_DIR}/production-staging.cmake" "${_staging_commands}")

file(WRITE "${_fixture}/CMakeLists.txt" [=[
cmake_minimum_required(VERSION 3.28)
project(CameraRuntimePackagingFixture LANGUAGES CXX)
add_executable(capture_daemon daemon.cpp)
add_executable(capture_worker_camera worker.cpp)
# Generator expressions keep output locations stable for single- and
# multi-config generators. Spaces exercise real command argument quoting.
set_target_properties(capture_daemon PROPERTIES
  SUFFIX ".exe"
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/daemon package/$<0:>")
set_target_properties(capture_worker_camera PROPERTIES
  SUFFIX ".exe"
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/worker runtime/$<0:>")
]=])
file(APPEND "${_fixture}/CMakeLists.txt" "\n${_staging_commands}")
file(WRITE "${_fixture}/daemon.cpp" "int main() { return 0; }\n")
file(WRITE "${_fixture}/worker.cpp" "int main() { return 0; }\n")
file(COPY "${CAPTURE_SOURCE_DIR}/plugins/camera_gstreamer/plugin.json"
     DESTINATION "${_fixture}/plugins/camera_gstreamer")
foreach(_dependency IN LISTS _dependencies)
  file(WRITE "${_runtime}/${_dependency}.dll"
       "Synthetic fixture runtime payload: ${_dependency}\n")
endforeach()

function(run_check name)
  execute_process(
    COMMAND "${CMAKE_COMMAND}" "-DWORK_DIR=${WORK_DIR}" -DVERIFY_ONLY=ON
            -P "${CMAKE_CURRENT_LIST_FILE}"
    RESULT_VARIABLE _result
    OUTPUT_FILE "${WORK_DIR}/${name}.log"
    ERROR_FILE "${WORK_DIR}/${name}.log"
  )
  if(NOT "${_result}" STREQUAL "0")
    file(READ "${WORK_DIR}/${name}.log" _failure)
    message(FATAL_ERROR "${name} failed:\n${_failure}")
  endif()
endfunction()

function(build_fixture name expect_success)
  execute_process(
    COMMAND "${CMAKE_COMMAND}" --build "${_build}" --config Release --parallel 1
    RESULT_VARIABLE _result
    OUTPUT_FILE "${WORK_DIR}/${name}.log"
    ERROR_FILE "${WORK_DIR}/${name}.log"
  )
  if(expect_success AND NOT "${_result}" STREQUAL "0")
    file(READ "${WORK_DIR}/${name}.log" _failure)
    message(FATAL_ERROR "${name} failed:\n${_failure}")
  elseif(NOT expect_success)
    if("${_result}" STREQUAL "0")
      message(FATAL_ERROR "${name} unexpectedly accepted a missing runtime input")
    endif()
    file(READ "${WORK_DIR}/${name}.log" _failure)
    if(NOT _failure MATCHES "zstd[.]dll")
      message(FATAL_ERROR "${name} failed for an unrelated reason:\n${_failure}")
    endif()
  endif()
endfunction()

execute_process(
  COMMAND "${CMAKE_COMMAND}" -S "${_fixture}" -B "${_build}" -DCMAKE_BUILD_TYPE=Release
  RESULT_VARIABLE _configured
  OUTPUT_FILE "${WORK_DIR}/configure.log"
  ERROR_FILE "${WORK_DIR}/configure.log"
)
if(NOT "${_configured}" STREQUAL "0")
  file(READ "${WORK_DIR}/configure.log" _failure)
  message(FATAL_ERROR "Fixture configure failed:\n${_failure}")
endif()
build_fixture(build TRUE)
run_check(initial-package)

# These native fixture executables prove path/openability only, not Windows
# DLL loading or camera operation; the DLLs above are deliberately plain text.
foreach(_destination workers/camera plugins/camera_gstreamer)
  execute_process(
    COMMAND "${_package}/${_destination}/capture_worker_camera.exe"
    RESULT_VARIABLE _exit
    TIMEOUT 5
  )
  if(NOT "${_exit}" STREQUAL "0")
    message(FATAL_ERROR "Cannot execute native fixture at ${_destination}: ${_exit}")
  endif()
endforeach()

# Changed input: recreate the observed plugin-only omission and require that
# the same byte verifier rejects it while the legacy copy remains intact.
file(REMOVE "${_package}/plugins/camera_gstreamer/lz4.dll")
execute_process(
  COMMAND "${CMAKE_COMMAND}" "-DWORK_DIR=${WORK_DIR}" -DVERIFY_ONLY=ON
          -P "${CMAKE_CURRENT_LIST_FILE}"
  RESULT_VARIABLE _omission
  OUTPUT_FILE "${WORK_DIR}/omission-control.log"
  ERROR_FILE "${WORK_DIR}/omission-control.log"
)
file(READ "${WORK_DIR}/omission-control.log" _omission_log)
if("${_omission}" STREQUAL "0" OR NOT _omission_log MATCHES "Missing packaged file:.*lz4[.]dll")
  message(FATAL_ERROR "Plugin-only DLL omission was not rejected:\n${_omission_log}")
endif()
assert_same("${_runtime}/lz4.dll" "${_package}/workers/camera/lz4.dll")
file(APPEND "${_fixture}/worker.cpp" "// Force a relink for the repair check.\n")
build_fixture(rebuild TRUE)
run_check(restored-package)

# A missing runtime input must make the real copy command fail the build.
file(REMOVE "${_runtime}/zstd.dll")
file(APPEND "${_fixture}/worker.cpp" "// Force a relink with missing input.\n")
build_fixture(missing-runtime-input FALSE)
file(WRITE "${_runtime}/zstd.dll" "Synthetic fixture runtime payload: zstd\n")
file(APPEND "${_fixture}/worker.cpp" "// Force a relink after restoring input.\n")
build_fixture(final-rebuild TRUE)
run_check(final-package)

message(STATUS "PASS: both layouts, exact bytes, native fixture paths, omission detection, rebuild repair, and missing-input build failure")
message(STATUS "Evidence retained in ${WORK_DIR}")
