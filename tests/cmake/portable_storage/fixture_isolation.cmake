# SPDX-License-Identifier: GPL-3.0-only
# Run the real storage test under private temporary storage containing an
# unrelated invocation's receipt. Keep failures available for inspection.
cmake_minimum_required(VERSION 3.28)
foreach(required STORAGE_TESTS TEST_ROOT)
  if(NOT DEFINED ${required})
    message(FATAL_ERROR "Missing ${required}")
  endif()
endforeach()

string(RANDOM LENGTH 24 ALPHABET 0123456789abcdef suffix)
set(root "${TEST_ROOT}-${suffix}")
if(EXISTS "${root}")
  message(FATAL_ERROR "Refusing existing fixture directory: ${root}")
endif()
set(sibling "${root}/capturesuite_atomic_test/another-invocation.txt")
file(MAKE_DIRECTORY "${root}/capturesuite_atomic_test")
file(WRITE "${sibling}" "Retain this fictional receipt from another invocation.\n")
file(SHA256 "${sibling}" before)

execute_process(COMMAND "${CMAKE_COMMAND}" -E env
    "TMPDIR=${root}" "TMP=${root}" "TEMP=${root}"
    "${STORAGE_TESTS}" "[storage][atomic]"
  RESULT_VARIABLE result OUTPUT_VARIABLE output ERROR_VARIABLE error)
if(NOT "${result}" STREQUAL "0")
  message(FATAL_ERROR
    "Storage test failed; retained ${root}: exit=${result}; ${output}${error}")
endif()
if(NOT EXISTS "${sibling}")
  message(FATAL_ERROR
    "Storage test deleted another invocation's receipt; retained ${root}")
endif()
file(SHA256 "${sibling}" after)
if(NOT before STREQUAL after)
  message(FATAL_ERROR
    "Storage test changed another invocation's receipt; retained ${root}")
endif()
file(GLOB remaining "${root}/*")
list(LENGTH remaining count)
if(NOT count EQUAL 1)
  message(FATAL_ERROR
    "Storage test left an owned temporary directory; retained ${root}")
endif()
file(REMOVE_RECURSE "${root}")
message(STATUS "Storage test preserves unrelated temporary files")
