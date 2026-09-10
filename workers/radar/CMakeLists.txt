# SPDX-License-Identifier: GPL-3.0-only
# Out-of-process Infineon FMCW radar worker (RADAR_PIPELINE.md / WORKER_HOST.md).
# Gated by CAPTURE_ENABLE_RADAR_WORKER at the top level.

list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")
find_package(InfineonRadar REQUIRED)

add_executable(capture_worker_radar
  src/main.cpp
  src/ifx_device.cpp
  src/worker_session.cpp
  src/capture_pipeline.cpp
)
target_include_directories(capture_worker_radar PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(capture_worker_radar PRIVATE
  capture_core
  capture_proto
  capture_storage
  InfineonRadar::Fmcw
  InfineonRadar::Ltr11
)
capture_set_warnings(capture_worker_radar)

set_target_properties(capture_worker_radar PROPERTIES
  VS_DEBUGGER_ENVIRONMENT "PATH=${InfineonRadar_RUNTIME_DIR};%PATH%"
)

if(TARGET capture_daemon)
  add_custom_command(TARGET capture_worker_radar POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory
            "$<TARGET_FILE_DIR:capture_daemon>/workers/radar"
    COMMAND ${CMAKE_COMMAND} -E make_directory
            "$<TARGET_FILE_DIR:capture_daemon>/plugins/radar_infineon"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "$<TARGET_FILE:capture_worker_radar>"
            "$<TARGET_FILE_DIR:capture_daemon>/workers/radar/"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "$<TARGET_FILE:capture_worker_radar>"
            "$<TARGET_FILE_DIR:capture_daemon>/plugins/radar_infineon/"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_SOURCE_DIR}/plugins/radar_infineon/plugin.json"
            "$<TARGET_FILE_DIR:capture_daemon>/plugins/radar_infineon/plugin.json"
    COMMENT "Copy capture_worker_radar next to capture_daemon"
  )
  file(GLOB _IFX_RUNTIME_DLLS "${InfineonRadar_RUNTIME_DIR}/*.dll")
  foreach(_dll IN LISTS _IFX_RUNTIME_DLLS)
    add_custom_command(TARGET capture_worker_radar POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E copy_if_different
              "${_dll}"
              "$<TARGET_FILE_DIR:capture_daemon>/workers/radar/"
      COMMAND ${CMAKE_COMMAND} -E copy_if_different
              "${_dll}"
              "$<TARGET_FILE_DIR:capture_daemon>/plugins/radar_infineon/"
      COMMENT "Copy Infineon runtime DLL into both radar package locations"
    )
  endforeach()
  foreach(_dep abseil_dll blake3 libprotobuf lz4 zstd)
    add_custom_command(TARGET capture_worker_radar POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E copy_if_different
              "$<TARGET_FILE_DIR:capture_worker_radar>/${_dep}.dll"
              "$<TARGET_FILE_DIR:capture_daemon>/workers/radar/"
      COMMAND ${CMAKE_COMMAND} -E copy_if_different
              "$<TARGET_FILE_DIR:capture_worker_radar>/${_dep}.dll"
              "$<TARGET_FILE_DIR:capture_daemon>/plugins/radar_infineon/"
      COMMENT "Copy ${_dep}.dll into both radar package locations"
    )
  endforeach()
endif()
