#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Freeze the maintained Analysis desktop for receiving recorded sessions on Linux.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
    echo "Only Linux x86_64 desktop bundles are supported" >&2
    exit 2
fi
py="${PYTHON:-python3}"
export PYTHONPATH="$repo/desktop:$repo/libs/python/capture_analysis:$repo/libs/python/capture_session:$repo/libs/python/capture_protocol${PYTHONPATH:+:$PYTHONPATH}"
"$py" -m pip check
"$py" -c 'import PyInstaller, PySide6, pyqtgraph, capture_analysis, capture_session, capture_protocol, mcap'
out="${OUTPUT_ROOT:-$repo/build/desktop-linux-release}"
mkdir -p "$out"
"$py" -m PyInstaller --noconfirm --clean --onedir \
    --name capturesuite-desktop \
    --distpath "$out/dist" \
    --workpath "$out/work" \
    --specpath "$out/spec" \
    --paths "$repo/tools" \
    --paths "$repo/desktop" \
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
    --exclude-module capture_desktop.app \
    --exclude-module PySide6.QtWebEngineCore \
    --exclude-module PySide6.QtWebEngineWidgets \
    "$repo/tools/desktop_bundle_entry.py"
bundle="$out/dist/capturesuite-desktop"
if [[ ! -x "$bundle/capturesuite-desktop" ]]; then
    echo "PyInstaller finished without the offline desktop executable" >&2
    exit 1
fi
cp "$repo/NOTICE" "$repo/LICENSE" "$repo/LICENSING.md" "$bundle/"
cp "$repo/docs/OFFLINE_DESKTOP.md" "$bundle/README.md"
cp "$repo/docs/FEATURE_TABLE_EXPORT.md" "$bundle/"
"$py" "$repo/tools/collect_analysis_notices.py"     "$out/work/capturesuite-desktop/Analysis-00.toc" "$bundle"
git rev-parse HEAD > "$bundle/SOURCE_COMMIT"
cat > "$bundle/RUN.sh" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$here/capturesuite-desktop" "$@"
LAUNCHER
chmod +x "$bundle/RUN.sh"
"$bundle/RUN.sh" --help >/dev/null
"$bundle/RUN.sh" --version
echo "CAPTURESUITE_OFFLINE_DESKTOP_BUNDLE=$bundle"
