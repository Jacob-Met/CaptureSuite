# Output-failure correction and independent receiving

The independent lead receiver rejected initial candidate `6866ebd` (runtime code
at `a00e0df`). Lazy output creation had moved inside an inherited broad
`except OSError: continue` that was intended for input reads. A destination error
could therefore omit a selected IMU stream and still return success when another
selected EMG stream exported.

## Real regression and control

The lead used actual files and child CLI processes, without output mocks. The
empty destination has a valid total path length of 3890 characters. Its short EMG
source fits, while the long but valid IMU source ID exceeds Linux `PATH_MAX` after
the exporter appends its output path. Both selected streams are present in the
same sealed synthetic fixture.

| Source | Result |
|---|---|
| Untouched PR #30, `69e6cb7` | Exit 1; no manifest; input hashes unchanged |
| Initial successor, `6866ebd` | **Exit 0 with EMG present and IMU missing**; regression |
| Corrected source, `f81ce45` | Exit 1; actionable output error; no manifest; input hashes unchanged |

The original and corrected outcomes are independently recorded by the lead in
`peer-before.json` and `peer-after.json`. `original-pr30-pathmax.json` uses the
same original peer fixture as an untouched-PR control. The author also reran
that same fixture after repair (`author-after-pathmax.json`). The original lead
harness is retained verbatim as `peer-harness.py.txt`; its two workspace paths
identify the receiving environment and must be changed in a copy when replaying
elsewhere. The source test helper constructs the real MCAP fixture.

## Narrow correction

`_read_messages` streams input records and retains the previous tolerance for
input `OSError`. Its handler covers producing the next input record, so it cannot
consume an exception from the output writer. Output directory creation, file
opening, writing and close/flush errors become `ExportOutputError`; the CLI
reports the failed modality/source and instructs the operator to choose a
writable destination with space and a shorter path. It returns 1 before writing
`export_manifest.json`. Existing partial output remains available for inspection.

This changes no global input-error, recovery, hardware or raw-data policy.

## Verification on exact source

The corrected code commit is
`f81ce452ece2efc2345eda8bdf6d477a93adc6a9`. Its exporter SHA-256 is
`85874a7489c1174e8e4a27a99fcc294e0d7df2bc46a011df6cb0e86ee9b5bd40`.

- Four portable output-fault cases cover `mkdir`, `open`, `write` and `close`;
  two controls preserve input-open/read-iteration failure handling. The initial
  code fails all four output cases and passes the two input controls.
- The corrected code passes **all 31 export cases** and **all 59 analysis cases**,
  without skips. The final source is clean and byte-unchanged during acceptance.
- Whole configured Ruff, licensing, static CI contract and generated-file drift
  checks exit 0. Logs, JUnit, source manifest, exact runtime versions and commands
  are retained here. The prior completed schema generation and dependency
  consistency record remains in the parent directory.
- The lead independently reviewed the code and repeated the actual long-path
  fixture successfully. This is independent source/behavior acceptance; full
  Windows CI and native daemon acceptance remain pending.

One invocation produced no usable test evidence when the cloud overlay reached
ENOSPC: process exit 120 with a zero-byte log. It is excluded from test counts and
recorded in `invalid-enospc-attempt.json`. Only this contributor's reproducible
duplicate worktrees, full bundle and Python bytecode cache were reclaimed.
Dependency sources were preserved. Valid reruns used a private temporary
directory under `/dev/shm` and disabled new bytecode/cache writes.

Before publication, current main `c43b2819…` was merged as `9d957ba…`. Its framing
implementation/tests/evidence are preserved, and the only conflict was the
progress log: all upstream entries were retained alongside this export record.
The accepted export runtime and test bytes are unchanged by that composition.

`artifact-hashes.json` binds the raw artifacts; this explanatory README is not
part of that hash manifest. The parent directory preserves the initial candidate
receipts rather than replacing failed or superseded evidence.
