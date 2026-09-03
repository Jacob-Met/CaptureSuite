# SPDX-License-Identifier: GPL-3.0-only
# Out-of-process GStreamer camera worker (VIDEO_PIPELINE.md / WORKER_HOST.md).
# Gated by CAPTURE_ENABLE_CAMERA_WORKER at the top level.

find_package(GStreamer REQUIRED)

add_executable(capture_worker_camera
  src/main.cpp
  src/camera_enumerate.cpp
  src/worker_session.cpp
  src/gst_pipeline.cpp
  src/capture_mode.cpp
  src/capture_pipeline.cpp
  src/uvc_controls.cpp
)
target_include_directories(capture_worker_camera PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)
target_link_libraries(capture_worker_camera PRIVATE
  capture_core
  capture_proto
  capture_storage
  GStreamer::GStreamer
)
# appsink lives in gstapp
if(EXISTS "${GStreamer_ROOT}/lib/gstapp-1.0.lib")
  target_link_libraries(capture_worker_camera PRIVATE
    "${GStreamer_ROOT}/lib/gstapp-1.0.lib"
  )
endif()
if(EXISTS "${GStreamer_ROOT}/lib/gstvideo-1.0.lib")
  target_link_libraries(capture_worker_camera PRIVATE
    "${GStreamer_ROOT}/lib/gstvideo-1.0.lib"
  )
endif()
if(WIN32)
  target_link_libraries(capture_worker_camera PRIVATE
    ole32 mfplat mf mfreadwrite mfuuid
  )
endif()
capture_set_warnings(capture_worker_camera)

# So the worker finds plugins/DLLs next to the official layout when launched
# from the build tree. Prefer setting PATH to ${GStreamer_RUNTIME_DIR} at run.
set_target_properties(capture_worker_camera PROPERTIES
  VS_DEBUGGER_ENVIRONMENT "PATH=${GStreamer_RUNTIME_DIR};%PATH%"
)

# Place copies next to capture_daemon for auto-resolve (legacy workers/ + plugins/).
if(TARGET capture_daemon)
  add_custom_command(TARGET capture_worker_camera POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory
            "$<TARGET_FILE_DIR:capture_daemon>/workers/camera"
    COMMAND ${CMAKE_COMMAND} -E make_directory
            "$<TARGET_FILE_DIR:capture_daemon>/plugins/camera_gstreamer"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "$<TARGET_FILE:capture_worker_camera>"
            "$<TARGET_FILE_DIR:capture_daemon>/workers/camera/"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "$<TARGET_FILE:capture_worker_camera>"
            "$<TARGET_FILE_DIR:capture_daemon>/plugins/camera_gstreamer/"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_SOURCE_DIR}/plugins/camera_gstreamer/plugin.json"
            "$<TARGET_FILE_DIR:capture_daemon>/plugins/camera_gstreamer/plugin.json"
    COMMENT "Copy capture_worker_camera next to capture_daemon"
  )
  # Without these the copied exe dies with STATUS_DLL_NOT_FOUND before it can
  # Hello, and the daemon only sees "worker did not connect to pipe".
  foreach(_dep abseil_dll blake3 libprotobuf lz4 zstd)
    add_custom_command(TARGET capture_worker_camera POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E copy_if_different
              "$<TARGET_FILE_DIR:capture_worker_camera>/${_dep}.dll"
              "$<TARGET_FILE_DIR:capture_daemon>/workers/camera/"
      COMMENT "Copy ${_dep}.dll next to capture_daemon"
    )
  endforeach()
endif()
