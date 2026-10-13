# Saved synchronization dashboard JSON

New dashboard data files use `capture.sync_dashboard_series/2`. The file remains
`figures/sync_dashboard_series.json` in a newly created analysis job.

## Missing observations are explicit JSON null

The `y` array contains finite JSON numbers or `null`. NaN, positive infinity and
negative infinity are unavailable observations and are written as `null`. Every
position remains present and aligned with its original `t_ns` value. No missing
point is replaced with zero, removed, interpolated or connected to its neighbor.

For a video interval interrupted by a recorded gap:

    {"t_ns": [100000000, 2100000000, 2200000000],
     "y": [10.0, null, 10.0]}

The first and last observations are 10 FPS. The middle interval is unavailable.
Integer timestamps retain their exact numeric decimal representation and ordering.
This change does not convert timestamps to strings; JavaScript consumers that
need integers above 2**53 must still use a parser that preserves them exactly.

The document retains its title, window, gaps, series order, labels and colors.
Finite values, including signed zero, retain their prior serialization. The schema
identifier changes even for an entirely finite document, so readers can recognize
the nullable-value contract. Remaining nonfinite JSON tokens are refused by the
serializer rather than emitted as invalid JSON.

## Compatibility and preserved science

Version 1 emitted bare `NaN`/`Infinity` tokens for missing or nonfinite values.
Python's permissive JSON parser accepted them, but standards-compliant parsers
rejected the entire document. Version 2 uses JSON null. The existing desktop path
loads JSON and calls `numpy.asarray(y, dtype=numpy.float64)`, which turns null into
NaN at the same position. A standalone consumer must apply the same missing-value
interpretation before plotting or computing with the series.

Existing saved version-1 jobs are not rewritten. Their current Python reader still
accepts them. The version-2 producer changes only the saved dashboard JSON and its
normal output-inventory hash/size; it does not modify arrays passed to plotting,
feature tables, PNG rendering, source recordings, native timestamps, gap policy
or physical synchronization. Infinity's sign is intentionally not retained in the
nullable visualization export; both signs mean an unavailable observation here.
The feature tables and original inputs keep their independent representation.

## Verification and limits

`tests/analysis/test_sync_series_json.py` receives real pipeline figures with
finite, NaN and both infinite values, float32/strided inputs, exact large integer
timestamps, signed zero and strict JSON parsing. It verifies unchanged plotted
array identities/bytes and exact output inventory. Actual four-frame protobuf MCAP
jobs check the saved null position, feature values and raw fingerprints. Legacy
version-1 and new version-2 values are also received through the existing NumPy
conversion contract. These are offline data checks, not a desktop UI or hardware
qualification. Independent review and exact source/native receipts are tracked in
CaptureSuite issue134.
