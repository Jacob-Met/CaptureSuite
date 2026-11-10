# LSL bridge plugin

Records numeric [Lab Streaming Layer](https://labstreaminglayer.org/) outlets
through the existing CaptureSuite Python worker into `generic.numeric_batch/1`
MCAP segments. Version 0.1.2 includes independent outlet lifecycle and the
Python SDK 0.1.1 handoff to ordinary native-created session packages.

## Use with CaptureSuite on Windows

Use this plugin with the matching CaptureSuite source checkout and Python 3.12.
From the repository root, install the worker dependencies and LSL:

```powershell
py -3.12 -m pip install -e libs/python/capture_protocol -e libs/python/capture_worker pylsl
```

Start your numeric LSL outlet, then start CaptureSuite's existing daemon and
desktop as described in the root README. The daemon discovers
`plugins/lsl_bridge/plugin.json` and invokes `run_worker.cmd`; do not launch that
script without the daemon-provided worker pipe. Each resolved outlet appears as
its own source. Start two sources, stop one, and the other continues recording.
The launch script uses the Python 3.12 installation under LOCALAPPDATA or falls
back to `python` on PATH.

## Source and lifecycle behavior

- One `SourceInstance` per resolved stream, using LSL `source_id` or UID as identity.
- Modality comes from the outlet's LSL `type`; each stream carries a valid
  `TIMESTAMP_SOURCE_DEVICE` protocol enum.
- Every source has its own stop token and inlet. Stopping or restarting one
  source never clears or sets another source's stop token.
- Inlet polling and initial time-correction waits are bounded. Stop waits for the
  source pump to finish before the SDK seals its writer. If it does not finish
  within three seconds, Stop fails explicitly instead of sealing a writer that
  might still be receiving samples.
- Inlets close when their source pump exits. Missing pylsl is shown as an
  unavailable source. No outlet means an empty discovered source list.

## Configuration

`name_filter`, `type_filter`, `chunk_size`, and `timeout_s` are exposed through
ApplyConfig. Existing discovery filters are worker-wide. A running source keeps
its chunk size and timeout snapshot until it is stopped and started again.
String-valued LSL marker streams are not supported by this numeric bridge.

## Run the real local-outlet check

The maintained test uses two real liblsl outlets, the actual Worker Start/Stop
RPC handlers and MCAP writers. It stops the first source, verifies that the
second continues, then decodes the sealed MCAP files and checks their distinct
values. No outlet, inlet, writer or plugin is replaced. Control uses the SDK's
MemoryTransport, so this check also runs on Linux without a Windows daemon.

```bash
python3.12 -m venv .venv-lsl
.venv-lsl/bin/python -m pip install -e libs/python/capture_protocol -e libs/python/capture_worker pylsl pytest
CAPTURE_RUN_LSL_TESTS=1 .venv-lsl/bin/python -m pytest -q tests/protocol/test_lsl_bridge_live.py
```

On PowerShell, set `$env:CAPTURE_RUN_LSL_TESTS="1"` and run the same pytest command
with the installed Python 3.12. The default test suite skips the live socket test.
The SDK's named-pipe connection remains Windows-only and fails explicitly when
requested on another OS; portable import does not enable a Linux capture daemon.

## Reopen a native-created recording

The Python SDK writes to the canonical
`sources/<source>/streams/<stream>/segments` directory. Restarting a source
chooses the next segment index; an explicit occupied index is refused. Existing
sealed bytes are preserved. The default sample anchor uses the monotonic QPC
clock from StartRequest. SegmentSealed counts sample frames and includes the
last frame of a numeric batch, using retained device-time deltas or the
descriptor's nominal rate. This keeps the native package's analysis window from
silently dropping a batch tail.

The opt-in integration test creates the package through the maintained native
SessionPackage API, feeds it actual Worker SegmentSealed events, and finalizes
it before running ordinary discovery, full-window loading and feature CSV
output. It uses two real unequal-rate LSL outlets and restarts one while the
other continues. It does not construct reader metadata or relocate raw files.

After installing the Linux build dependencies in docs/BUILDING-LINUX.md:

```bash
scripts/build-linux.sh
python -m pip install -e libs/python/capture_session -e 'libs/python/capture_analysis[analysis]'
CAPTURE_RUN_LSL_TESTS=1 \
CAPTURE_NATIVE_PACKAGE_FIXTURE="$PWD/build/linux-debug/tests/cpp/capture_python_worker_package_fixture" \
python -m pytest -q tests/analysis/test_python_worker_native_live.py
```

The C++ fixture is a test driver for native storage, not a replacement capture
daemon. Real retained values, source-isolated restarts, raw-file preservation
and ordinary analysis handoff are tested; physical synchronization is not.

## Current limits

This change proves live discovery, independent source stopping and retained
numeric values on local LSL transport. It does not establish Windows named-pipe
operation, remote-clock synchronization, hardware accuracy, long recording
reliability or the full native daemon/desktop workflow.

The bridge still stores timestamps after adding its latest LSL clock
correction. The default SDK anchor is acquisition arrival time and does not fit
remote device drift or establish physical synchronization. The native storage
test uses the SDK's MemoryTransport rather than Windows named pipes. Inlet timeouts currently skip empty chunks; they do not
produce the daemon-owned capture gap records. The earlier README's claims of
raw timestamp preservation and logged gaps did not match this implementation.
