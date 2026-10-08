# QC gap attribution — ultra-20b27c2e

## Result and boundary

The existing QC report counted gaps globally while discarding their source,
stream, cause and interval. A copied sealed mini-session with a closed DISCONNECT
from session second 2.0 to 4.5 still showed its EMG source as `ok`, with an empty
QC warning list. The native CLI emitted the same incomplete JSON and HTML.

The candidate retains the gap inventory in `capture.analysis_qc/2` and the
existing HTML report. It preserves prior QC fields, reported identities and
causes, uses decimal strings for exact native integer times/counts, and names
unknown-duration reasons. Listed gaps make their reported source at least
`warn`; an existing `fail` remains dominant. This is a request to review recorded
coverage, not a new device-failure classification. The native schema has no
planned-pause cause. Overlapping records remain separate.

The two production files are `capture_analysis/qc.py` and `report_html.py`.
The authored regression module, `docs/design/ANALYSIS.md`, and the required
additive research progress entry complete the five-path change. Raw readers,
feature masks, job lifecycle, platform code, dependencies and capture hardware
are outside this change.

## Exact source

| File | Candidate SHA-256 |
|---|---|
| `libs/python/capture_analysis/capture_analysis/qc.py` | `f24e0593a3723311d41054aef40b56c4bb46d4f3ba5ef4b01afcae3a6cc4440a` |
| `libs/python/capture_analysis/capture_analysis/report_html.py` | `f2c89c7faf6e4edc265540140272396b4195eb5aed9edf05c4912aac74286f03` |
| `tests/analysis/test_qc_gap_details.py` | `9c6942a27fd37c01262d388e0834bdd49154a430b20cdf294791d6007e98f690` |

The preserved original production files have Git blob hashes
`7221b26a129b7915a42fed900908a04eae213454` and
`a0bb34d71fe03a4426ef0479619fa8d22a7bc8fa`. The reproduction began on main
`d3edda561322a80bfc1491ae4f4c7b0bb94943ea`.

The author full-analysis replay used the original dependency copy. At receiving
main `a1b3c966bc8df46fd8160d3854c30a9e03c6a478`, its 77 relevant
analysis/session package, analysis-test, fixture, CLI/demo, pytest configuration
and schema paths remained byte-identical. A separate independent receiver then
qualified seven native cases against the current 100-file source closure,
including protocol framing blob `9dd5021b815b31ab02eaaa814210525ebb543862`;
all 98 unowned files were verified and preserved. The full analysis directory
was not rerun with that newer framing file. See the independent review below.
The receiving manifest must be refreshed at publication; shared `PROGRESS.md`
is composed from the then-current complete file plus this contribution's append.

## Native verification

| Execution | Original report code | Frozen candidate |
|---|---:|---:|
| Same 25 authored cases within final full analysis replay | 24 failed, 1 passed | 25 passed |
| Complete `tests/analysis` directory, including those cases | 26 failed, 15 passed, 3 skipped (2.92 s) | 2 failed, 39 passed, 3 skipped (2.79 s) |
| Actual CLI with `--strict-warnings`, no-gap control | See original baseline witness | Exit 0, `completed`, source `ok` |
| Actual CLI with `--strict-warnings`, closed-gap witness | Negative CLI control is retained in the full baseline replay | Exit 2, `completed_with_warnings`, affected source `warn` |

All new cases pass. They cover original writer keys and source-directory
fallback, discovered and gap-only sources, failure-severity preservation,
canonical and unexpected cause text, overlapping records, open/missing/reversed
intervals, negative and extreme timestamps, exact loss counts, legacy-report
honesty, HTML escaping, actual job/CLI outputs and raw input hashes.

The two remaining failures are identical on original and candidate code:
`test_export_writes_manifest_and_sidecar` needs unavailable PySide6, and
`test_dummy_stream_handler_writes_parquet` needs unavailable PyArrow or
Fastparquet. Three existing module skips require unavailable MCAP (phase B,
pose, and kinematics through pose). No assertions or skip rules were altered.
This is **not a full analysis, native-platform, hosted-Windows or hardware pass**.

Python 3.12.14 and pytest 9.1.1 used the installed native NumPy 2.3.5, SciPy
1.17.0, pandas 2.2.3, Matplotlib 3.10.8, PyYAML 6.0.3 and jsonschema 4.26.0.
The latter was reused read-only from a sibling task's existing environment.
No package was installed or substituted. The initial simple baseline witness
predates that reuse and records the missing-jsonschema job warning explicitly;
its QC result and raw input checks remain exact. The final paired suite and
candidate CLI witness use jsonschema 4.26.0.

The full invocation and environment paths are retained in
`execution-commands.json`. The normal replay shape from a prepared project
environment is:

```bash
python -m pytest -q tests/analysis -ra
python -m pytest -q tests/analysis/test_qc_gap_details.py
```

Scoped Ruff with `--no-cache`, the repository license checker, and
`git diff --check` pass. No live model, device, recording or deployment request
was used.

## Evidence and resource handling

`baseline-reproduction.json` contains the original native package/CLI witness,
the exact synthetic gap and raw before/after hashes. Its original producing
script and both original production files are retained. That script uses its
recorded workspace layout; the checked-in regression module is the portable
receiver for a normal checkout.

The final paired full-analysis logs and JUnit files distinguish actual failures,
passes and existing skips. `candidate-cli-receipt.json` binds the paired CLI
commands, complete output manifests, emitted QC and identical raw input hashes
before and after execution. `candidate-qc.html` is the emitted synthetic report;
it is not a hardware recording.

A first full candidate attempt stopped before collection because the shared
root filesystem left no usable default temporary directory. Its raw traceback
is retained separately, together with the initial baseline run. The final pair
used a bounded, owned temporary directory on the available tmpfs; neither test
selection nor capture behavior changed. Reproducible pytest fixture directories
were reclaimed after the relevant logs, source and explicit CLI witnesses were
preserved. No other task's files or installed environments were changed.

## Independent current-source receiving

[The independent review](independent-review/REVIEW.md) records **7 passed**,
with no failures, errors or skips, using the same frozen production files and
the current framing dependency. It challenges compound source/stream mapping,
failure-severity dominance, exact signed-64-bit endpoint differences, unknown
durations, snapshot custody, HTML escaping and the real CLI. Its original-QC
control has one expected failing gap case and one passing no-gap case. All 12
raw package-file hashes remain unchanged in each CLI replay, and the emitted
JSON/HTML hashes agree with their job manifests. The independent source-closure,
harness, raw logs, JUnit files and four paired CLI receipts are retained without
modification.

The earlier `baseline-regressions.log` and `candidate-regressions.log` record
the first 25-case replay before final formatting-only changes. The final full
analysis logs bind the exact frozen source/test pins. The initial storage
failure and both earlier baseline full-run artifacts are retained as historical
attempts, without relabeling them as the final replay.

The recorded `review.patch` and `patch-receipt.json` preserve the successful
five-path transport check before the final PROGRESS review-status/link update.
The two production files, authored test module and ANALYSIS.md are unchanged
since that check. The final PROGRESS still preserves the complete receiving
original as an exact prefix; full remote-tree preservation and the final
documentation bytes must be checked at publication.

Source publication and exact-head hosted gates remain pending. The source and
raw evidence are already retained in the shared workspace; the final small
metadata packet uses an owned temporary-memory directory because the shared
root filesystem was full. Publication will provide the durable repository copy.

