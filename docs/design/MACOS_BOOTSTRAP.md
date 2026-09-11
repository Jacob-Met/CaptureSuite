# macOS Apple-silicon bootstrap

Status: **experimental portability bootstrap for issue #15 / CS-MAC-A**. This document does not change CaptureSuite's Windows production baseline, protocol/session formats, or hardware-support claims.

## Scope

This lane answers one question before application-source porting begins: can an Apple-silicon Mac configure CaptureSuite through the repository's **existing pinned vcpkg manifest** reproducibly, so dependency failures are separated from genuine source portability failures?

The root `vcpkg.json` already declares `protobuf`, `mcap[lz4,zstd]`, `spdlog`, `sqlite3`, `nlohmann-json`, `blake3`, and `catch2`, pinned by full registry commit. macOS bootstrap therefore uses that manifest rather than mixing Homebrew/MacPorts C++ packages with CaptureSuite's dependency graph.

Camera and radar workers stay **OFF** in the macOS presets. This slice does not claim GStreamer/AVFoundation worker integration, Infineon radar support, daemon transport portability, sealed-session equivalence, Qt startup, signing, notarization, or release readiness.

## Current measured evidence

On the actual arm64 Mac before this bootstrap candidate:

- macOS 26.6.2, arm64;
- CPython 3.12.8;
- current-main synthetic offline QC: PASS;
- AppleClang and Protobuf were reached by native CMake configure;
- configure then stopped at missing `spdlog` CMake package;
- host-level AVFoundation capture from `Jacob’s iPhone Camera` is separately proven in draft PR #16.

Because `spdlog` is already present in `vcpkg.json`, that stop is treated as a dependency/bootstrap ambiguity, **not** a CaptureSuite source compile verdict. CS-MAC-A removes that ambiguity by requiring the pinned vcpkg toolchain and `arm64-osx` triplet.

The Mac was not reachable to the CS-MAC-A worker when this candidate was authored, so the new presets/bootstrap are not claimed native-green until rerun on the target Mac.

## Presets

`CMakePresets.json` adds:

- `macos-arm64-debug`
- `macos-arm64-release`

Both inherit a hidden `macos-arm64-base` that fixes:

- generator: Unix Makefiles (from the Xcode command-line toolchain);
- `VCPKG_TARGET_TRIPLET=arm64-osx`;
- `CMAKE_OSX_ARCHITECTURES=arm64`;
- vcpkg toolchain: `$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake`;
- `CAPTURE_ENABLE_CAMERA_WORKER=OFF`;
- `CAPTURE_ENABLE_RADAR_WORKER=OFF`.

The existing Windows presets are unchanged.

## Fail-closed bootstrap

From a fresh checkout on the Apple-silicon Mac:

```bash
bash scripts/bootstrap-macos.sh --provision-vcpkg --configure-only
```

This performs a configuration proof only. The provisioning flag may create a dedicated vcpkg checkout at `${VCPKG_ROOT:-$HOME/.cache/capturesuite/vcpkg}` and bootstraps the **exact** `builtin-baseline` from `vcpkg.json`.

It intentionally does **not** install system packages. If an existing `VCPKG_ROOT` is at another commit, the script refuses to reset it; point `VCPKG_ROOT` at a dedicated checkout instead.

After configure succeeds, obtain the first real source compile verdict with:

```bash
bash scripts/bootstrap-macos.sh
```

or for release configuration:

```bash
bash scripts/bootstrap-macos.sh --release
```

`CAPTURE_BUILD_JOBS` controls parallel build jobs and defaults to 4.

## Preconditions and failure meaning

The bootstrap requires:

- Darwin on `arm64`;
- CMake 3.28+;
- Git;
- Xcode command-line tools (`xcrun` / AppleClang);
- CPython 3.12.x.

A missing prerequisite exits before configure. A mismatched pre-existing vcpkg checkout exits without modifying it. Once the pinned manifest is installed through the toolchain, any subsequent compile error is a more useful portability result and should be routed to the owning CS-MAC-B/C/D/E slice rather than patched inside CS-MAC-A unless it is itself a bootstrap defect.

## Verification contract

`python tools/check_ci_contract.py` now checks the macOS preset/bootstrap shape on existing Windows CI without pretending that Windows can qualify macOS execution. It fails if the arm64 triplet/architecture, vcpkg toolchain, camera/radar-off guard, matching build presets, or fail-closed bootstrap markers drift.

The Mac-native completion gate remains a real target-machine run that records exact host/tool versions, vcpkg baseline, configure result, and first genuine build failures or success. A Windows CI pass only demonstrates that this additive bootstrap did not break the existing repository contract.
