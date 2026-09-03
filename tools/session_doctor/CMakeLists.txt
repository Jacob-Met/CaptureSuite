# SPDX-License-Identifier: GPL-3.0-only
if(NOT TARGET capture_storage)
  return()
endif()

add_executable(session_doctor main.cpp)
target_link_libraries(session_doctor PRIVATE capture_storage)
capture_set_warnings(session_doctor)
