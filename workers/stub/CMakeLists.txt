# SPDX-License-Identifier: Apache-2.0
if(NOT TARGET capture_proto)
  message(WARNING "capture_proto unavailable — skipping capture_worker_stub")
  return()
endif()

add_executable(capture_worker_stub
  main.cpp
)
target_link_libraries(capture_worker_stub PRIVATE
  capture_core
  capture_proto
)
capture_set_warnings(capture_worker_stub)
