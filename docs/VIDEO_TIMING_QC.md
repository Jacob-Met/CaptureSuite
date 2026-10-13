# Video timing quality features

Video timing QC describes the observed interval between consecutive retained frame
timestamps. Run the existing `features`, `plots`, or `all` analysis command on a
session package. Each job writes its video table under
`processing/jobs/<job_id>/features/video/<source_id>/timing_qc.parquet`, with a CSV
mirror and the existing feature schema metadata. Plot jobs also save the video FPS
figure and the synchronization dashboard series under that job's `figures/` folder.

## Reading the interval table

The table keeps one row for every consecutive pair when at least two timestamps
are available. It does not remove an observed pair merely because the pair is
unusable for cadence statistics.

| Column | Meaning |
| --- | --- |
| `t_ns` | Exact signed integer timestamp of the pair's second frame, in session nanoseconds. |
| `dt_s` | Observed second timestamp minus first timestamp, converted to floating-point seconds. This remains present for invalid pairs, including zero or negative durations. |
| `fps_inst` | `1 / dt_s` for a valid pair; `NaN` for an invalid pair. |
| `valid` | Integer boolean: `1` only for a positive interval with both endpoints inside the selected window and outside recorded gaps, and no recorded gap between the endpoints. |

Gap endpoints use the existing inclusive convention. A closed gap touching either
endpoint invalidates the pair. An open gap extends to the selected window's end.
Overlapping gaps act as a union. Reversed gap records retain the shared mask's
existing empty-interval behavior; this extractor does not repair their source
records.

For example, retained frames at `0`, `0.1`, `2.1`, and `2.2` seconds, with a recorded
disconnect from `0.2` through `2.0` seconds, produce:

| Second frame (s) | Observed `dt_s` | `fps_inst` | `valid` |
| --- | ---: | ---: | ---: |
| 0.1 | 0.1 | 10 | 1 |
| 2.1 | 2.0 | NaN | 0 |
| 2.2 | 0.1 | 10 | 1 |

The two-second observation remains in the table, while the known disconnect is
excluded from usable frame cadence. Without a recorded gap, a slow positive
interval remains valid observed timing. `nominal_rate_hz` does not impose a cutoff
or invent missing-frame records.

`mask` and `split` retain the same interval rows and validity flags. With `fail`, a
recorded gap intersecting an observed pair is refused even when neither retained
endpoint lies inside the gap. The existing job pipeline reports the stream refusal
through its normal warning and job-status handling.

## Counts, coverage, and plots

The existing `video_qc_summary` entry includes `frame_count`, `interval_count`,
`valid_interval_count`, `invalid_interval_count`, `fps_median`, `dt_p50_s`,
`dt_p95_s`, and `nominal_rate_hz`. The median FPS and timing percentiles use only
valid intervals. They are explicitly `None` when there are no valid intervals.
Duplicate and reversed timestamps therefore remain visible without producing
divide-by-zero warnings or contaminating those statistics.

The returned `validFraction` keeps its existing meaning: valid retained frames
divided by retained frames. Interval counts have a different denominator. In the
example above, every retained frame is outside the disconnect, so frame coverage
is `1.0` while only two of the three observed intervals are usable.

The video FPS figure and retained synchronization series use the table's same
masked `fps_inst` values. A line breaks across invalid cadence. The feature columns,
their units, and feature schema version `1` remain unchanged. Zero or one retained
frame keeps the existing empty-feature result. Raw source data and timestamps are
not rewritten by analysis.

## Timestamp arithmetic

Subtracting floating-point timestamps can erase short intervals at large absolute
origins. At an origin of `2**60` nanoseconds, for example, two successive 100 ns
steps must remain 100 ns each. The extractor subtracts integer nanoseconds before
converting the resulting duration to floating-point seconds. Ordinary same-sign
pairs use NumPy integer subtraction; pairs crossing zero use Python integers to
handle the complete signed-int64 span without overflow. The loader's signed-int64
timestamp contract is unchanged. Floating-point seconds and rates retain their
normal rounding limits.

## Verification and receiving

The regression module is `tests/analysis/test_video_qc_intervals.py`. Its 29 cases
exercise known gaps strictly between retained frames, inclusive and open boundaries,
overlaps, window selection, duplicate/reversed timestamps, large positive and
negative origins, signed-int64 extrema, gap policies, and short/all-invalid inputs.
Real synthetic protobuf MCAP jobs verify saved Parquet and CSV values, actual plot
inputs, retained synchronization series, schema identity, and unchanged source
hashes for `features`, `plots`, and `all`.

On Python 3.12.14, the 29 cases and 39 neighboring feature/gap/pipeline cases pass;
the new module also passes under `python -O`. Scoped Ruff passes. An independent
worker accepted 550 integer/Fraction/interval oracle cases: 527 received results,
two short inputs, and 21 expected `fail` refusals. Maximum observed rounding error
was one ULP for seconds and two ULP for FPS. Both the large-origin and inter-frame
gap controls reject the original implementation.

The source composes with current main `ab17b8c50af9892483b49ce4c125ef28f38eb72c`,
preserving the separately received CSV path correction. The focused selection plus
its six writer-path regression cases passes 74 tests on that composition.

Seven alternating timed runs after warmup measured full public extraction on the
local Python 3.12.14 / NumPy 2.3.5 runner:

| Input | Original median | Corrected median |
| --- | ---: | ---: |
| 216,000 frames, no recorded gaps | 4.27 ms | 4.89 ms |
| 1,000,000 frames, no recorded gaps | 20.31 ms | 23.39 ms |
| 216,000 frames, 10 recorded gaps | 4.92 ms | 7.21 ms |

These timings cover feature extraction, not MCAP decoding, serialization, or a
hardware capture workload. Source publication, supported Windows receiving, and
installed adoption are tracked separately in
[issue 123](https://github.com/Jacob-Met/CaptureSuite/issues/123). GitHub Actions,
PR creation, and main-branch integration are not part of this receiving procedure.
