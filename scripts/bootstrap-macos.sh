#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Reproducible Apple-silicon macOS bootstrap for CaptureSuite core C++ builds.
#
# This script provisions only the pinned vcpkg checkout when explicitly asked.
# It does not install system packages, enable camera/radar workers, or modify an
# existing vcpkg checkout whose HEAD differs from the repository baseline.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap-macos.sh [--release] [--configure-only] [--provision-vcpkg]

Defaults:
  preset: macos-arm64-debug
  VCPKG_ROOT: $HOME/.cache/capturesuite/vcpkg
  build jobs: 4 (override with CAPTURE_BUILD_JOBS)

--provision-vcpkg clones/bootstrap the exact vcpkg baseline only when the
configured VCPKG_ROOT is absent. Existing mismatched checkouts fail closed.
EOF
}

preset="macos-arm64-debug"
configure_only=0
provision_vcpkg=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --release)
      preset="macos-arm64-release"
      ;;
    --configure-only)
      configure_only=1
      ;;
    --provision-vcpkg)
      provision_vcpkg=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [ "$(uname -s)" != "Darwin" ]; then
  echo "error: CS-MAC-A bootstrap requires macOS (Darwin)." >&2
  exit 2
fi
if [ "$(uname -m)" != "arm64" ]; then
  echo "error: this qualified bootstrap targets Apple-silicon arm64 only." >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: required command not found: $1" >&2
    exit 2
  fi
}

require_cmd git
require_cmd cmake
require_cmd ninja
require_cmd xcrun

python_cmd=""
for candidate in python3.12 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)' >/dev/null 2>&1; then
      python_cmd="$candidate"
      break
    fi
  fi
done
if [ -z "$python_cmd" ]; then
  echo "error: CPython 3.12.x is required (python3.12 or python3)." >&2
  exit 2
fi

cmake_version="$(cmake --version | sed -n '1s/^cmake version //p')"
if ! "$python_cmd" - "$cmake_version" <<'PY'
import re
import sys
m = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", sys.argv[1])
raise SystemExit(0 if m and (int(m.group(1)), int(m.group(2))) >= (3, 28) else 1)
PY
then
  echo "error: CMake 3.28 or newer is required; found ${cmake_version:-unknown}." >&2
  exit 2
fi

baseline="$("$python_cmd" - <<'PY'
import json
from pathlib import Path
value = json.loads(Path("vcpkg.json").read_text(encoding="utf-8"))["builtin-baseline"]
if not isinstance(value, str) or len(value) != 40:
    raise SystemExit("invalid vcpkg builtin-baseline")
print(value)
PY
)"

: "${VCPKG_ROOT:=$HOME/.cache/capturesuite/vcpkg}"
export VCPKG_ROOT

if [ ! -d "$VCPKG_ROOT/.git" ]; then
  if [ -e "$VCPKG_ROOT" ]; then
    echo "error: VCPKG_ROOT exists but is not a git checkout: $VCPKG_ROOT" >&2
    exit 2
  fi
  if [ "$provision_vcpkg" -ne 1 ]; then
    echo "error: pinned vcpkg checkout missing at $VCPKG_ROOT" >&2
    echo "rerun with --provision-vcpkg or set VCPKG_ROOT to a checkout at $baseline" >&2
    exit 2
  fi
  mkdir -p "$(dirname "$VCPKG_ROOT")"
  git clone https://github.com/microsoft/vcpkg.git "$VCPKG_ROOT"
  git -C "$VCPKG_ROOT" checkout --detach "$baseline"
  "$VCPKG_ROOT/bootstrap-vcpkg.sh" -disableMetrics
fi

vcpkg_head="$(git -C "$VCPKG_ROOT" rev-parse HEAD)"
if [ "$vcpkg_head" != "$baseline" ]; then
  echo "error: VCPKG_ROOT is at $vcpkg_head but CaptureSuite requires $baseline" >&2
  echo "refusing to reset an existing checkout; use a dedicated pinned VCPKG_ROOT." >&2
  exit 2
fi
if [ ! -x "$VCPKG_ROOT/vcpkg" ]; then
  if [ "$provision_vcpkg" -ne 1 ]; then
    echo "error: $VCPKG_ROOT/vcpkg is missing; rerun with --provision-vcpkg to bootstrap." >&2
    exit 2
  fi
  "$VCPKG_ROOT/bootstrap-vcpkg.sh" -disableMetrics
fi

echo "CaptureSuite CS-MAC-A bootstrap"
echo "repo=$(git rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
echo "host=$(sw_vers -productVersion) $(uname -m)"
echo "compiler=$(xcrun clang++ --version | head -n 1)"
echo "cmake=$cmake_version"
echo "ninja=$(ninja --version)"
echo "python=$("$python_cmd" --version 2>&1)"
echo "vcpkg_root=$VCPKG_ROOT"
echo "vcpkg_baseline=$baseline"
echo "preset=$preset"
echo "camera_worker=OFF radar_worker=OFF"

cmake --preset "$preset"

if [ "$configure_only" -eq 1 ]; then
  echo "configure-only complete: $preset"
  exit 0
fi

jobs="${CAPTURE_BUILD_JOBS:-4}"
case "$jobs" in
  ''|*[!0-9]*)
    echo "error: CAPTURE_BUILD_JOBS must be a positive integer." >&2
    exit 2
    ;;
esac
if [ "$jobs" -lt 1 ]; then
  echo "error: CAPTURE_BUILD_JOBS must be at least 1." >&2
  exit 2
fi

cmake --build --preset "$preset" --parallel "$jobs"
