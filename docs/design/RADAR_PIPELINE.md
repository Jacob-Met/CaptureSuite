# Radar Capture Pipeline

The radar record path for Milestone 6. Batching and rotation rules are fixed in [SESSION_FORMAT.md](SESSION_FORMAT.md), process model in [WORKER_HOST.md](WORKER_HOST.md); this document pins what a radar worker records, at what fidelity, and how loss and timing are reported.

Per-board measurements live in [adapters/](adapters/). This document holds the decisions those measurements produced.

## Milestone 6 covers the radar family, not one part number

[`IMPLEMENTATION_PLAN.md`](../../docs/spec/IMPLEMENTATION_PLAN.md) titles Milestone 6 "Radar + Multi-Radar" but names only the BGT60TR13C, because that was the only board assumed available. Two boards are now on the bench, and more may follow.

**Decision: Milestone 6 covers any supported radar board. Its exit criterion reads "every radar can be independently named, configured, and recorded, and validated multi-radar modes work" with no part number attached.**

This is the ground rule against hard-coding the app around one device, applied one level up from sources to milestones. The alternative — a milestone per part number — would multiply milestones without changing any architecture.

What generalizes: worker process model, discovery by stable identity, configuration snapshotting, timing and gap semantics, array membership, preview transport.

What does not generalize is the recorded payload, and that is a property of the instruments rather than a design choice. An FMCW board sweeps a frequency ramp and yields a sample block per antenna per chirp, from which range is recoverable. A Doppler board yields a single-antenna stream with no range information at all. Describing the second with the first's `num_chirps` / `num_samples` fields would populate them with values that mean nothing, which is the failure the honesty rules exist to prevent.

**Decision: one milestone, one worker pattern, one data schema per radar class.**

### Adding a third board

1. Run the spike per [VENDOR_SPIKE.md](VENDOR_SPIKE.md) and fill an adapter note under [adapters/](adapters/).
2. Reuse `radar.frame/1` if the board is FMCW and the existing fields describe it honestly. Otherwise register a new `data_schema_id` and its proto under `schemas/proto/capture/v1/data/`.
3. Add a worker binary or a device class inside an existing worker; the pipe contract, `SegmentSealed` handshake, and health reporting are unchanged.

No core session or storage code should need editing. If it does, that is a bug in the abstraction, not a reason to special-case the vendor.

## What gets recorded: FMCW boards (BGT60TR13C)

**Decision: record the raw interleaved ADC frame from `ifx_fmcw_get_next_raw_frame`, not the deinterleaved float cube from `ifx_fmcw_get_next_frame`.**

The SDK offers both. The float cube is what the Python wheel and every vendor example use, and what the initial spike measured. It is not, however, closer to the sensor — it is the raw frame after two mechanical transforms the SDK performs on the host:

| SDK function | What it does |
|---|---|
| `ifx_fmcw_convert_raw_data_to_float_array` | scales 12-bit integers to float |
| `ifx_fmcw_view_deinterleaved_frame` / `ifx_fmcw_deinterleave_raw_frame` | reorders chip transmission order into Rx × chirp × sample |

Both are published, deterministic, and reproducible offline from the raw frame. Neither filters, averages, or discards. So recording the cube stores a derived form of data we could have stored directly, and pays for it: a 12-bit reading that fits in 2 bytes occupies 4.

| Encoding | Bytes/frame (3 Rx × 32 chirps × 128 samples) | At 20 Hz |
|---|---|---|
| `float32_le` deinterleaved cube | 49 152 | ~3.4 GiB/h |
| `uint16_le` raw interleaved | 24 576 | ~1.7 GiB/h |

Rawer and half the size, so there is no trade to weigh. The cost is that a reader must deinterleave before the data means anything, which is why the configuration snapshot below is mandatory rather than advisory.

The raw path is reachable only from the C SDK. `ifxradarsdk` exposes `get_next_frame` and no raw equivalent, which settles the worker language question already implied by [`ARCHITECTURE.md`](../../docs/spec/ARCHITECTURE.md): the radar worker is C++ against `radar_sdk.lib`.

### Field mapping onto `radar.frame/1`

The schema was registered at Milestone 1 and needs no revision.

| Field | Value |
|---|---|
| `sample_encoding` | `uint16_le_raw_interleaved` |
| `payload` | the frame exactly as `ifx_Fmcw_Raw_Frame_t.samples` delivered it |
| `num_rx`, `num_chirps`, `num_samples` | the configured geometry, so a reader can size the deinterleave |
| `configuration_hash` | key into the configuration snapshot in `stream.json` |
| `frame_index` | worker-side monotonic counter; gaps are meaningful |

`sample_encoding` is a free-text field, so adding a value is forward compatible with anything already written.

Samples are **real-valued**, not complex I/Q. The BGT60TR13C digitizes a real IF signal. A reader that pairs adjacent samples into complex values gets nonsense, so the encoding string says `raw_interleaved` rather than anything suggesting pairing.

One MCAP message per frame, per the radar row of the batching table in [SESSION_FORMAT.md](SESSION_FORMAT.md). At these rates a segment rotates on the 300 s time threshold (~140 MiB) well before the 512 MiB size threshold.

