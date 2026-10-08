#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Build/test the native portable subset. Does not install system packages.
set -euo pipefail
cs_src="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
cs_config="${2:-debug}"
cs_jobs="${CAPTURE_BUILD_JOBS:-2}"
cs_mcap_commit="b2953496735e7b89d5b2ea58be73abed85317c5f"

if [[ "$(uname -s)" != Linux ]]; then
  echo "This entrypoint qualifies the Linux portable subset only." >&2
  exit 2
fi
case "$cs_config" in
  debug|release) ;;
  *) echo "Usage: scripts/build-linux.sh [SRC_DIR] [debug|release]" >&2; exit 2 ;;
esac
if [[ ! "$cs_jobs" =~ ^[1-9][0-9]*$ ]]; then
  echo "CAPTURE_BUILD_JOBS must be a positive integer." >&2
  exit 2
fi
cd "$cs_src"
cs_deps="${CAPTURESUITE_DEPS:-$PWD/build/deps}"

missing=()
for tool in cmake ninja g++ pkg-config protoc git; do
  command -v "$tool" >/dev/null || missing+=("$tool")
done
if command -v pkg-config >/dev/null; then
  for package in libzstd liblz4 sqlite3; do
    pkg-config --exists "$package" || missing+=("pkg:$package")
  done
fi
if ((${#missing[@]})); then
  echo "MISSING: ${missing[*]} (see docs/BUILDING-LINUX.md)" >&2
  exit 2
fi

if [[ -z "${MCAP_INCLUDE_DIR:-}" ]]; then
  if [[ ! -e "$cs_deps/mcap" ]]; then
    mkdir -p "$cs_deps"
    git clone --depth 1 --branch releases/cpp/v2.1.1 \
      https://github.com/foxglove/mcap.git "$cs_deps/mcap"
  fi
  if [[ "$(git -C "$cs_deps/mcap" rev-parse HEAD)" != "$cs_mcap_commit" ]] ||
     [[ -n "$(git -C "$cs_deps/mcap" status --porcelain)" ]]; then
    echo "MCAP checkout differs from the pinned clean source; left untouched." >&2
    exit 2
  fi
  export MCAP_INCLUDE_DIR="$cs_deps/mcap/cpp/mcap/include"
fi
if [[ ! -f "$MCAP_INCLUDE_DIR/mcap/mcap.hpp" ]]; then
  echo "MCAP_INCLUDE_DIR must contain mcap/mcap.hpp." >&2
  exit 2
fi

cmake --preset "linux-$cs_config" -DCAPTURE_BUILD_TESTS=ON \
  -DCAPTURE_ENABLE_CAMERA_WORKER=OFF -DCAPTURE_ENABLE_RADAR_WORKER=OFF
cmake --build --preset "linux-$cs_config" --parallel "$cs_jobs"
ctest --test-dir "build/linux-$cs_config" --output-on-failure --no-tests=error
printf 'CAPTURESUITE_LINUX_PORTABLE_BUILD_OK\n'
