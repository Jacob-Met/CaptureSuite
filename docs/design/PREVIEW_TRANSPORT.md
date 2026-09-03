# Preview Transport

Preview is the one path in the system allowed to lose data. This document pins how preview frames reach the UI today, the shared-memory design they move to, and the measured trigger for the switch.

Guarantees, unchanged by transport: previews are droppable, latest-wins, never journaled, and never able to back-pressure acquisition. Preview reliability is deliberately not capture reliability.

## Two transports, one payload

**Decision: both transports carry byte-identical serialized `capture.v1.PreviewFrame` payloads.**

The shared-memory slot holds exactly what the pipe frame's payload holds. The UI's decode and render path therefore does not change at cutover — only where the bytes came from. Defining a second, shm-specific layout would mean two parsers, two schema-evolution stories, and a UI that behaves subtly differently depending on transport.

### Current: pipe-carried events

After `SubscribeStatus(include_preview=true)`, the daemon pushes `PreviewFrame` as unsolicited events with `correlation_id = 0`, applying latest-wins in the daemon's per-source slot before the send. Implemented and in use since Milestone 4.

This is sufficient today and the numbers say so. A 480-pixel-longest-edge JPEG thumbnail at quality 70 is roughly 25 to 40 KB; at 15 Hz that is about 0.5 MB/s per camera, so four cameras plus simulated modalities sit near 2 MB/s against an 8 MiB per-frame ceiling. Building the shared-memory ring before this hurts would be optimizing a path that is not the bottleneck.

### Target: shared-memory ring

Required once preview payloads grow past what a control pipe should carry — most obviously full-resolution uncompressed preview, where a single 1080p RGB frame is about 6 MB and per-frame pipe delivery stops being reasonable.

## Cutover criteria

Cut over when any of these is measured, not when it is suspected. The benchmark lives in `tests/perf/preview_load.py` and drives synthetic previews at contract rates and sizes.

| Trigger | Threshold |
|---|---|
| Aggregate preview throughput on the control pipe | above 8 MB/s sustained |
| Control RPC p99 latency while previews stream | above 50 ms |
| Daemon-side preview drop rate with CPU headroom still available | above 20 percent, indicating transport-bound rather than compute-bound |
| Any requirement for uncompressed or full-resolution preview | immediate, no measurement needed |

The third row is the one worth stating explicitly: dropping previews because the compute is saturated is expected and fine, while dropping them because the transport is saturated is the condition shared memory fixes. Distinguishing the two is what keeps this from being a guess.

## Segment layout

One mapping per source, created by the producing worker, opened read-only by any number of UI clients.

Name: the `shm_key` already carried in `PreviewDescriptor`, of the form `Local\capturesuite.{instance_id}.preview.{source_id}`. Size: 128-byte header plus `ring_slot_count` (always 3) slots of 64-byte slot header plus `max_payload_bytes`.

### Header

| Offset | Size | Field | Notes |
|---|---|---|---|
| 0 | 4 | `magic` | ASCII `CSPV` |
| 4 | 4 | `layout_version` | starts at 1 |
| 8 | 4 | `slot_count` | 3 |
| 12 | 4 | `payload_capacity` | bytes per slot |
| 16 | 4 | `epoch` | incremented by each new producer instance |
| 20 | 4 | `producer_pid` | diagnostics only |
| 24 | 8 | `write_index` | atomic, monotonic; slot is `write_index % slot_count` |
| 32 | 8 | `frames_published` | atomic |
| 40 | 8 | `frames_dropped` | atomic, producer-side drops |
| 48 | 80 | reserved | zero-filled, for forward compatibility |

### Slot header

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | `seq` — atomic; odd means a write is in progress |
| 4 | 4 | `payload_len` |
| 8 | 8 | `frame_sequence` — the producer's global frame counter |
| 16 | 8 | `session_time_ns` |
| 24 | 40 | reserved |

## Publish and read protocol

A seqlock, because the alternative — a mutex shared with an untrusted, crash-prone reader — lets a UI crash inside the critical section stall a capture worker. A reader that dies mid-read costs the writer nothing here.

Writer, per frame:

1. Target slot `(write_index + 1) % slot_count`
2. Increment that slot's `seq` to an odd value (release)
3. Write `payload_len`, `frame_sequence`, `session_time_ns`, then the payload
4. Increment `seq` again to an even value (release)
5. Store `write_index + 1` (release), and increment `frames_published`

The writer never checks whether a reader consumed the slot it is about to overwrite. That is the latest-wins guarantee and the reason it cannot block.

Reader, per redraw:

1. Load `write_index` (acquire); if unchanged since last redraw, nothing new, done
2. Read the slot's `seq`; if odd, abandon this frame and try next redraw
3. Copy `payload_len` bytes out
4. Re-read `seq`; if it changed, discard the copy and retry or abandon

Abandoning rather than spinning is correct: at 15 to 30 Hz the next frame is milliseconds away, and a preview frame is worth no CPU spent contending for it.

Gaps in `frame_sequence` are how the reader computes `dropped_since_last`. They are expected, and reported rather than hidden.

## Notification

**Decision: readers poll at their own redraw rate. There is no event object.**

The UI is already a fixed-rate renderer and latest-wins semantics mean it only ever wants the newest frame, so an auto-reset event would add a kernel transition per frame to deliver information the reader gets for free from one atomic load. Polling also degrades correctly: a UI that renders at 10 Hz simply sees fewer frames instead of building a backlog.

## Lifecycle and safety

- Created by the producing worker when the source opens, with the same explicit DACL as the pipes in [PROTOCOL.md](PROTOCOL.md). `NULL` DACLs are forbidden here too.
- The name is stable per `source_id`, so a restarted worker recreates the same name with an incremented `epoch`. A reader observing an `epoch` change remaps, because slot contents from the previous producer are not valid across a restart.
- Readers must tolerate a missing mapping at any time and fall back to showing the source as having no preview. A source without preview is a display state, never an error.
- Readers open the mapping with `FILE_MAP_READ` only. A UI cannot corrupt a producer's ring, which matters because the UI is untrusted.
- `layout_version` is checked on attach; an unrecognized version means the reader declines to attach rather than misparsing.

## Migration

The `PreviewDescriptor` fields needed for shared memory (`shm_key`, `ring_slot_count`, `max_payload_bytes`) already exist and are already populated, so the switch adds no schema change. During migration a descriptor may advertise both transports; a UI that cannot attach to the mapping falls back to pipe events, which lets the cutover happen per source rather than as one flag day.
