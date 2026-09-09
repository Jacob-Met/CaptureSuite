# Build and Toolchain

Pinned decisions for building CaptureSuite. Anything not stated here is a bug in this document, not a choice for the implementer.

## Targets

| Item | Decision |
|---|---|
| Primary platform | Windows 10 21H2 or newer, x64 only |
| C++ standard | C++20, no compiler extensions (`CXX_EXTENSIONS OFF`) |
| Compiler | MSVC from Visual Studio 2022, toolset v143, 17.10 or newer |
| Windows SDK | 10.0.22621.0 or newer |
| Build system | CMake 3.28 or newer, Ninja generator |
| C++ dependency manager | vcpkg in manifest mode |
| Python | CPython 3.12.x exactly (not 3.13, not 3.14) |
| Python env/workspace | uv |

Python 3.12 is a hard pin because PySide6 wheels lag new CPython releases. This was confirmed during prototyping: 3.14 had no PySide6 wheel, 3.12 did.

## Directory conventions

- Out-of-source builds only, under `build/<preset>/`
- `CMakePresets.json` defines `windows-debug` and `windows-release`, both Ninja, both with `VCPKG_TARGET_TRIPLET=x64-windows`
- Machine-local camera/radar/GStreamer/IFX paths live in `CMakeUserPresets.json` (gitignored). Copy from `CMakeUserPresets.example.json`.
- Warnings-as-errors in CI, warnings-only locally: `cmake/CompilerWarnings.cmake` sets `/W4 /permissive-` and adds `/WX` only when `CAPTURE_WERROR=ON`

## C++ dependencies

Declared in a single root `vcpkg.json`. No `FetchContent`, no submodules, no system-installed libraries.

| Dependency | Minimum | Used for |
|---|---|---|
| `protobuf` | 5.26 | IPC schemas, descriptor sets |
| `mcap` | 1.4 | numeric/structured stream writer and reader |
| `zstd` | 1.5 | MCAP chunk compression |
| `lz4` | 1.9 | MCAP dependency |
| `spdlog` | 1.14 | structured logging |
| `sqlite3` | 3.45 | session journal |
| `nlohmann-json` | 3.11 | session metadata JSON read/write |
| `blake3` | 1.5 | integrity hashing of sealed segments |
| `catch2` | 3.5 | unit tests |

Media Foundation (`mfplat`, `mfreadwrite`, `mfuuid`, `ole32`) links from the Windows SDK, so it needs no port.

### The one exception: GStreamer

[VIDEO_PIPELINE.md](VIDEO_PIPELINE.md) commits the camera worker to GStreamer. It is **not** taken from vcpkg. It comes from the official GStreamer MSVC development and runtime installers, 1.24 LTS or newer, discovered through the `GSTREAMER_1_0_ROOT_MSVC_X86_64` environment variable the installers set.

This deliberately breaks the no-system-libraries rule above, for two reasons that outweigh it: the vcpkg port does not ship the plugins the pipeline depends on (`mfvideosrc`, `nvcodec`, `qsv`), and building it from source adds a very long step to every clean bootstrap. The vendor's own Windows distribution is the supported way to get those plugins.

The exception is contained rather than allowed to spread:

- Only the `worker_camera` target links GStreamer. `capture_core`, `capture_daemon`, and every test outside the camera worker's own suite stay vcpkg-only.
- The target is guarded by `CAPTURE_ENABLE_CAMERA_WORKER`, default `OFF`, and configure fails with a clear message if it is `ON` and neither `GSTREAMER_1_0_ROOT_MSVC_X86_64` nor a local extract under `third_party/gstreamer/` is present. `cmake/FindGStreamer.cmake` resolves the root; `tools/gstreamer-installers/install-gstreamer.ps1` downloads via admin MSI or (default) `msiexec /a` extract without elevation.
- The exact GStreamer version is recorded in the session manifest's `sdk_versions`, since it determines encoder behavior.

A developer who never touches the camera worker therefore never installs GStreamer, and the core build stays reproducible from the manifest alone.

The registry baseline is pinned in `vcpkg.json` to
`4334d8b4c8916018600212ab4dd4bbdc343065d1` (the verified `2025.09.17` commit).
The old `2024.12.16` registry lacks MCAP. The new pin is the first stable registry
release after the official MCAP port was added; all seven direct dependencies
and both MCAP compression features were checked. This explicit version change
replaces an unusable baseline, not a request for a latest-version upgrade.

Both CI and the tag-triggered release workflow use that full commit SHA: a version
label is not a valid `vcpkgGitCommitId`. Upgrading the registry is a deliberate
change to all three pins, not an implicit latest-version update.

`python tools/check_ci_contract.py` verifies that these pins agree before a build.
It checks this repository's configuration shape, not arbitrary workflow security.
With `--vcpkg-root vcpkg`, it validates direct ports and requested features in the
actual pinned registry checkout before CMake. Transitive resolution stays with
vcpkg. `windows-2022` retains the documented VS 2022 toolchain rather than allowing
`windows-latest` to silently select VS 2026.

### Complete Python test environment

From the repository root, in a fresh CPython 3.12 environment:

```powershell
python -m pip install -r requirements-ci.txt
python -m pip check
python tools/check_ci_contract.py --check-environment
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest tests -q -ra --ignore=tests/kill_tests
```

