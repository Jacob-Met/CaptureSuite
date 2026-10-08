# SPDX-License-Identifier: GPL-3.0-only
# Linux shim for vcpkg's `unofficial-mcap` (header-only MCAP C++ library).
# Point CAPTURE_MCAP_INCLUDE_DIR (or env MCAP_INCLUDE_DIR) at the directory that
# contains mcap/mcap.hpp  (foxglove/mcap: cpp/mcap/include).
if(NOT TARGET unofficial::mcap::mcap)
  find_path(CAPTURE_MCAP_INCLUDE_DIR mcap/mcap.hpp
    HINTS "$ENV{MCAP_INCLUDE_DIR}" REQUIRED)
  find_package(PkgConfig REQUIRED)
  pkg_check_modules(CAPTURE_ZSTD REQUIRED IMPORTED_TARGET libzstd)
  pkg_check_modules(CAPTURE_LZ4 REQUIRED IMPORTED_TARGET liblz4)
  add_library(unofficial::mcap::mcap INTERFACE IMPORTED)
  set_target_properties(unofficial::mcap::mcap PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "${CAPTURE_MCAP_INCLUDE_DIR}"
    INTERFACE_LINK_LIBRARIES "PkgConfig::CAPTURE_ZSTD;PkgConfig::CAPTURE_LZ4")
endif()
set(unofficial-mcap_FOUND TRUE)
