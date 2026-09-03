# SPDX-License-Identifier: GPL-3.0-only
# Find official GStreamer MSVC install (BUILD_TOOLCHAIN.md).
# Not a vcpkg port — resolve via GSTREAMER_1_0_ROOT_MSVC_X86_64.

set(_gst_root_candidates "")
if(DEFINED ENV{GSTREAMER_1_0_ROOT_MSVC_X86_64}
   AND NOT "$ENV{GSTREAMER_1_0_ROOT_MSVC_X86_64}" STREQUAL "")
  list(APPEND _gst_root_candidates "$ENV{GSTREAMER_1_0_ROOT_MSVC_X86_64}")
endif()
if(GSTREAMER_1_0_ROOT_MSVC_X86_64)
  list(APPEND _gst_root_candidates "${GSTREAMER_1_0_ROOT_MSVC_X86_64}")
endif()
# Local msiexec /a extract used when a system install is unavailable.
list(APPEND _gst_root_candidates
  "${CMAKE_SOURCE_DIR}/third_party/gstreamer/gstreamer/1.0/msvc_x86_64"
  "C:/Program Files/gstreamer/1.0/msvc_x86_64"
)

set(GStreamer_ROOT "")
foreach(_cand IN LISTS _gst_root_candidates)
  if(EXISTS "${_cand}/include/gstreamer-1.0/gst/gst.h"
     AND EXISTS "${_cand}/lib/gstreamer-1.0.lib")
    set(GStreamer_ROOT "${_cand}")
    break()
  endif()
endforeach()

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(GStreamer
  REQUIRED_VARS GStreamer_ROOT
  FAIL_MESSAGE
    "GStreamer MSVC root not found. Set GSTREAMER_1_0_ROOT_MSVC_X86_64 or extract the official installers under third_party/gstreamer/."
)

if(GStreamer_FOUND)
  set(GStreamer_INCLUDE_DIRS
    "${GStreamer_ROOT}/include/gstreamer-1.0"
    "${GStreamer_ROOT}/include/glib-2.0"
    "${GStreamer_ROOT}/lib/glib-2.0/include"
  )
  # Some layouts also ship orc / json-glib headers under include/.
  if(EXISTS "${GStreamer_ROOT}/include")
    list(APPEND GStreamer_INCLUDE_DIRS "${GStreamer_ROOT}/include")
  endif()

  set(GStreamer_LIBRARY_DIRS "${GStreamer_ROOT}/lib")
  set(GStreamer_RUNTIME_DIR "${GStreamer_ROOT}/bin")

  set(_gst_libs
    gstreamer-1.0
    gstapp-1.0
    gstbase-1.0
    gstvideo-1.0
    gobject-2.0
    glib-2.0
    intl
    ffi
  )
  set(GStreamer_LIBRARIES "")
  foreach(_lib IN LISTS _gst_libs)
    if(EXISTS "${GStreamer_ROOT}/lib/${_lib}.lib")
      list(APPEND GStreamer_LIBRARIES "${GStreamer_ROOT}/lib/${_lib}.lib")
    endif()
  endforeach()

  if(NOT TARGET GStreamer::GStreamer)
    add_library(GStreamer::GStreamer INTERFACE IMPORTED)
    set_target_properties(GStreamer::GStreamer PROPERTIES
      INTERFACE_INCLUDE_DIRECTORIES "${GStreamer_INCLUDE_DIRS}"
      INTERFACE_LINK_LIBRARIES "${GStreamer_LIBRARIES}"
      INTERFACE_LINK_DIRECTORIES "${GStreamer_LIBRARY_DIRS}"
    )
  endif()

  message(STATUS "GStreamer root: ${GStreamer_ROOT}")
endif()
