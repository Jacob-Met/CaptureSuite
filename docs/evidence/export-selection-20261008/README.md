# Selective export receiving — 2026-10-08

**Latest source acceptance:** `f81ce452ece2efc2345eda8bdf6d477a93adc6a9`, with
59 analysis cases and an independent real output-failure rerun. The initial
`a00e0df` / `6866ebd` candidate was rejected during independent review because it
could hide a destination write failure. Its original passing test record and
the later counterexample are both preserved. See [the correction record](r2/README.md)
for the accepted behavior, controls and remaining Windows gate.

Contributor: `estate-234cae4aee53 / project_production`, independent receiving of
the existing T68 implementation. T68 task ownership remains with the existing
owner. No capture device, installed app, native service, queue record or release
was changed by this receiving work.

## Inputs and result

| Input | Exact commit |
|---|---|
| Initial composition main | `742dd7dc0455cc8c060db06123c8432d919e93eb` |
| Original PR #30 | `69e6cb7120916d48732c80db870161a04e396ee9` |
| Main + original PR composition | `f733ac450d57c7f02419894091d78a634dd071b1` |
| Initial code, tests and design note | `a00e0df50263ce2f82275a3cea4ff41c301dd760` |
| Independently accepted correction | `f81ce452ece2efc2345eda8bdf6d477a93adc6a9` |
| Current main received before publication | `c43b2819b149e1e87d7f957d8b3583881c29ffb4` |
| Composition preserving current framing work | `9d957ba472a863028ca680c00b873a28292690b0` |

The original feature correctly routes the wizard's selected modalities into the
export CLI. Real protobuf payloads inside MCAP files exposed two receiving
failures beyond the original mocked tests:

1. When a neutral source ID contains both EMG and IMU, the first message's
   schema excludes the later modality from discovery. This affects separate
   stream files and multiplexed MCAP messages. Selecting IMU alone returns no
   stream; selecting both can report success with only EMG.
2. Exporting a different selection into an earlier output directory retains
   unselected files while replacing the manifest. The directory and provenance
   then disagree. Existing unrelated destination contents also remain mixed
   with the newly produced output.

The repair uses the actual schema of each message and opens EMG/IMU output only
after a matching record is decoded. It also requires a new or empty destination
before writes. A directory selected by the desktop picker remains usable when
empty; existing content is preserved with an actionable error. No deletion,
raw-file overwrite or implicit merging of exports was added.

## Initial functional verification

These results are retained for the initial candidate. They do not override the
later output-failure rejection or the corrected 59-case acceptance in `r2/`.

| Check | Original source | Initial candidate |
|---|---|---|
| Same 12 independent real-MCAP/Qt cases | **7 failed, 5 passed**, process exit 1 | **12 passed** within the analysis run |
| Existing export tests plus new cases | Not claimed as rerun on original source | **25 passed**, no skips |
| Complete `tests/analysis` | Not claimed as rerun on original source | **53 passed**, no skips; process exit 0 |
| Configured whole-repository Ruff | Previously clean in #31 handoff | **Passed**, process exit 0 |
| SPDX license check | Not rerun | **Passed**, process exit 0 |
| Static CI contract | Unchanged | **Passed**, process exit 0 |
| Protobuf/session-schema generation | Existing source baseline | Generated successfully, **zero byte drift** |
| Dependency consistency | Fresh isolated CPython 3.12 environment | `pip check`: no broken requirements |

The tests use generated EMG/IMU protobuf messages with known sequence numbers,
nanosecond timestamps, sensor/channel IDs and byte counts. They exercise the
real MCAP writer and reader, real child exporter processes, Unicode/space output
paths, both multiple-file and multiplexed-stream arrangements, and a real
PySide6 `ExportWizard`. They assert input-file hash equality, absence of
unselected output directories, requested-versus-actual sidecar flags, and
preservation of pre-existing destination bytes.

The initial 53-case acceptance binds a **clean, unchanged** source checkout at
`a00e0df…` through the repository's `source_snapshot` and `summarize` helpers.
That scoped test pass did not cover the output-error regression found later.
Runtime: Linux x86-64, CPython 3.12.14, PySide6 6.11.2, MCAP 1.5.0, protobuf
4.25.9, NumPy 2.5.3, pytest 9.1.1 and Ruff 0.16.10. Exact version/command and
source-file evidence is in `candidate-receipt.json` and
`candidate-source-manifest.json`.

## Full-suite boundary

The repository targets Windows. `tools/run_ci_tests.py` was also invoked on
current main and on the composed successor. Both stop during collection with
the same four missing-`msvcrt` errors in:

- `tests/protocol/test_daemon_e2e.py`
- `tests/protocol/test_lsl_bridge.py`
- `tests/protocol/test_python_worker_sdk.py`
- `tests/protocol/test_soak_cleanup.py`

Both native receipts report test process exit 2, zero executed passing cases,
four collection errors and unchanged source bytes. The candidate full-suite
run preceded the documentation-only/final-help-string freeze; it is retained as
platform-limit evidence, not a whole-repository pass. `--check-environment`
likewise rejects the existing `capture_worker.transport` import of `msvcrt`.
The Linux portability owner's imports/build scope was preserved.

Windows CI, native daemon behavior, hardware capture and release acceptance are
**not established by this record**. No publication or integration is implied by
this source acceptance. The successor needs repository integration and the
applicable Windows receiving gate.

## Replay

In a fresh Python 3.12 environment, from the chosen checkout:

```sh
python -m pip install -r requirements-ci.txt
python -m pip check
QT_QPA_PLATFORM=offscreen python -m pytest tests/analysis -q -ra
ruff check libs/python/capture_protocol libs/python/capture_session libs/python/capture_analysis libs/python/capture_worker workers/python_host desktop/capture_desktop tools tests plugins/example_sine_py plugins/lsl_bridge
python tools/check_licenses.py --enforce-spdx
```

On Windows, set `QT_QPA_PLATFORM=offscreen` using the shell's environment syntax
and run the repository's full configured CI instead of interpreting the Linux
platform limitation as acceptance.

For the controlled before run, copy only
`tests/analysis/test_export_selection_mcap.py` from `a00e0df…` into an isolated
checkout of `69e6cb7…`, then run that file with pytest. No original runtime
source bytes are changed. `source-pins.json` binds the original and successor
runtime files and the independent test file. The negative log and JUnit are
retained verbatim as `before-pr30.log` and `before-pr30.xml`; the final accepted
run is `candidate-analysis.log` and `candidate-analysis.xml`.

`artifact-hashes.json` records the byte hashes of the receiving artifacts present
when assembled; this explanatory README is excluded to avoid self-reference.