The requirements install all five local workspace members together, including the
analysis and desktop extras. CI explicitly imports those dependencies before tests
so an absent optional library cannot make its test coverage disappear silently.
Six daemon integration cases still require a built Windows executable; skipped
cases are reported rather than counted as passes. The destructive-test directory
remains outside this unit/UI job as before.

Generated Python import rewrites and session JSON schemas explicitly use UTF-8
with LF line endings on Windows as well as Linux. The existing byte-for-byte
regeneration assertion is retained; it is not replaced by newline normalization.

## Protobuf code generation

One `protoc` binary — the one vcpkg builds — generates every language. This guarantees C++ and Python bindings come from identical codegen.

Three outputs from `schemas/proto/capture/v1/*.proto`:

1. **C++**: generated at build time into `${CMAKE_BINARY_DIR}/generated/capture/v1/`, wired through `cmake/CaptureProtobuf.cmake` using `protobuf_generate`. Never committed.
2. **Python**: generated into `libs/python/capture_protocol/capture_protocol/generated/` and **committed**, so Python-side work needs no C++ toolchain or protoc.
3. **Descriptor set**: `build/generated/capture_v1.desc` (`--descriptor_set_out --include_imports`), consumed by session JSON Schema generation and by MCAP schema registration.

`tools/gen_protos.py` drives 2 and 3 and is the only supported way to refresh committed Python bindings. It locates protoc via the `CAPTURE_PROTOC` environment variable, falling back to the vcpkg install tree. CI runs it and fails if the committed output differs from freshly generated output.

## Session JSON Schema generation

`tools/gen_session_schemas.py` reads `capture_v1.desc` and emits `schemas/session/jsonschema/*.schema.json` using the protobuf canonical JSON mapping. These files are **generated and committed**, never hand-edited. CI regenerates and fails on diff.

This is the mechanism that prevents IPC and on-disk representations from drifting apart.

## Python packaging

Root `pyproject.toml` defines a uv workspace with members:

- `libs/python/capture_protocol` — generated bindings plus thin wrappers
- `libs/python/capture_session` — open, validate, and recover `.mmsession` packages
- `desktop` — PySide6 shell (stub until Milestone 4)
- `tools/session_doctor`, `tools/diagnostic_bundle` — CLIs

Lock with `uv lock`, commit `uv.lock`. Dev dependencies: `pytest`, `pytest-cov`, `ruff`, `mypy`.

Lint and type configuration lives in the root `pyproject.toml`: ruff with line length 100, mypy in strict mode for `libs/python/*` and non-strict for `desktop`.

## Build commands

```powershell
# configure and build C++
cmake --preset windows-debug
cmake --build build/windows-debug

# C++ tests
ctest --test-dir build/windows-debug --output-on-failure

# Python environment and tests
uv sync
uv run pytest

# refresh generated artifacts
uv run python tools/gen_protos.py
uv run python tools/gen_session_schemas.py
```

## CI

`.github/workflows/ci.yml` on `windows-latest`:

1. Cache vcpkg binary artifacts keyed on `vcpkg.json` hash
2. Configure and build with `CAPTURE_WERROR=ON` (sim-only; camera/radar optional job)
3. `ctest`
4. Python 3.12: proto/schema drift check, `ruff check`, full `pytest tests/`
5. `python tools/check_licenses.py --enforce-spdx`

Optional job builds the camera plugin with `CAPTURE_CAMERA_FAKE=1` when GStreamer is available.

Release tags run `.github/workflows/release.yml` to attach a win64 zip + PyInstaller desktop build.


Test state isolation: the session fixture redirects application settings, registry,
cache and child-process app-data paths to a pytest-owned temporary tree. UI smoke
tests do not use the operator's actual saved preferences or active daemon record.


### Exit-aware test receipts

`python tools/run_ci_tests.py` runs the existing Python unit/UI suite into a new
`build/evidence/python-...` directory. It retains the process exit, full log,
JUnit case counts, hashes, source commit, dirty-worktree indicator and an exact
working-source manifest. A native crash after 100% progress, missing or malformed
JUnit, contradictory case counts, an empty/all-skipped run, or source mutation
during the test cannot be reported as accepted. Skips stay separate from passes.
This validates execution evidence, not device accuracy or scientific conclusions.

### Generated headers and application warning policy

The hosted compiler identified protobuf-generated map accessors returning
`size_t` as `int`. The upstream v29.5 generator emits that conversion itself.
The existing generated `.cc` target already exempts those vendor warnings; the
corresponding generated include directory is now exported as `SYSTEM` so consumer
targets have the same third-party boundary. No hand-written include directory,
application `/W4 /WX`, or existing compiler warning helper is relaxed.

`python tools/check_cpp_warning_boundary.py`, in an MSVC environment, verifies
three real builds: a valid control succeeds, a consumer of the generated-header
pattern succeeds, and the same implicit narrowing conversion in owned source
fails with C4267. It preserves the expected failed compile log as evidence. This
is a scoped generated-code compatibility decision, not a claim that warning-free
compilation proves arbitrary inputs safe.

Reference: https://cmake.org/cmake/help/latest/command/target_include_directories.html
