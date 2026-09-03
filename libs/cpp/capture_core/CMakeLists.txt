# SPDX-License-Identifier: GPL-3.0-only
find_package(spdlog CONFIG REQUIRED)
find_package(nlohmann_json CONFIG REQUIRED)

add_library(capture_core STATIC
  src/version.cpp
  src/clock.cpp
  src/framing.cpp
  src/session_fsm.cpp
  src/source_fsm.cpp
  src/recording_buffer.cpp
  src/logging.cpp
)
target_include_directories(capture_core PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(capture_core PUBLIC
  spdlog::spdlog
  nlohmann_json::nlohmann_json
)
capture_set_warnings(capture_core)
