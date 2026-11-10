#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Install declared desktop/analysis packages in an isolated environment, then run the native app.
set -euo pipefail
cs_repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cs_python="${PYTHON:-python3}"
cs_venv="${CAPTURE_DESKTOP_VENV:-$cs_repo/.venv-desktop}"
"$cs_python" -c 'import sys; assert sys.version_info[:2] == (3, 12), "CaptureSuite requires Python 3.12"'
if [[ ! -x "$cs_venv/bin/python" ]]; then
    "$cs_python" -m venv "$cs_venv"
fi
if [[ ! -f "$cs_venv/.capturesuite-desktop-ready" || "${1:-}" == --setup-only ]]; then
    "$cs_venv/bin/python" -m pip install \
        -e "$cs_repo/libs/python/capture_protocol" \
        -e "$cs_repo/libs/python/capture_session" \
        -e "$cs_repo/libs/python/capture_analysis[analysis]" \
        -e "$cs_repo/desktop[analysis]" 'mcap>=1.5,<2'
    touch "$cs_venv/.capturesuite-desktop-ready"
fi
if [[ "${1:-}" == --setup-only ]]; then
    exit 0
fi
exec "$cs_venv/bin/python" -m capture_desktop "$@"
