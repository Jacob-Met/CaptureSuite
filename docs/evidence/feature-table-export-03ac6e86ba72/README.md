# Selected feature export: native author qualification

Issue [#78](https://github.com/Jacob-Met/CaptureSuite/issues/78);
draft [PR #81](https://github.com/Jacob-Met/CaptureSuite/pull/81).

## Frozen source and actual outcome

Native author qualification passed on exact source
`ccc7bf599a87419b171f817f268715a94cd6b19e`, tree
`5c303593618740fc32134e4a90d8e64b835f8c46`.
The native working tree matched that published commit before execution.

- **43 maintained tests passed, no skips**, in 5.07 seconds.
- Actual current synthetic protobuf MCAP → completed features job → new export CLI passed.
- All three original Mac-created feature tables exported on Windows with selected
  mean/timestamp columns in reversed order. Actual typed CSV and Parquet readers
  returned the exact retained values, five rows per table.
- Every original Mac session/job file matched the pre-implementation inventory
  before and after export. Source hashes also remained unchanged during qualification.
- Focused Ruff and the enforced SPDX/license checker passed.
- The suite retains two upstream protobuf deprecation warnings; its supported
  execution runtime was Python 3.12.8.

This qualifies the selected-column data handoff. It does not change provisional or
calibrated scientific status, run hardware capture, or adopt an installed package.
Independent receiving and hosted gates are recorded separately as they complete.

## Preserved negative evidence

`baseline-mac.tar.gz` predates implementation and contains the actual native
baseline script, full synthetic MCAP package and three completed feature tables,
source/input inventories and command outputs. The existing selected-column
entrypoint was absent (actual exit 2), while current feature analysis completed
with strict warnings and unchanged raw hashes.

`author-qualification.tar.gz` preserves all three author iterations:

1. **v1:** the first real CLI invocation failed to import `capture_session`.
   `capture_analysis.__init__` imports the existing job module, so the CLI needed
   the same three repository library roots as the existing analysis CLI. Exact
   source hashes and original stdout/stderr are retained; execution stopped before
   a full qualification receipt could be created.
2. **v2:** the bootstrap correction passed all three cross-platform saved-job
   exports, Ruff and licenses. The maintained suite passed 40/43. All three
   failures exposed one-column null rows being skipped by the CSV reader's
   default empty-line policy (three rows read from four retained rows).
3. **v3:** the schema/guide now require `ignore_empty_lines=False`, alongside
   multiline quoted values and explicit Arrow types/null-string settings.
   Maintained readers consume the sidecar's parser options; the original values
   and row-count assertions are retained. All 43 tests and native exports pass.

Exact library, CLI, test and guide snapshots for every iteration were matched
against that iteration's captured SHA256 and byte inventory while sealing the
archive. The pre-correction test snapshot includes the one Ruff import-group
whitespace correction and is checked against the actual executed-source hash.

The maintained failure controls explicitly inject one output-capacity error
after creating a real partial file and one concurrent synthetic-parameter change
during real CSV writing. Those controls are identified in the receipt.

## Archives and readback

| File | Bytes | SHA256 |
|---|---:|---|
| `baseline-mac.tar.gz` | 31,832 | `888a7fce598cccc0947b116a463b9a248b1eb96581c73bd85a7104324b9b8972` |
| `author-qualification.tar.gz` | 208,303 | `e93aa2c5b0f24b7bc19954539e949f195e9f92aaba418760d5107f56c706e1b0` |

The author archive contains 853 entries: original logs, JSON/XML receipts,
regular fixture/output file bytes, exact source snapshots, the qualification
scripts and their inventory. Every inventoried member was read back and matched.
Forty native link observations are retained in `fixture-links.json`; the portable
archive contains regular files only and no live symlink/junction/hardlink entries.
Maintained tests recreate link behavior on the target filesystem.

Final author receipt SHA256:
`a8e1b992309310e13cd5deec44144b5c421b27beb36dd6d38b175eecad8256e5`.

## Runtime and source integration

The Mac baseline used the existing Python 3.12.8 analysis runtime. Its filesystem
and the separate scratch filesystem reached ENOSPC before the first implementation
file could be written. The original unqualified checkpoint and capacity record
remain in `CHECKPOINT.md`.

Author work moved to a distinct Windows stage. One task-local official Python
3.12.8 NuGet runtime was acquired and sealed by the independent receiver, with
catalog SHA512 verification and package SHA256
`406856be971d957e0bee7a5cefe20a5ec78d70a495e9e33cd0e53d31faec049d`.
Author and receiver use that interpreter read-only, with separate source,
fixtures, outputs and Matplotlib configuration directories. No global PATH or
installation settings changed.

Executed dependency versions are recorded in the receipt, including PyArrow
25.0.0, NumPy 2.5.3, pandas 3.0.6, pytest 9.1.1 and Ruff 0.16.10. Runtime acquisition,
dependency report and seal remain in the receiver's provenance packet.

Current main `a2fd6c58` was incorporated with both progress records preserved.
The native and GitHub merged trees matched exactly. Existing producer pipeline,
job runner, feature writers, desktop, raw exporter, dependencies and workflow
files have no changes in this contribution.
