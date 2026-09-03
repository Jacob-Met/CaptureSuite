# Contributing to CaptureSuite

Thanks for helping. CaptureSuite is Windows-first multimodal capture
infrastructure. Please read [AGENTS.md](AGENTS.md) before architectural or
schema changes, and [LICENSING.md](LICENSING.md) before adding files.

## Prerequisites

- Windows 10 21H2+ x64
- Visual Studio 2022 (v143), CMake ≥ 3.28, Ninja, vcpkg
- CPython 3.12.x
- Optional: GStreamer 1.24+ (camera plugin), Infineon Radar SDK (radar plugin)

## Build (sim-only)

```powershell
. .\scripts\dev-env.ps1
cmake --preset windows-release
cmake --build build/windows-release --target capture_daemon
```

For camera/radar plugins, copy `CMakeUserPresets.example.json` →
`CMakeUserPresets.json` and edit paths, then use `windows-release-local`.

## Tests

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m pytest tests -q
ctest --test-dir build/windows-release --output-on-failure
```

## Pull requests

1. Keep changes focused; prefer the plugin registry over editing daemon core.
2. Version every on-disk and IPC schema change.
3. Do not hard-code vendor logic in session/storage code.
4. Run the license check: `python tools/check_licenses.py`.
5. Update docs when behavior changes (`docs/design/`, `docs/plugins/`).

## Agent / Cursor notes

Historical Cursor handoff notes live under `docs/spec/`. Prefer
`docs/design/README.md` as the implementation source of truth.

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