## Configuration is part of the recording

The app drives emission, not just reception: it sets the frequency sweep, transmit power, antenna selection, filtering, and timing before each session rather than accepting a device default. A recorded frame is therefore uninterpretable without knowing what was transmitted to produce it.

**Decision: `stream.json` carries a full configuration snapshot, hashed into `configuration_hash` on every frame. A frame whose configuration is unknown is a defect, not a degraded case.**

The snapshot records the requested chirp parameters, the values the device actually applied (`ifx_fmcw_get_acquisition_sequence` — the SDK rounds gain and cutoff to supported steps), the derived metrics the SDK reports, and the register dump from `save_register_file`. Board UUID, SDK version, and firmware version go in `source.json` as provenance.

Recording requested-versus-applied separately matters because the difference is silent otherwise. Asking for 33 dB of gain and getting the nearest supported step is normal; discovering years later that you cannot tell which happened is not.

## Timing is host-arrival, and the uncertainty is milliseconds

No device-native frame timestamp is exposed. The worker stamps QPC when the frame is returned, and that is the only clock available.

Two mechanisms put real error on that stamp. Frames cross USB in slices that are not frame-aligned, so the SDK explicitly notes consecutive calls may return immediately when a slice carried more than one frame. Measured pull intervals on the bench were p50 45.9 ms against a 50 ms configured period, with p95 at 61 ms.

**Decision: radar `timestamp_uncertainty_ns` is on the order of tens of milliseconds and is measured per configuration, not assumed.**

This corrects the 0.5 ms placeholder in the [TIMING.md](TIMING.md) uncertainty budget, which predates hardware and assumed a frame-trigger-to-transfer path that the SDK does not expose. Per that document's own rule, a wrong small number is worse than an honest large one.

The consequence is scope, not a defect: radar aligns with other modalities at millisecond scale, and any analysis needing tighter alignment must use measured sync anchors. There is no hardware trigger or external sync input in the radar SDK, so the anchor has to be a physical event several sensors observe together, recorded in `events/sync_anchors.json`. That is a measurement of the offset rather than elimination of it.

## Loss is loud

The sensor FIFO overflows if the host does not drain it fast enough. The SDK surfaces this as `IFX_ERROR_FIFO_OVERFLOW` and **stops the sensor state machine** — it does not skip frames and continue.

This is the behavior ground rule 8 wants, so the worker must not soften it:

| Condition | Response |
|---|---|
| `IFX_ERROR_FIFO_OVERFLOW` | journal an `OVERLOAD` gap, mark the source failed, keep the session recording |
| `IFX_ERROR_COMMUNICATION_ERROR` | treat as disconnect; the restart policy in [STATE_MACHINES.md](STATE_MACHINES.md) applies |
| `IFX_ERROR_TIMEOUT` | no data yet; not an error, do not journal |
| `frame_index` discontinuity | set `SEQUENCE_DISCONTINUITY` on the timing header |

Recovering silently from an overflow by restarting acquisition would hide exactly the condition an operator needs to know about, because it means the chosen configuration exceeds what the host can sustain.

## Preview is derived and droppable

The range-Doppler map shown in the UI is computed in the worker from the frame it just recorded, downsampled to the `MATRIX_2D` contract size, and sent latest-wins. It is never written to the session.

Nothing derived is recorded. Range profiles, Doppler maps, MTI output, and presence decisions are all recomputable from the raw frames, and `processing/` is reserved for derived artifacts at Milestone 12. Preview loss is normal and unreported; record loss is a defect and always reported.

Note from the spike: a naive FFT magnitude profile is dominated by DC and antenna leakage, with the peak pinned at bin 0. Preview needs MTI or a range-Doppler transform to show motion at all. That is a preview-quality matter only — it has no bearing on what is recorded.

## What gets recorded: Doppler boards (BGT60LTR11AIP)

One transmit and one receive antenna, 8-bit ADC, no chirp sweep, therefore no range. `radar.frame/1` does not describe it, so it gets `radar.doppler/1` when the worker is built. Its preview is a motion trace, not a matrix.

The board is not named in the Milestone 6 plan and is a deliberate scope addition. See [adapters/infineon_bgt60ltr11aip.md](adapters/infineon_bgt60ltr11aip.md).

## Non-goals for v1

- **No hardware synchronization between radars.** The SDK exposes no trigger input or sync mode. Software-coordinated start is not hardware sync and will not be described as such.
- **No multi-radar interference claim** as a synchronization story. A first concurrent soak on this host (TR13C 20 Hz + LTR11 ~7.8 Hz, 15 s) showed stable rates, zero SDK errors, and no TR13C energy-CV spike — see [adapters/infineon_bgt60tr13c.md](adapters/infineon_bgt60tr13c.md) §8 and `tools/vendor_spike/spike_dual_radar_interference.py`. That is a throughput/RF-smoke result only, not hardware sync.
- **No lossy sample encoding.** Quantizing below the ADC's native width buys storage we do not need to save.
- **No reconnect heroics.** A board that disconnects mid-session follows the standard restart policy and then fails visibly.
