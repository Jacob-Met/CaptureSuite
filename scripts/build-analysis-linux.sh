#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Build a standalone experimental offline QC executable for Linux x86_64.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
    echo "Only Linux x86_64 release binaries are supported" >&2
    exit 2
fi
py="${PYTHON:-python3}"
export PYTHONPATH="$repo/libs/python/capture_analysis:$repo/libs/python/capture_session:$repo/libs/python/capture_protocol${PYTHONPATH:+:$PYTHONPATH}"
"$py" -m pip check
"$py" -c 'import PyInstaller, capture_analysis, capture_session, capture_protocol, mcap, yaml, jsonschema'
out="${OUTPUT_ROOT:-$repo/build/analysis-linux-release}"
mkdir -p "$out"
"$py" -m PyInstaller --noconfirm --clean --onedir \
    --name capturesuite-analysis \
    --distpath "$out/dist" \
    --workpath "$out/work" \
    --specpath "$out/spec" \
    --paths "$repo/tools" \
    --paths "$repo/libs/python/capture_analysis" \
    --paths "$repo/libs/python/capture_session" \
    --paths "$repo/libs/python/capture_protocol" \
    --collect-submodules capture_analysis \
    --collect-submodules capture_protocol \
    --collect-submodules mcap \
    --collect-data matplotlib \
    --add-data "$repo/libs/python/capture_analysis/capture_analysis/plugins/manifest.yaml:capture_analysis/plugins" \
    --add-data "$repo/schemas/session/jsonschema:schemas/session/jsonschema" \
    --add-data "$repo/docs/design/research/schemas/analysis_plugin_manifest.schema.json:docs/design/research/schemas" \
    --exclude-module PySide6 \
    "$repo/tools/analysis_bundle_entry.py"
if [[ ! -x "$out/dist/capturesuite-analysis/capturesuite-analysis" ]]; then
    echo "PyInstaller finished without a runnable QC executable" >&2
    exit 1
fi
"$out/dist/capturesuite-analysis/capturesuite-analysis" --help >/dev/null
"$out/dist/capturesuite-analysis/capturesuite-analysis" qc --help >/dev/null
"$out/dist/capturesuite-analysis/capturesuite-analysis" export-table --help >/dev/null
"$out/dist/capturesuite-analysis/capturesuite-analysis" jobs --help >/dev/null
cp "$repo/NOTICE" "$out/dist/capturesuite-analysis/NOTICE"
cp "$repo/LICENSE" "$out/dist/capturesuite-analysis/LICENSE"
cp "$repo/LICENSING.md" "$out/dist/capturesuite-analysis/LICENSING.md"
cp "$repo/docs/OFFLINE_ANALYSIS_LINUX.md" "$out/dist/capturesuite-analysis/README.md"
cp "$repo/docs/FEATURE_TABLE_EXPORT.md" "$out/dist/capturesuite-analysis/FEATURE_TABLE_EXPORT.md"
"$py" "$repo/tools/collect_analysis_notices.py" \
    "$out/work/capturesuite-analysis/Analysis-00.toc" "$out/dist/capturesuite-analysis"
git rev-parse HEAD > "$out/dist/capturesuite-analysis/SOURCE_COMMIT"
"$out/dist/capturesuite-analysis/capturesuite-analysis" --version
echo "CAPTURESUITE_LINUX_ANALYSIS_BUNDLE_OK=$out/dist/capturesuite-analysis"
