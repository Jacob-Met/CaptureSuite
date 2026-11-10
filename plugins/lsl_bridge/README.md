# LSL bridge plugin

Records numeric [Lab Streaming Layer](https://labstreaminglayer.org/) outlets
through the existing CaptureSuite Python worker into `generic.numeric_batch/1`
MCAP segments. Version 0.1.1 repairs live outlet discovery and makes stopping
one source independent of other outlets in this shared worker.

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

## Current limits

This change proves live discovery, independent source stopping and retained
numeric values on local LSL transport. It does not establish Windows named-pipe
operation, remote-clock synchronization, hardware accuracy, long recording
reliability or complete sealed-session integration.

Existing timing and packaging limitations remain: the bridge stores timestamps
after adding its latest LSL clock correction, and the generic SDK's default
session-time anchor uses wall clock with a QPC start field. The SDK writes worker
segments beneath `streams/<source>/<stream>`; native daemon/package integration
needs separate validation. Do not interpret these files as a validated
synchronized recording. Inlet timeouts currently skip empty chunks; they do not
produce the daemon-owned capture gap records. The earlier README's claims of
raw timestamp preservation and logged gaps did not match this implementation.
