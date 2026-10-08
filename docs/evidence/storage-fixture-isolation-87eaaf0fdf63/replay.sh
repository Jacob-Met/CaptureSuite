#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
if [[ "$(uname -s)" != Linux ]]; then
  echo "This replay qualifies Linux storage receiving only." >&2
  exit 2
fi
cs_packet="$(cd "$(dirname "$0")" && pwd)"
cs_repo="$(cd "$cs_packet/../../.." && pwd)"
cs_out="$(mktemp -d -t capturesuite-review-87ea.XXXXXX)"
cs_include="$cs_repo/libs/cpp/capture_storage/include"
cs_source="$cs_repo/libs/cpp/capture_storage/src"
cs_check="$cs_repo/tests/cmake/portable_storage/fixture_isolation.cmake"
printf 'Retaining replay output at %s\n' "$cs_out"

c++ -std=c++20 -Wall -Wextra -Wpedantic -Werror \
  -I "$cs_include" "$cs_packet/original/test_storage_posix.cpp" \
  "$cs_source/atomic_file.cpp" "$cs_source/disk_watchdog.cpp" \
  -lCatch2Main -lCatch2 -pthread -o "$cs_out/original-storage-tests" \
  >"$cs_out/original-compile.stdout.txt" 2>"$cs_out/original-compile.stderr.txt"

if cmake "-DSTORAGE_TESTS=$cs_out/original-storage-tests" \
    "-DTEST_ROOT=$cs_out/original-fixture" -P "$cs_check" \
    >"$cs_out/original-receiving.stdout.txt" \
    2>"$cs_out/original-receiving.stderr.txt"; then
  echo "The original destructive fixture unexpectedly passed receiving." >&2
  exit 1
fi
if ! grep -Fq "deleted another invocation's receipt" \
    "$cs_out/original-receiving.stderr.txt"; then
  echo "Original refusal did not reproduce the retained counterexample." >&2
  exit 1
fi

c++ -std=c++20 -Wall -Wextra -Wpedantic -Werror \
  -I "$cs_include" "$cs_repo/tests/cpp/test_storage_posix.cpp" \
  "$cs_source/atomic_file.cpp" "$cs_source/disk_watchdog.cpp" \
  -lCatch2Main -lCatch2 -pthread -o "$cs_out/candidate-storage-tests" \
  >"$cs_out/candidate-compile.stdout.txt" 2>"$cs_out/candidate-compile.stderr.txt"
"$cs_out/candidate-storage-tests" "[storage]" \
  >"$cs_out/storage-tests.stdout.txt" 2>"$cs_out/storage-tests.stderr.txt"
cmake "-DSTORAGE_TESTS=$cs_out/candidate-storage-tests" \
  "-DTEST_ROOT=$cs_out/candidate-fixture" -P "$cs_check" \
  >"$cs_out/receiving.stdout.txt" 2>"$cs_out/receiving.stderr.txt"

c++ -std=c++20 -Wall -Wextra -Wpedantic -Werror \
  -I "$cs_include" "$cs_packet/receiver_atomic.cpp" \
  "$cs_packet/original/atomic_file.cpp" \
  -Wl,--wrap=fsync -Wl,--wrap=open -Wl,--wrap=close \
  -o "$cs_out/receiver-atomic" \
  >"$cs_out/receiver-compile.stdout.txt" 2>"$cs_out/receiver-compile.stderr.txt"
"$cs_out/receiver-atomic" >"$cs_out/receiver.stdout.txt" \
  2>"$cs_out/receiver.stderr.txt"
printf 'CAPTURESUITE_STORAGE_RECEIVING_PASSED %s\n' "$cs_out"
