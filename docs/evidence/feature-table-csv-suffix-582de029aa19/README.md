# Keep feature CSV mirrors beside the selected Parquet table

## User-visible correction

The shared feature writer previously replaced every `.parquet` token in the
relative path. A source named `sim.imu.parquet` therefore wrote its Parquet
table in the intended source directory, then attempted its CSV mirror in
`sim.imu.csv`. When that unrelated directory existed, its CSV could be
overwritten; otherwise the native analysis job recorded a warning and omitted
both table-output registrations.

The one-line correction uses `Path.with_suffix(".csv")`, then the existing
portable forward-slash representation. Only the terminal extension changes.
Parent directories, filename stems, source labels and table values retain
their identities. The ordinary output naming contract is unchanged.

## Source and scope

- Repository: `Jacob-Met/CaptureSuite`.
- Parent commit: `3960c0c756cd4e9facbde0d76eaaa3c31ab7c167`.
- Parent tree: `d1af33caaf7154e83def1dab035920907d417e8d`.
- Runtime source: `libs/python/capture_analysis/capture_analysis/features/io.py`.
- Original writer blob: `b998063a5036b73a67b773f70c193b1f9827c248`.
- Corrected writer blob: `dfa2e34fc881a76fb461c51dbf3e94aa4c594e0c`.
- Corrected writer SHA-256: `e7c26202f02ba870e0a2db9cb840ab64c706929efe98da111b405ce4ffb47321`.

The accompanying maintained regression is
`tests/analysis/test_feature_table_paths.py`. It covers ordinary names,
`.parquet` in directories/stems, repeated tokens, Unicode/space names and
Windows-style separators. Existing unrelated CSV sentinels, prior manifest
entries and prior schema tables must survive, and both actual output formats
must retain exact integer timestamps, values, column types and source labels.

Current feature-export ownership explicitly excluded this writer. IMU
loader/handler, EMG mathematics, job orchestration, native UI, raw recording,
schemas, dependencies and workflows are outside this increment.

## Executed qualification

| Course | Original | Corrected |
| --- | --- | --- |
| Six maintained writer cases | 1 pass, 5 failures | 6 passes |
| Scoped and inherited analysis tests | Not rerun as a combined original course | 41 passes, no skips |
| Independent actual writer receiving | 49 of 69 checks pass | 69 of 69 pass |
| Actual CLI: ordinary IMU source | Completed, both outputs registered | Completed, both outputs registered |
| Actual CLI: `sim.imu.parquet` source | Exit 0 with warning; CSV absent and Parquet unregistered | Completed, both outputs registered |

The 41-case command was:

```sh
python -m pytest tests/analysis/test_feature_table_paths.py tests/analysis/test_phase_b_features.py tests/analysis/test_plugin_registry.py tests/analysis/test_numeric_batch_pipeline.py -q
```

Ruff on the two changed Python files and
`python tools/check_licenses.py --enforce-spdx` also pass. The inherited test
run emitted two protobuf deprecation warnings, retained in its raw output.

`receive_feature_cli.py` constructs fictional recordings with the existing
MCAP fixture producer and invokes `tools/run_analysis.py features` in actual
subprocesses. Reproduce in a new output directory from the repository root:

```sh
python docs/evidence/feature-table-csv-suffix-582de029aa19/receive_feature_cli.py --repo . --out /new/receiving-directory
```

The four before/after Parquet files are byte-identical, with SHA-256
`65594844829d6d2035767a3684231995c254c9c7c3cdb16231ff8559146775e9`.
The three produced CSV files agree with their Parquet tables. All 13 input
files per package were checked unchanged by the author during each run.
The separate independent readback checks retained before/after input pairs;
it does not claim an independently recorded within-run preimage.

The independent receiver froze its path expectations and code before candidate
exposure, then ran the identical five-case course on both writer sources.
Its first attempt stopped at output-directory creation with `ENOSPC` before
calling the writer; that environmental failure remains in the original
baseline receipt. No expected product failure was suppressed.

## Evidence and limits

`packet-manifest.json` inventories the retained logs, receipts, exact executed
CLI driver, independent contract and receiver, and native output readback.
`environment.json` records Python and package versions. The independent
receiver's publication copy adds only the required SPDX comment; the exact
executed pre-comment source is recoverable by the transformation recorded in
`independent/license-header.json`. Its original receipt hashes remain intact.

This work qualifies the public writer and offline CLI on Linux using Python
3.12.14, pandas 2.2.3, NumPy 2.3.5 and PyArrow 26.0.0. It does not establish
native Windows, desktop, device or clinical validation. Actions, installed
adoption and release are separate; no hosted workflow was requested. The
coordinating root retains final review and integration.
