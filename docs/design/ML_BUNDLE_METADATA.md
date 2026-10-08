# ML-bundle producer metadata

The current producer writes `ml_bundle/windows.parquet` and
`ml_bundle/manifest.json` inside the analysis job directory. The manifest uses
`capture.ml_bundle/1`. Its grid describes the derived windows produced by
[the implementation](../../libs/python/capture_analysis/capture_analysis/ml_bundle/job.py).

## Values and alignment

Both `normalization.input` and `normalization.target` are `none`. The producer
keeps the feature scalar and aggregated targets in their incoming units.
The feature loader selects the numeric `energy` column when available, with
its existing numeric-column mean fallback. It applies no z-score transform.
Target units belong to the individual input columns; the default set contains
both angles and angular velocities.

`method = nearest_feature_window_median_targets` describes the two existing
operations: select the nearest feature timestamp to each window center, then
take each target column's median over the inclusive label window. The existing
validity mask and feature selection policy are retained.

## Requested and effective timing

The caller's `hop_sec` controls the output-center step. The producer converts it
to an integer number of nanoseconds. A separate `grid_rate_hz` argument remains
recorded as a request; it does not control this center generator.

| Manifest field | Meaning |
|---|---|
| `analysisGrids[0].rateHz` | Configured rate, `1e9 / hopNs`. |
| `params.rateBasis` | `configured_integer_hop`; identifies what the rate describes. |
| `params.hopNs` | Integer step actually used between regular centers. |
| `window.hopSec`, `params.windowHopSec` | That integer step expressed in seconds. |
| `params.requestedHopSec` | The original caller-supplied hop. |
| `params.requestedRateHz` | The original separate rate argument. |
| `params.halfWindowNs` | Integer half-width used to select labels. |
| `window.windowSec`, `params.windowSec` | Separation between the inclusive window endpoints: `2 * halfWindowNs / 1e9`. |
| `params.requestedWindowSec` | The original caller-supplied duration. |
| `params.windowBounds` | `inclusive`: labels satisfy `center - halfWindowNs <= t <= center + halfWindowNs`. |
| `params.centerPolicy` | `regular_hop` for fitting windows, or `median_fallback` for the short-source fallback. |

Here `params` means `analysisGrids[0].params`. The source schema already allows
these grid parameters and the `none` normalization values.

Regular centers begin at the first teacher timestamp plus `halfWindowNs` and
advance by `hopNs` while a complete window fits. When none fits, the existing
producer emits one center from the teacher timestamps' median. In that case
`centerPolicy` is `median_fallback`. The configured rate remains available as
configuration provenance; a single window supplies no observed cadence.
These fields describe derived windows rather than a native sensor sample rate.

For example, `hop_sec=0.3000000009` produces `hopNs=300000000`, an effective hop
of 0.3 seconds and a configured rate of approximately 3.333333333 Hz. A separate
rate request of 99 Hz remains visible in `requestedRateHz`. Similarly,
`window_sec=0.2000000019` produces a 100,000,000 ns half-width and a 0.2 second
endpoint separation.

## File and consumer contract

The analysis job's `params.json` retains the original caller parameters and
their existing digest. The enclosing `job_manifest.json` inventory identifies
the final manifest and Parquet bytes. The bundle's `sha256.windows.parquet`
also identifies the emitted window table.

Grid IDs, target names, source-job IDs, Parquet columns and the provisional
marker retain their existing meanings. The current desktop summary reads the
grid ID and target count. Evaluation consumes the recorded windows and target
columns. Consumers that need normalization can choose it explicitly from this
truthful description of the supplied values.

[Focused receiving](../evidence/ml-bundle-metadata-713adaab/README.md) binds the
metadata to three actual small Parquet witnesses and the public analysis-job
API. All three window files remain byte-identical to the original producer;
only the metadata dictionary changes.
