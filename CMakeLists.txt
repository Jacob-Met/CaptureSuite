# SPDX-License-Identifier: GPL-3.0-only
cmake_minimum_required(VERSION 3.28)
project(CaptureSuite VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(CAPTURE_WERROR "Treat warnings as errors" OFF)
option(CAPTURE_BUILD_TESTS "Build C++ tests" ON)
option(CAPTURE_ENABLE_CAMERA_WORKER
  "Build out-of-process GStreamer camera worker (Milestone 5)" OFF)
option(CAPTURE_ENABLE_RADAR_WORKER
  "Build Infineon radar worker (Milestone 6)" OFF)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(CompilerWarnings)
include(CaptureProtobuf)

add_subdirectory(libs/cpp/capture_core)
add_subdirectory(libs/cpp/capture_proto)
add_subdirectory(libs/cpp/capture_storage)
add_subdirectory(daemon)
add_subdirectory(workers/stub)
if(CAPTURE_ENABLE_CAMERA_WORKER)
  # FindGStreamer.cmake requires GSTREAMER_1_0_ROOT_MSVC_X86_64 (or the
  # third_party/gstreamer extract). Configure fails loudly if missing.
  add_subdirectory(workers/camera)
endif()
if(CAPTURE_ENABLE_RADAR_WORKER)
  add_subdirectory(workers/radar)
endif()
add_subdirectory(tools/session_doctor)

if(CAPTURE_BUILD_TESTS)
  enable_testing()
  if(CAPTURE_PROTOBUF_FOUND)
    add_subdirectory(tests/cpp)
  endif()
endif()
