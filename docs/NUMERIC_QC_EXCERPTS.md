# Recorded numeric excerpts in QC

Run the maintained offline entry point on a saved session:

```sh
./capturesuite-analysis qc /path/to/recording.mmsession --inspect-payloads
```

Open the resulting job's `reports/qc.html`. For a successfully decoded
`generic.numeric_batch/1` stream, **Recorded numeric excerpts** shows the first
256 recorded sample frames and the first six channels. Shorter recordings show
every available frame. The report states both the displayed and checked totals.
QC continues checking every declared-schema message after the excerpt fills.

Each lane shows exact decoded values, with no averaging, downsampling, resampling
or modification of the sealed source. Amplitude scales are independent between
lanes; units are copied from the stream descriptor. The horizontal axis is
recorded sample position, **not elapsed time**. Lines stop at batch boundaries,
which dashed vertical lines mark. Gap duration is not encoded in this axis:
use the report's Recorded gaps and Warnings sections when judging continuity.

Expand **Show excerpt source and native timestamps** to find the originating
MCAP segment, message, sample positions, batch session anchor, and unchanged
first/last native timestamp integers. These are separate clocks, with no new
synchronization or calibration. Missing native timestamps say **not recorded**.

The JSON report adds an optional, versioned
`payloadInspection.numericPreview` object with schema ID
`capture.numeric_qc_preview/1`. It retains the selected values, native timestamp
strings and batch identity for reproducible downstream inspection. It does not
change the existing QC schema or default descriptor-only workflow.

## Inspect a later episode

To inspect a grip pulse around 45 seconds in a longer recording:

```sh
./capturesuite-analysis qc /path/to/recording.mmsession --inspect-payloads \
  --start-ns 45000000000 --end-ns 45500000000
```

The bounds are inclusive session nanoseconds. Either bound may be omitted.
The report selects at most the first 256 matching frames and six channels,
shows the total matching count, and retains each original source position.
It uses the same mapping as the numeric loader: each MCAP message's session
anchor plus the difference from its first native timestamp. All arithmetic
uses integers; native and mapped timestamps are serialized as decimal strings.
This mapping is not a new clock calibration. Frames without native timestamps
cannot be precisely placed and are explicitly counted as excluded.

**The interval selects the displayed numeric excerpt only.** QC still checks
the whole selected source recording, including samples outside the interval;
its warnings and traffic lights do not become interval-only assessments.
An empty timed interval is shown explicitly. The sample-position axis still
does not encode elapsed time or gap duration, and lines stop at batch boundaries.

## Limits

- This is a bounded excerpt, not a recording-wide waveform browser. Use explicit
  bounds to reach later events; channels after the first six are not plotted.
- No preview is presented after a supported stream fails payload inspection,
  even if some early samples were readable.
- EMG and IMU retain their existing decoded checks; these numeric plots do not
  imply plots for those schemas.
- A readable trace does not establish recording-wide quality, calibrated
  measurement accuracy, physiological validity or physical synchronization.
- The self-contained HTML report works offline in desktop and phone browsers.
  The runnable executable is experimental Linux x86_64; no Windows binary or
  physical-instrument qualification is claimed by this change.

## Design reference and validation

The maintained design uses separate signal lanes, explicit labels and source
information, informed by [LabChart Lightning's signal/channel model](https://www.adinstruments.com/support/knowledge-base/how-are-signals-and-channels-configured-labchart-lightning).
A full recording array was rejected because report memory should remain bounded;
a downsampled overview was rejected because it can conceal brief excursions.
Exact bounded excerpts make those limitations reviewable.

Astra-Lumen ran the real QC CLI on a simulated two-channel force recording stored
as protobuf MCAP and inspected the resulting HTML at desktop and phone widths.
Focused tests cover actual sample order, 256-frame/six-channel limits, later QC
failures, separate batches/segments, missing clocks, unchanged source bytes,
extreme finite values and escaped channel/source labels. Release source and
download/use evidence are recorded in the versioned release and task
`capturesuite-qc-signal-traces-keel9b71`.
