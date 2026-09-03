# Timing Model

Canonical session time is a signed 64-bit integer count of nanoseconds. Using nanoseconds is a representation choice and implies nothing about physical accuracy.

## Clock sources

| Purpose | Source | Notes |
|---|---|---|
| Monotonic base | `QueryPerformanceCounter` with `QueryPerformanceFrequency` | Immune to NTP steps, DST, and manual clock changes |
| Wall-clock anchor | `GetSystemTimePreciseAsFileTime` | Recorded alongside T0 for external correlation only |
| Device clocks | Whatever the vendor SDK exposes | Never converted destructively; always preserved verbatim |

Session time is never derived from wall clock. Wall clock exists only so a session can be related to lab notes, other systems, and later Vicon integration.

### Converting QPC ticks to nanoseconds

Use a 128-bit intermediate to avoid overflow and drift from repeated floating-point conversion:

```
session_time_ns = ((qpc_now - qpc_t0) * 1'000'000'000) / qpc_frequency
```

with the multiply performed in 128-bit (`_umul128` or `unsigned __int128` equivalent). Never precompute `1e9 / frequency` as a double and multiply.

## Establishing T0

T0 belongs to the session, not to any device. Sequence at coordinated start:

1. Validate selected sources
2. Prepare storage and confirm the disk watchdog is satisfied
3. `Arm` every source that advertises arming; wait for readiness with a 10 s deadline
4. Establish T0: read QPC and precise system time in an interleaved triple (QPC, wall, QPC, wall, QPC, wall), take the median pairing, and set `t0_uncertainty_ns` to half the spread of the QPC reads
5. Issue `Start` to all armed sources
6. Record the actual first datum from each source and store its offset from T0
7. Journal `SESSION_STARTED` with T0, the wall anchor, and per-source start offsets

Step 6 matters: the coordinated start is a request, not a guarantee. The recorded first-datum offsets are the honest account of when each source actually began.

## Wall-clock re-anchoring

Re-anchor every 60 s. If the observed wall clock deviates from the predicted value by more than 250 ms, treat it as a discontinuity: journal `TIME_DISCONTINUITY` with the observed delta, re-anchor, and continue. The monotonic timeline is unaffected and no gap is created, because no data was lost.

Suspend and resume is handled the same way. If the QPC delta between two heartbeats exceeds 5 s, journal a discontinuity and open an `UNKNOWN` gap on every recording lane for the unaccounted interval, since data genuinely was not captured.

## Device clock mapping

Workers push `ClockSample` events at a minimum of 1 Hz, each pairing a device timestamp with the host QPC nanosecond value at which it was observed.

The daemon fits a linear model per device clock:

- Estimator: weighted least squares over a sliding 120 s window, weights decaying linearly with age
- Minimum 8 samples before a mapping is published; until then `session_time_ns` falls back to host arrival time and `quality_flags` sets `CLOCK_UNMAPPED`
- Model: `session_time_ns = offset + rate_ratio * device_time`, where `rate_ratio` is expected within 1 part in 10^4 of unity
- Outlier rejection: discard samples beyond 3 sigma of current residuals, capped at 20 percent of the window

Publication rules:

- Publish a new `ClockMapping` with a fresh `mapping_id` every 30 s, or immediately when the residual of a new sample exceeds 3 sigma
- Each mapping carries `valid_from_ns` and `valid_to_ns`; mappings are append-only and never edited
- Every data unit references the `clock_mapping_id` active when it was mapped, so re-deriving timestamps later is always possible

In-flight data is never retroactively re-stamped. A new mapping applies to subsequent data only, which keeps stored timestamps reproducible.

## The canonical timing header

Defined once in `common.proto` and embedded by every data schema. No stream may define its own timing fields.

```proto
message TimingHeader {
  int64  sequence_number          = 1;  // monotonic per stream, gaps are meaningful
  int64  device_index             = 2;  // sample or frame index as reported by the device
  int64  device_timestamp         = 3;  // device-native units, uninterpreted
  string device_timestamp_unit    = 4;  // "ns", "us", "ticks", or "" if none
  sint64 host_arrival_ns          = 5;  // QPC-based, when the host saw the datum
  sint64 session_time_ns          = 6;  // canonical session timeline
  int64  timestamp_uncertainty_ns = 7;  // honest estimate, never 0 to imply perfection
  string clock_mapping_id         = 8;  // which mapping produced session_time_ns
  uint32 quality_flags            = 9;  // bitmask, see below
}
```

### Quality flags

| Bit | Name | Meaning |
|---|---|---|
| 0 | `CLOCK_UNMAPPED` | session time is host arrival, no device mapping yet |
| 1 | `SEQUENCE_DISCONTINUITY` | sequence number jumped |
| 2 | `DEVICE_REPORTED_ERROR` | vendor SDK flagged this datum |
| 3 | `INTERPOLATED_TIMESTAMP` | timestamp inferred from rate, not reported |
| 4 | `AFTER_RECONNECT` | first datum after a reconnect |
| 5 | `SATURATED` | value at or beyond device range |

## Uncertainty budget

Initial estimates, to be replaced by measurement during the vendor milestones. Documented next to each adapter, per the coding rules.

| Source class | Estimate | Dominant term |
|---|---|---|
| Camera | half a frame period | driver timestamp granularity |
| EMG (Delsys) | 0.5 ms | base station buffering and radio latency |
| IMU (Xsens) | 2 ms | wireless jitter and retransmission |
| Radar (BGT60TR13C) | tens of ms | sliced USB transfer, no device timestamp |

Do not report an uncertainty better than the mechanism can justify. A wrong small number is worse than an honest large one.

The radar row was revised down from an assumed 0.5 ms once the board was measured. There is no frame trigger to observe: the SDK exposes no device-native frame timestamp, and it transfers data in slices unaligned to frame boundaries, so a single pull can return a frame that has been buffered. See [RADAR_PIPELINE.md](RADAR_PIPELINE.md) and [adapters/infineon_bgt60tr13c.md](adapters/infineon_bgt60tr13c.md).

## Gap taxonomy

A gap is any interval where a stream that should have been recording produced no data. Gaps are always explicit, always journaled, and never interpolated away.

| Cause | Raised when |
|---|---|
| `DISCONNECT` | source dropped, worker died, or device removed |
| `SEQUENCE_LOSS` | sequence or frame indices missing from the device |
| `OVERLOAD_DROP` | raw queue reached capacity |
| `WRITER_ERROR` | storage rejected or failed a write |
| `UNKNOWN` | data missing with no attributable cause |

Every gap records `start_session_time_ns`, `end_session_time_ns` (null while open), cause, and estimated lost sample or frame count. On reconnect, the first datum sets `AFTER_RECONNECT` in its quality flags.
