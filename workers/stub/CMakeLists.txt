# SPDX-License-Identifier: Apache-2.0
if(NOT TARGET capture_proto)
  message(WARNING "capture_proto unavailable — skipping capture_worker_stub")
  return()
endif()

if(WIN32)
  set(CAPTURE_STUB_SOURCE main.cpp)
else()
  set(CAPTURE_STUB_SOURCE main_posix.cpp)
endif()

add_executable(capture_worker_stub
  ${CAPTURE_STUB_SOURCE}
)
target_link_libraries(capture_worker_stub PRIVATE
  capture_core
  capture_proto
)
capture_set_warnings(capture_worker_stub)
