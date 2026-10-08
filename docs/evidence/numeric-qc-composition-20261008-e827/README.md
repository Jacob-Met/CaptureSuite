# Numeric CLI receiving after QC gap reporting changed

This is a test-only receiving successor for CaptureSuite PR #49 after current main `fae29ddcbc0380b7d7e307130093bc5d66bf2f90` integrated QC PR #50. The earlier accepted run receipts retain their original source bindings.

## Why the expectation changed

The case-only stream fixture deliberately records one closed DISCONNECT gap for source `sampler.a`, stream `A`. The new QC contract correctly emits `sampler.a: 1 recorded gap(s); see gap details`, marks that source `warn`, and publishes `capture.analysis_qc/2`. The old test called its gap-free healthy-job assertion, so it failed against this valid new behavior.

The successor changes only `test_case_only_stream_ids_keep_distinct_paths_and_gap_provenance`. It requires the exact QC warning, job status `completed_with_warnings`, and strict-warnings exit code 2. It also checks the QC schema, gap identity and timing, and the unaffected source's `ok` state. Every pre-existing artifact, figure, feature-table, independent-path and raw-preservation assertion remains. The other six methods and all helpers are byte-identical, including the gap-free strict-zero controls.

## Exact receiving

The prior test is Git blob `b3c91a705d9ec1ec8adbefee2f19b164197b33a5`, SHA-256 `5d5e7105330d31c8f8e9cbb624641808703a719d62a3674ad69faf1f08d18f22`. The successor is Git blob `9d1bc393b23ed30e52cab2e6f65e8ac7a96018d8`, SHA-256 `cde85c2220a9428dd6509a0ab2e5e94253370772ea1152dfc072479b1c973e6a`.

The source owner supplied an exact 59-file native source slice composed from current main and the frozen numeric packet. Independent receiving verified that all six numeric production blobs remain unchanged. The same source bytes were used for both processes and remained unchanged during and between them.

| Receiving step | Result |
| --- | --- |
| Old one-case test on current QC composition | 1 failure, no errors or skips; exact added QC warning caused the failure |
| Successor one-case test on the same composition | 1 pass, no errors or skips |
| Actual strict CLI subprocess in both cases | exit 2, `completed_with_warnings` |
| Source and raw fixture bytes | unchanged in both cases |

The isolated local environment still lacks `jsonschema`. Both runs explicitly allow only the previously documented missing-validator warning in addition to the exact QC warning. This receipt does not claim local clean schema validation. The published unchanged native CI must run the full test suite with the real validator installed; that gate is pending when this packet is prepared.

## Files

`source-freeze.json` binds the test and all six production hashes. `prior-test-failure.log` and `prior-one-case-receipt.json` preserve the failure without rewriting it. `successor-test-pass.log` and `successor-one-case-receipt.json` preserve the affected-case success, actual process output and input hashes. `test-only.patch` is the complete one-method change. Older logs and figures are not duplicated.

With the repository's existing CI dependencies, protobuf bindings and generated schemas available, the affected case can be run directly:

```bash
python -m pytest tests/analysis/test_numeric_cli_receiving.py::NumericCliReceiving::test_case_only_stream_ids_keep_distinct_paths_and_gap_provenance
```

Only the affected case was rerun locally. This work makes no numeric production, hardware, provider, installed-host or deployment change.
