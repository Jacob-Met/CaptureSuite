# UI Data Contract

What the UI is guaranteed to receive, independent of layout. Validated against the interactive prototype in `prototypes/ui_mockup/`, which exercised every payload kind and health field below.

Layout is deliberately not specified here. The contract exists so the layout can change without touching the protocol.

## Chosen layout direction

The prototype settled the direction: a permanent source rail plus a swappable centre view offering timeline, single-source focus, and card grid. Because all three views consume the same data, the contract below must satisfy the most demanding of them, which is the card grid.

## Preview payload kinds

Preview is non-critical, reduced-rate, latest-wins, and droppable. It never back-pressures the raw path.

| Kind | Used by | Payload | Max size | Max rate |
|---|---|---|---|---|
| `IMAGE_THUMBNAIL` | camera | JPEG or raw RGB, longest edge 480 px | 256 KB | 15 Hz |
| `TRACE_SINGLE` | IMU default, any single channel | one channel, 256 decimated points | 4 KB | 20 Hz |
| `TRACE_BLOCK` | EMG, multi-channel IMU | up to 16 channels, 256 points each | 32 KB | 20 Hz |
| `ORIENTATION` | Xsens | one quaternion plus accel and gyro magnitude | 64 B | 30 Hz |
| `VECTOR_PROFILE` | radar range profile | up to 256 float bins | 1 KB | 15 Hz |
| `MATRIX_2D` | radar range-Doppler | up to 128 x 64 float | 32 KB | 5 Hz |
| `SCALAR_SERIES` | rail sparklines, motion energy | 64 points | 512 B | 10 Hz |

Rules that fell out of prototyping:

- **A multi-sensor source previews one selected channel by default.** The Xsens preview streams a single raw trace from one operator-chosen sensor, not all seven. This keeps the shared-memory payload small and is sufficient proof of life. All sensors are still recorded in full.
- **Decimation is the worker's job**, not the UI's. The worker sends 256 points regardless of native rate.
- **Preview selection is per source** (`preview_channel`, layout mode) and belongs in the workspace preset so it survives restarts.
- `PreviewDescriptor` declares kind, max payload bytes, ring slot count (3), and update rate so the UI can allocate without guessing.
- **ORIENTATION (cube) and MATRIX_2D (heatmap) stay the default painters.** The UI may offer an optional graph rendering of the same payload; that is display-only and does not change the wire kind.

## Health fields

Emitted at 1 Hz and immediately on change. These exist to answer the five proof-of-life questions from [`MASTER_SPEC.md`](../../docs/spec/MASTER_SPEC.md).

| Field | Answers |
|---|---|
| `lifecycle_state` | where the source is in its machine |
| `health` (`OK`/`WARNING`/`ERROR`) | is anything obviously wrong |
| `connected` | is it connected |
| `data_arriving` | is data arriving now |
| `measured_rate_hz`, `expected_rate_hz` | is it arriving at roughly the right rate |
| `dropped_count`, `dropped_last_10s` | is anything being lost |
| `write_ok`, `current_segment` | is raw data actually being written |
| `open_gap` (cause, start, duration) | is there a hole right now |
| `gap_count` | how many holes so far |
| `last_error` | what went wrong most recently |
| `battery_percent`, `signal_quality` | optional, per-source, null when unsupported |

`write_ok` is deliberately **per source**, not one global storage indicator. Every card in `UI_UX.md` shows its own disk and write health, and a single global flag cannot express one stream failing while others succeed.

## Session and event data

The UI additionally consumes: session state, elapsed session time, T0 and wall anchor, the checkpoint list with original and effective timestamps, annotations, sync anchors, per-lane segment and gap lists for the timeline, the alert list with levels and acknowledgement state, disk status, and the preflight check list with per-check overridable flags.

## Interaction guarantees

Behaviors the UI may rely on, all enforced by the daemon:

- A checkpoint command returns the assigned timestamp immediately; naming is a later call
- `RequestStop` returns a confirmation token; `Stop` without it is rejected
- Config and selection changes are rejected while recording
- A source failing produces an `Alert` plus a `GapEvent`, and never affects other sources
- No event ever causes the UI to change view; navigation is always the operator's choice. Auto-focus on fault is a client-side preference, off by default, because jumping the view mid-recording hides healthy sources.

## Milestone 4 transport note

The production UI in `desktop/capture_desktop/` consumes the same payload kinds above. Until shared-memory preview lands, frames arrive as `MESSAGE_TYPE_PREVIEW_FRAME` on the subscribed control connection. Semantics (latest-wins, droppable, worker/daemon decimation) are unchanged, and the shared-memory ring carries byte-identical payloads, so no UI parsing changes at cutover. See [PREVIEW_TRANSPORT.md](PREVIEW_TRANSPORT.md).

Real cameras expose `IMAGE_THUMBNAIL`. When the out-of-process GStreamer worker is active (`camera.gstreamer`, `record_mode=mkv_h264`), preview and MKV record share one device open. The in-process Media Foundation fallback (`camera.mf`, `record_mode=timing_only`) still records per-frame timing only; the UI surfaces that as an explicit caption, not a silent omission. See [VIDEO_PIPELINE.md](VIDEO_PIPELINE.md).

Source configuration forms are generated from worker-published JSON Schema, per [CONFIGURATION_UI.md](CONFIGURATION_UI.md). The UI contains no vendor-specific form code.

## Non-goals

This document says nothing about visual design, card layout, drag and reorder, pop-out windows, multi-monitor arrangement, theming, sounds, the 3D anatomy mapper, or the radar spatial editor. Layout direction was settled by the mockup; Milestone 10 concerns remain free to change without a protocol revision.
