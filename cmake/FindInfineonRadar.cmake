# SPDX-License-Identifier: GPL-3.0-only
# Locates the Infineon Radar SDK (RDK) for CAPTURE_ENABLE_RADAR_WORKER.
#
# Expected layout (RDK 3.6.x extract):
#   <root>/sdk/c/ifxFmcw/DeviceFmcw.h
#   <root>/libs/win32_x64/sdk_fmcw.lib  (+ companion DLLs)
#
# Override with IFX_RADAR_SDK_ROOT or CAPTURE_IFX_RADAR_SDK_ROOT.

set(_IFX_HINTS "")
if(DEFINED ENV{CAPTURE_IFX_RADAR_SDK_ROOT})
  list(APPEND _IFX_HINTS "$ENV{CAPTURE_IFX_RADAR_SDK_ROOT}")
endif()
if(DEFINED ENV{IFX_RADAR_SDK_ROOT})
  list(APPEND _IFX_HINTS "$ENV{IFX_RADAR_SDK_ROOT}")
endif()
if(DEFINED ENV{USERPROFILE})
  list(APPEND _IFX_HINTS
    "$ENV{USERPROFILE}/Infineon/Tools/radar_sdk_3.6.5/radar_sdk"
    "$ENV{USERPROFILE}/Infineon/Tools/Radar-Development-Kit/3.6.5/assets/software/radar_sdk"
  )
endif()

find_path(InfineonRadar_INCLUDE_DIR
  NAMES ifxFmcw/DeviceFmcw.h
  HINTS ${_IFX_HINTS}
  PATH_SUFFIXES sdk/c
)
find_library(InfineonRadar_FMCW_LIBRARY
  NAMES sdk_fmcw
  HINTS ${_IFX_HINTS}
  PATH_SUFFIXES libs/win32_x64
)
find_library(InfineonRadar_LTR11_LIBRARY
  NAMES sdk_ltr11
  HINTS ${_IFX_HINTS}
  PATH_SUFFIXES libs/win32_x64
)
find_path(InfineonRadar_RUNTIME_DIR
  NAMES sdk_fmcw.dll radar_sdk.dll
  HINTS ${_IFX_HINTS}
  PATH_SUFFIXES libs/win32_x64
)

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(InfineonRadar
  REQUIRED_VARS InfineonRadar_INCLUDE_DIR InfineonRadar_FMCW_LIBRARY
                InfineonRadar_LTR11_LIBRARY InfineonRadar_RUNTIME_DIR
)

if(InfineonRadar_FOUND AND NOT TARGET InfineonRadar::Fmcw)
  add_library(InfineonRadar::Fmcw UNKNOWN IMPORTED)
  set_target_properties(InfineonRadar::Fmcw PROPERTIES
    IMPORTED_LOCATION "${InfineonRadar_FMCW_LIBRARY}"
    INTERFACE_INCLUDE_DIRECTORIES "${InfineonRadar_INCLUDE_DIR}"
  )
  # Companion import libs commonly required by sdk_fmcw.
  foreach(_lib sdk_base radar_sdk sdk_radar_device_common)
    find_library(_IFX_${_lib}
      NAMES ${_lib}
      HINTS ${_IFX_HINTS}
      PATH_SUFFIXES libs/win32_x64
    )
    if(_IFX_${_lib})
      target_link_libraries(InfineonRadar::Fmcw INTERFACE "${_IFX_${_lib}}")
    endif()
  endforeach()
endif()

if(InfineonRadar_FOUND AND NOT TARGET InfineonRadar::Ltr11)
  add_library(InfineonRadar::Ltr11 UNKNOWN IMPORTED)
  set_target_properties(InfineonRadar::Ltr11 PROPERTIES
    IMPORTED_LOCATION "${InfineonRadar_LTR11_LIBRARY}"
    INTERFACE_INCLUDE_DIRECTORIES "${InfineonRadar_INCLUDE_DIR}"
  )
  foreach(_lib sdk_base radar_sdk sdk_radar_device_common)
    find_library(_IFX_LTR_${_lib}
      NAMES ${_lib}
      HINTS ${_IFX_HINTS}
      PATH_SUFFIXES libs/win32_x64
    )
    if(_IFX_LTR_${_lib})
      target_link_libraries(InfineonRadar::Ltr11 INTERFACE "${_IFX_LTR_${_lib}}")
    endif()
  endforeach()
endif()

mark_as_advanced(
  InfineonRadar_INCLUDE_DIR
  InfineonRadar_FMCW_LIBRARY
  InfineonRadar_LTR11_LIBRARY
  InfineonRadar_RUNTIME_DIR
)
