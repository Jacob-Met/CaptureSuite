# SPDX-License-Identifier: GPL-3.0-only
cmake_minimum_required(VERSION 3.28)
project(CameraPackagingProbe LANGUAGES CXX)

# This fixture substitutes compilation dependencies, then executes the unchanged
# production camera CMakeLists.txt. It tests packaging, not GStreamer or capture.
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

function(capture_set_warnings target)
endfunction()

add_executable(capture_daemon daemon.cpp)
set_target_properties(capture_daemon PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/daemon/$<CONFIG>"
)
add_library(capture_core INTERFACE)
add_library(capture_proto INTERFACE)
add_library(capture_storage INTERFACE)

set(_value 0)
foreach(_dep abseil_dll blake3 libprotobuf lz4 zstd)
  math(EXPR _value "${_value} + 1")
  add_library(probe_${_dep} SHARED dependency.cpp)
  target_compile_definitions(probe_${_dep} PRIVATE
    PROBE_FUNCTION=probe_${_dep} PROBE_VALUE=${_value}
  )
  set_target_properties(probe_${_dep} PROPERTIES
    OUTPUT_NAME "${_dep}"
    PREFIX ""
    SUFFIX ".dll"
    WINDOWS_EXPORT_ALL_SYMBOLS ON
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/workers/camera/$<CONFIG>"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/workers/camera/$<CONFIG>"
  )
  target_link_libraries(capture_core INTERFACE probe_${_dep})
endforeach()

add_subdirectory(workers/camera)
set_target_properties(capture_worker_camera PROPERTIES
  SUFFIX ".exe"
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/workers/camera/$<CONFIG>"
  # The Linux probe must not find dependencies back in its original build tree.
  BUILD_WITH_INSTALL_RPATH TRUE
  INSTALL_RPATH "$ORIGIN"
)
