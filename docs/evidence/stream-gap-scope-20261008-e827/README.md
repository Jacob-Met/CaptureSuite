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
