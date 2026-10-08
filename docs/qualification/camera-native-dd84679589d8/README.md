# Native camera worker CI qualification

This job builds the real Windows camera worker with the official GStreamer MSVC
SDK and runs the repository's three existing camera cases against the original
executable and both packaged copies. It extends the linked-DLL staging fixture
received in [PR #38](https://github.com/Jacob-Met/CaptureSuite/pull/38) with actual
worker protocol, GStreamer, preview and session-package execution.

The workflow is `.github/workflows/camera-native.yml`. Its runtime evidence is
uploaded as the `native-camera-evidence` Actions artifact. The initial source
review and portable acceptance controls do not establish a Windows camera pass;
that requires a successful job and its accepted native receipt.

## Executed scope

The test-only `CAPTURE_TEST_CAMERA_WORKER_EXE` selector accepts an absolute path.
When absent, the existing tests retain their original build-tree executable.
All three original test bodies and assertions remain in place:

| Existing native case | Behavior exercised |
| --- | --- |
| `worker host spawns camera worker Identify` | Actual worker process, Hello and Identify exchange |
| `camera worker start/stop with videotestsrc` | GStreamer fake source, capture, preview and clean stop |
| `camera worker bridge seals into session package` | Worker bridge, sealed segment and session-package output |

The three executable layouts are:

- `workers/camera/capture_worker_camera.exe`
- `daemon/plugins/camera_gstreamer/capture_worker_camera.exe`
- `daemon/workers/camera/capture_worker_camera.exe`

Each process uses `CAPTURE_CAMERA_FAKE=1`, an empty working directory, a private
temporary directory and GStreamer registry, and a PATH containing only the
verified SDK's `bin` directory. The existing worker runs GStreamer's
`videotestsrc`; no replacement worker or port of its behavior is used.

The runner checks the actual x64 PE files and their direct imports. Worker and
five existing runtime-DLL hashes must match across all three layouts. The plugin
manifest must match its repository source. It then withholds only the plugin's
directly imported `libprotobuf.dll`, launches the actual plugin worker with real
pipe arguments, and requires Windows `STATUS_DLL_NOT_FOUND` (`0xC0000135`) before
any observed pipe connection. Cleanup restores the exact DLL bytes; all three
plugin cases run after restoration as the positive control.

## Pinned SDK

Both packages come from the official
[GStreamer 1.24.13 MSVC directory](https://gstreamer.freedesktop.org/data/pkg/windows/1.24.13/msvc/).
The helper verifies both SHA-256 checksums before either administrative
extraction. It extracts into a fresh job-owned directory with `msiexec /a`;
it does not install a product or change machine/user environment settings.

| Package | SHA-256 |
| --- | --- |
| `gstreamer-1.0-msvc-x86_64-1.24.13.msi` | `66915d82adda34189703c36a5d2ef145d2e3afb7afc12c66fcf2ea506e2466d2` |
| `gstreamer-1.0-devel-msvc-x86_64-1.24.13.msi` | `0afb4394c2cba3999c0f5e74f28c2ac5d98f03131140e09246d4dcd60a0a0395` |

The SDK manifest retains installer identities, vendor URLs, hashes, extraction
exits and log hashes, required header/import-library hashes, every extracted DLL
and executable, and the actual version probe. The runner checks that runtime
binary inventory and those required files before and after native execution.
This is explicit runtime-code coverage; other SDK documentation and development
files are outside that file-comparison gate.

## Acceptance and retained evidence

Each layout must exit zero and provide Catch2 native XML containing exactly the
three distinct expected camera case names. Case totals must be three successful,
zero failed, zero expected failures and zero skipped; assertion totals are
checked separately. Missing, partial, duplicated, unrelated, malformed or
contradictory reports fail acceptance. Parser controls exercise these refusals
and the SDK/PE/pipe evidence boundaries without claiming camera execution.

The fresh `build/evidence/camera-native-<time>-<id>/` directory retains:

- `receipt.json`, the final acceptance decision and explicit limitations.
- `source-manifest.json`, the actual source file hashes, commit and dirty state.
- `binary-manifest.json`, the actual PE/import identities for all layouts.
- Each layout's native XML, combined log, invocation and execution environment.
- The actual missing-DLL process receipt and exact restoration result.

Acceptance also requires unchanged source during the receiving run, unchanged
build binaries, unchanged SDK manifest files, all three successful layout groups
and the successful negative control. A source worktree marked dirty is reported
as dirty. The source snapshot records working bytes before and after these tests;
the fresh hosted checkout, configure and build logs establish the compilation
relationship. Running the receiver against an existing build does not reconstruct
that build\'s earlier source history.

## Running on Windows

Use a PowerShell 7 MSVC development environment, the repository's existing
pinned vcpkg registry and Python 3.12. Choose fresh absolute SDK and evidence
directories. The CI workflow contains the complete setup; its essential
commands are:

```powershell
python -m unittest discover -s tests/protocol -p test_camera_ci_qualification.py -v
./tools/prepare_camera_ci.ps1 -SdkDirectory $sdk -EvidenceDirectory $evidence
$receipt = Get-Content -LiteralPath (Join-Path $evidence "manifest.json") -Raw | ConvertFrom-Json
$env:GSTREAMER_1_0_ROOT_MSVC_X86_64 = $receipt.gstreamer_root
$env:PATH = (Join-Path $receipt.gstreamer_root "bin") + ";" + $env:PATH
cmake --preset windows-release -B build/camera-native -DCAPTURE_ENABLE_CAMERA_WORKER=ON -DCAPTURE_WERROR=ON
cmake --build build/camera-native --target capture_worker_camera capture_daemon capture_core_tests -j 4
python tools/qualify_camera_ci.py --build-dir build/camera-native --sdk-manifest (Join-Path $evidence "manifest.json")
```

The evidence directory must be inside the checkout for the receiving command.
The SDK can remain outside it. The workflow uses a fresh ephemeral hosted
Windows runner, preserving the established fleet and migration owners.

This gate qualifies the synthetic GStreamer source and explicit executable
selection. Physical camera capture, automatic daemon manifest resolution,
installation, deployed services and end-user recording remain separate gates.
