# Recorded stream gap receiving — 2026-10-08

Project claim: [CaptureSuite #40](https://github.com/Jacob-Met/CaptureSuite/issues/40).
Contributor: `estate-e82707f2bc62 / runtime_discovery`.

## Product result

A gap recorded for an interrupted stream previously invalidated healthy samples
from sibling streams sharing its source. Real EMG feature extraction consequently
reported reduced validity, changed feature values, and rejected a healthy stream
under `gap_policy=fail`.

The candidate matches each nonempty gap source ID and stream ID before constructing
the mask. An empty stream ID still applies across that source; both IDs empty still
apply globally. Matching gaps, inclusive time boundaries, open intervals, and both
`GapSummary` and `GapInterval` inputs keep their existing behavior. The package and
sample arrays remain unchanged by analysis.

## Exact input and candidate

- Reproduction commit: `d3edda561322a80bfc1491ae4f4c7b0bb94943ea`.
- Original `windows.py` blob: `79abc9135e104b38451beb72276d75628bbcfaac`.
- Candidate `windows.py` blob: `80bea6bd69365a48c5b204c26d054b8ae179437a`.
- Frozen test blob: `c160b2f5faebf6e97b5b0817e06303f1a607b183`.
- Publication parent: `c43b2819b149e1e87d7f957d8b3583881c29ffb4`, preserving the
  separate framing-view contribution. Analysis source is unchanged between this
  parent and the reproduction commit.

`manifest.json` records SHA-256 and Git blob hashes for all 68 selected original
source/test/contract files, the candidate production file, the test, and both raw
outputs. The local working directories are verified source subsets; they are not
represented as complete repository checkouts. Publication uses the full existing
Git tree, with only the claimed production, test, progress, and evidence files
changed.

## Reproduce

Use Python 3.12 and the repository's declared analysis dependencies. From the
repository root:

```sh
PYTHONPATH=libs/python/capture_analysis:libs/python/capture_session python3 -m unittest discover -s tests/analysis -p test_stream_gap_scope.py -v
```

The focused test uses ordinary public package imports, a temporary recorded
session with three stream descriptors and a `gaps.jsonl`, package review/discovery,
native validity masks, and native EMG feature extraction. It supplies six explicit
samples at the descriptor rate. It does not substitute package modules, masks, or
feature implementations. Source-package file hashes and sample arrays are checked
for preservation.

| Stage | Same frozen test | Native outcome |
|---|---|---|
| Original source | Eight methods | Four methods pass; four fail, producing six failed and two errored subtests |
| Candidate source | Eight methods | All eight methods pass; exit 0 |

Raw unchanged outputs are `baseline.log` and `candidate.log`. The local environment
was CPython 3.12.14, NumPy 2.3.5, pandas 2.2.3. The original failure is retained and
does not count as a successful run.

## Acceptance boundary at this snapshot

The focused tests establish stream scope through real package discovery and
feature consumers. The existing hosted Python and Windows C++ workflow and
independent receiving still need their own exact-candidate outcomes. Local pytest
and Ruff were unavailable. No whole-product, daemon, physical hardware, release,
or deployment result is inferred from these eight tests. Subsequent acceptance
belongs in the linked pull request with its exact source and workflow identifiers.

## Native lint receiving follow-up

The first hosted run `37755974937`, Python job `113240491876`, passed dependency
consistency, the CI contract, and both protobuf/schema generation and byte-drift
checks, then reported one Ruff I001 in the new test import block. Pytest was skipped.
`initial-ci-lint.log` retains the unchanged diagnostic through exit 1; it is a
40-line excerpt from that job's log.

Removed only the blank line between the NumPy import and the analysis imports.
The test AST, excluding source-location attributes, is identical to the frozen
test used in the paired runs. The original test remains available at initial
commit `c2a92268ddfb7031173059f9f81dec7991f23936`, and all original raw outputs are
retained here. Current test blob: `caaf1268ee87ae62ed16c04520dcbbfea5dc7d94`.
The formatted test again passes all eight methods locally; its raw output is
`formatted-candidate.log`. Production source is unchanged. The child commit still
requires its own native workflow result; the failed predecessor is not counted
as a successful hosted run.

## Native JUnit receiving follow-up

Run `37756406356`, Python job `113241936725`, passed Ruff and license checks.
Pytest 9.1.1 then reported 227 passing test methods, 24 passing subtests and six
explicit daemon-unavailable skips, with process exit 0. The unchanged strict
receipt checker rejected the JUnit report as invalid (`ValueError`), so the native
gate failed. `initial-junit-rejection.log` retains that test/receipt output through
wrapper exit 1. The JUnit and uploaded archive hashes are recorded in the manifest.
The artifact file reference was issued, but its signed download returned HTTP 403
in this runtime; no locally observed XML counts are claimed.

The [pytest 9.1.1 JUnit implementation](https://github.com/pytest-dev/pytest/blob/9.1.1/src/_pytest/junitxml.py)
counts passed reports and reuses reporters for the same test node, while CaptureSuite's checker requires
declared counts to match actual testcase elements. Removed the new test's eight
`unittest.subTest` reporting contexts to use ordinary test-method reporting. Every
original input, loop body and assertion is preserved, verified by comparing ASTs
after stripping only those contexts. A failed assertion now ends its method, as
in an ordinary unittest test. The receipt checker and workflow remain unchanged.

Current test blob: `7b239c2ac7c002164732eeded969c628464e61df`. This exact test was
rerun against the untouched original production source in a separate baseline
directory: four methods pass, three fail and one errors. Against the unchanged
candidate production source, all eight methods pass. Raw outputs are
`final-baseline.log` and `final-candidate.log`. All earlier failures and receipts
remain available. The next hosted run must establish native receipt acceptance.
