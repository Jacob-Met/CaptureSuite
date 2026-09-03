# SPDX-License-Identifier: GPL-3.0-only
if(NOT CAPTURE_PROTOBUF_FOUND)
  message(STATUS "Skipping capture_proto (protobuf not found)")
  return()
endif()

find_package(protobuf CONFIG REQUIRED)

set(CAPTURE_PROTO_ROOT "${CMAKE_SOURCE_DIR}/schemas/proto")
set(CAPTURE_PROTO_GEN_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY ${CAPTURE_PROTO_GEN_DIR})

set(CAPTURE_PROTO_FILES
  ${CAPTURE_PROTO_ROOT}/capture/v1/common.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/source.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/events.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/project.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/presets.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/control.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/health.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/preview.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/worker.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/storage.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/arrays.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/data/emg_batch.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/data/imu_frame.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/data/numeric_batch.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/data/radar_frame.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/data/radar_doppler.proto
  ${CAPTURE_PROTO_ROOT}/capture/v1/data/video_timing.proto
)

find_program(CAPTURE_PROTOC_EXECUTABLE NAMES protoc
  HINTS
    "$ENV{VCPKG_ROOT}/installed/${VCPKG_TARGET_TRIPLET}/tools/protobuf"
    "${CMAKE_BINARY_DIR}/vcpkg_installed/${VCPKG_TARGET_TRIPLET}/tools/protobuf"
  REQUIRED
)

set(CAPTURE_PROTO_GEN_SRCS "")
foreach(proto ${CAPTURE_PROTO_FILES})
  file(RELATIVE_PATH rel ${CAPTURE_PROTO_ROOT} ${proto})
  get_filename_component(rel_dir ${rel} DIRECTORY)
  get_filename_component(rel_name ${rel} NAME_WE)
  set(out_dir "${CAPTURE_PROTO_GEN_DIR}/${rel_dir}")
  file(MAKE_DIRECTORY ${out_dir})
  set(out_cc "${out_dir}/${rel_name}.pb.cc")
  set(out_h "${out_dir}/${rel_name}.pb.h")
  add_custom_command(
    OUTPUT ${out_cc} ${out_h}
    COMMAND ${CAPTURE_PROTOC_EXECUTABLE}
      --proto_path=${CAPTURE_PROTO_ROOT}
      --cpp_out=${CAPTURE_PROTO_GEN_DIR}
      ${proto}
    DEPENDS ${proto}
    COMMENT "Generating C++ from ${rel}"
    VERBATIM
  )
  list(APPEND CAPTURE_PROTO_GEN_SRCS ${out_cc})
endforeach()

add_library(capture_proto STATIC ${CAPTURE_PROTO_GEN_SRCS})
add_library(capture::proto ALIAS capture_proto)
target_include_directories(capture_proto PUBLIC ${CAPTURE_PROTO_GEN_DIR})
target_link_libraries(capture_proto PUBLIC protobuf::libprotobuf)
capture_set_warnings(capture_proto)
if(MSVC)
  target_compile_options(capture_proto PRIVATE /wd4100 /wd4127 /wd4244 /wd4267 /wd4996)
endif()
