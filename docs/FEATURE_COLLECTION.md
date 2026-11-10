# Collect measurements across conditions

Take the same measured columns from two or more saved analysis tables into one
CSV or Parquet file, with a condition label and recorded context on every row.
Use this for baseline, task and recovery measurements, or repeated recordings.

This is part of the maintained offline analysis executable. It reads saved
results; it does not rerun extraction, average windows, align clocks or perform
a statistical test.

## Select saved tables

Analyze the desired full-session, checkpoint or time-range scopes first. A
checkpoint names the interval **ending** at that checkpoint. Explicit ranges use
integer nanoseconds on the original session clock, with inclusive endpoints.

Inspect each saved job to get its exact table path and column names:

~~~sh
./capturesuite-analysis export-table "Study.mmsession/processing/jobs/baseline" --list
./capturesuite-analysis export-table "Study.mmsession/processing/jobs/reach" --list
~~~

Replace TABLE_PATH below with the actual path from each listing:

~~~sh
./capturesuite-analysis collect-tables \
  --input Baseline "Study.mmsession/processing/jobs/baseline" TABLE_PATH \
  --input Reach "Study.mmsession/processing/jobs/reach" TABLE_PATH \
  --column t_start_ns --column signal_mean --column gap_fraction \
  --output /existing/analysis/conditions
~~~

Those column names illustrate a numeric stream; use the names recorded by your
tables. Repeat `--input` for additional conditions or recordings. Repeated
condition labels can identify distinct trials. Selecting the same physical
job/table twice is refused to avoid counting it twice accidentally.

`--format csv`, `parquet` or `both` controls output; `both` is the default.
The new destination must be outside every selected session. Existing destinations
are left intact. Open `index.html` to see conditions, intervals, source bindings,
warnings, recorded units and a short preview before importing the data.

## Read the table

Original selected fields retain their values, types and requested order. Added
context fields precede them:

| Field | Meaning |
|---|---|
| `capture_input` | Zero-based input index in manifest.json. |
| `capture_condition` | Explicit label supplied for this input. |
| `capture_session_id`, `capture_job_id` | Recorded session and saved job. |
| `capture_source_id`, `capture_stream_id` | Per-table source binding; null when an older job did not record it. |
| `capture_scope_start_ns`, `capture_scope_end_ns` | Saved analysis bounds on that session's original clock. |
| `capture_gap_policy` | Original job gap policy. |
| `capture_job_status`, `capture_warning_count` | Original status/count; full warnings remain per input. |
| `capture_row` | Original zero-based row index within the saved table. |

Rows remain in input order, then original row order. Session clocks are not
aligned. No missing values are removed, gaps filled, units converted, columns
renamed or types coerced.

~~~python
import pyarrow.parquet as pq

data = pq.read_table("conditions/table.parquet").to_pandas()
print(data.groupby(["capture_condition", "capture_session_id"]).size())
print(data[["capture_condition", "capture_job_status", "capture_warning_count"]]
      .drop_duplicates())
~~~

These are often overlapping feature windows, not independent subjects or trials.
Unequal durations, gaps, participants and settings need a design-aware analysis:
a naive mean across rows can overweight longer or better-supported recordings.

For CSV use the explicit Arrow reader settings in
[FEATURE_TABLE_EXPORT.md](FEATURE_TABLE_EXPORT.md#read-csv-without-losing-types-or-null-distinctions).
This collection's `_schema.json` describes the whole table, including context
fields, so timestamps, nulls and literal strings need not rely on inference.

## What is checked

Inputs use the same retained-table reader as single-table export. Recorded hashes,
row counts, metadata and selected Arrow columns must agree. Selected column names,
types, units, calibration flags, feature schema version and other **recorded**
column metadata must match across inputs. Incompatible units or types are refused
before output creation.

This establishes compatibility of recorded representations only. Older jobs may
lack the estimator revision, complete window/filter definition or software source
commit. Matching version strings do not prove identical algorithms, sensor
accuracy, correct physical units or experimental comparability.

Differences in analysis parameters beyond ordinary scope/source/job/execution
selection are visible. Available job/tooling versions, parameters and warnings
remain with each input. New feature tables record source/stream bindings directly;
older missing bindings remain null with an explicit notice.

## Completion and failures

`completed` means collection finished; `completed_with_warnings` means it finished
with source warnings, missing context, differing settings or an empty input to
review. `--strict-warnings` returns exit 2 in that case. Argument errors return 2;
failed collection returns 1.

Admission failures create no destination. Later failures retain an incomplete
directory with `failure.json` where possible and **no completed manifest**.
Inputs are not modified.

Outputs are `table.csv` and/or `table.parquet`, `_schema.json`, `manifest.json`
and offline `index.html`. The versioned `capture.feature_collection/1` manifest
records inputs, scopes, settings, warnings, row counts and output identities.
The review shows the first three rows and first six selected measurements per
input; the data files contain all selected rows and fields.

## Source API

~~~python
from capture_analysis.feature_collection import FeatureTableInput, collect_feature_tables

result = collect_feature_tables(
    [
        FeatureTableInput("Baseline", baseline_job_dir, baseline_table_path),
        FeatureTableInput("Reach", reach_job_dir, reach_table_path),
    ],
    new_output_dir,
    columns=["t_start_ns", "signal_mean", "gap_fraction"],
)
~~~

For a source checkout, `python tools/collect_feature_tables.py ...` accepts the
same flags as the packaged `collect-tables` command.
