# Analyze generic numeric recordings

CaptureSuite's existing analysis commands can read `generic.numeric_batch/1`
recordings and produce numeric features and figures. This includes Python-worker
and LSL streams whose descriptive modality is `emg`, `eeg`, or another label: the
registered wire schema selects the numeric handler.

Use the normal [analysis installation](design/ANALYSIS.md), with the real MCAP,
protobuf, NumPy, pandas, PyArrow, matplotlib and schema-validation dependencies.
Run commands from the repository root, with the command before the package path:

```sh
python tools/run_analysis.py all /path/to/recording.mmsession --strict-warnings
python tools/run_analysis.py features /path/to/recording.mmsession --checkpoint-section trial
python tools/run_analysis.py plots /path/to/recording.mmsession --sources lsl.source
```

To limit a feature job to a session-time interval and a materialization budget:

```sh
python tools/run_analysis.py features /path/to/recording.mmsession \
  --start-ns 1000000000 --end-ns 5000000000 --max-ram-bytes 67108864 \
  --gap-policy split --strict-warnings
```

The command prints the job ID, status and output directory. Capture sources and
their native timestamps remain unchanged; derived files go under
`processing/jobs/<job_id>/`.

## Find the products

The job manifest lists the feature and figure paths, byte counts and SHA-256
hashes. Numeric products include:

| Product | Relative path within the job |
|---|---|
| Window features | `features/numeric/source-<hex>/stream-<hex>/windows.parquet` |
| CSV mirror | The same path with `.csv` |
| Column metadata and original stream identity | `features/_schema.json` |
| Per-channel figure | `figures/numeric/source-<hex>/stream-<hex>/channel_<index>.png` |
| Shared dashboard and data series | `figures/sync_dashboard.png` and `figures/sync_dashboard_series.json` |

Each identity component contains the exact UTF-8 bytes of the source or stream
ID encoded as lowercase hexadecimal. This preserves distinct IDs such as `A`
and `a` on case-insensitive filesystems and prevents separators or reserved names
from becoming path operations. Original `sourceId`, `streamId` and that stream's
`validFraction` are recorded in its table descriptor in `features/_schema.json`.

Numeric channel figures show elapsed time since the first retained sample. Their
title gives that sample's exact `session_time_ns`, so the origin is explicit.
The plotted values retain the stream's declared units and provisional label.
Plots may reduce point density for display; feature calculations use all retained
samples selected by the gap policy.

## How session time is derived

The native worker registers the MCAP protobuf schema name
`capture.v1.data.NumericBatch`. The loader also accepts the existing
`generic.numeric_batch/1` MCAP schema-name alias, including its JSON encoding.
The stream descriptor must declare the supported data schema and a finite,
positive `nominalRateHz`.

The [session format](design/SESSION_FORMAT.md) defines MCAP `log_time` as the
session timestamp of the first datum in a batch. For batches containing one
native device timestamp per frame, analysis uses:

```text
session_time_ns[i] = log_time + device_time_ns[i] - device_time_ns[0]
```

This preserves native within-batch time differences while using the recorded
session anchor. Each batch has its own anchor, so separate segments need not
share a device-clock epoch. This is an uncalibrated derived timebase; it does not
fit clock drift or certify hardware synchronization.

If a batch has no native timestamps, analysis derives offsets from the required
nominal rate. It marks the batch with `INTERPOLATED_TIMESTAMP` (bit 3 from the
[timing contract](design/TIMING.md)) and sets `interpolatedTimestamps: true` in
the feature column metadata. A partially populated timestamp array is rejected.
Missing or invalid nominal rates are rejected; no default 100 Hz rate is invented.

The loader selects samples inside the inclusive requested session-time window,
then stably orders retained samples and their channel values together. It does
not change timestamps to fit the window, resample the signal, deduplicate equal
timestamps, or rewrite the raw MCAP. Device timestamps remain available in that
raw recording.

## Interpret the features

`numeric.basic.v1` provides a mean and RMS for each named channel. Default windows
use the nominal sample count for one second, with a half-second hop. Only complete
sample-count windows are emitted. The temporal width can vary when native sample
times are irregular; these are sample-based QC statistics, not time-weighted
physical estimators.

`t_start_ns` is the first included sample's actual derived session timestamp.
`t_end_ns` is the last included sample's timestamp plus one nominal sample period,
an exclusive support endpoint. It can therefore extend one nominal interval past
the inclusive selection boundary without adding an out-of-window sample. The
`rate_hz` column records the nominal descriptor rate.

Mean and RMS reductions are scaled before summing or squaring, so finite double
values such as `1e308` do not become infinite merely from intermediate overflow.
All numeric feature columns carry their units, `provisional: true` and
`calibrated: false`. These products do not establish sensor calibration or clinical
validity.

Gap behavior follows the selected stream's recorded gaps:

- `mask` removes samples covered by those gaps before calculating each window.
- `split` also separates windows at recorded gap boundaries, including a gap
  between adjacent retained samples that contains no sample itself.
- `fail` uses the existing analysis failure policy when a recorded gap
  invalidates retained samples.

`gap_fraction` is the fraction of retained window samples invalidated by recorded
gaps. Each table's `validFraction` describes its retained stream samples over the
selected interval. Neither value estimates unrecorded lost frames or proves
continuous coverage between samples. The internal per-source numeric fraction
uses the minimum observed sibling-stream fraction, so a healthy sibling cannot
hide a gapped stream. Existing job orchestration does not export that internal
aggregate; the per-stream table metadata is the persisted evidence.

## Refusals and memory budgets

Malformed complete-frame counts, duplicate or changing channel layouts, partial
timestamps, backwards native time within a batch, nonfinite samples and timestamps
outside the signed 64-bit analysis range produce explicit source/stream warnings.
The pipeline can still produce products for healthy streams in the same package.

Use `--strict-warnings` when a script must distinguish a fully clean job from one
that completed with warnings. Its exit code is 2 for warning status, while a failed
job or unreadable package exits 1. The normal command can exit 0 with warnings;
inspect the printed status and job manifest. An unknown-duration QC warning can
coexist with correctly produced numeric features.

The loader estimates memory before decoding each message and allocating numeric
arrays, including retained data and copies needed for concatenation and sorting.
It uses actual payload/frame/channel sizes and a fixed overhead, so understated
descriptor density cannot suppress the check. The estimate is a materialization
budget, not an operating-system process-memory limit.

Packages without a recorded duration use the existing open analysis window. Its
sentinel bounds are not treated as a recorded duration for the memory estimate;
a small valid recording remains readable under a suitable budget. Raise
`--max-ram-bytes` or select a smaller interval when an actual estimate is refused.

## Source and receiving record

This capability is tracked in [issue #43](https://github.com/Jacob-Met/CaptureSuite/issues/43).
Its source and authored synthetic receiving cases are retained in:

- [Author source and baseline/candidate receipt](evidence/numeric-analysis-20261008-e827/README.md)
- [Independent numerical and real MCAP receipt](evidence/numeric-mcap-20261008-e827/receiving-receipt.json)
- [Independent actual CLI workflow and final figures](evidence/numeric-cli-20261008-e827/README.md)

At the publication checkpoint, local author tests passed 26/26, independent
numerical tests passed 9/9, the unchanged independent CLI suite passed 7/7, and the
final axis-label successor passed its affected actual CLI/figure receiving. The
original failed baseline runs remain recorded. Hosted current-source CI and its
real installed schema validator are a separate required integration gate, recorded
on the linked pull request. No physical-device, calibration, installed-host or
deployment result is claimed by this source receipt.
