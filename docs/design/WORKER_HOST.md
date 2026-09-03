# Worker Host and Process Model

How source workers are spawned, supervised, and killed, and who writes raw bytes. Pins the decisions Milestone 5 onward depends on. Transport and framing are in [PROTOCOL.md](PROTOCOL.md); lifecycle states are in [STATE_MACHINES.md](STATE_MACHINES.md).

Milestone 4 deliberately runs sources **in-process** inside `capture_daemon` (simulator plus Media Foundation cameras). That was a scope decision, not a change of architecture. This document defines the out-of-process target so the in-process code can be lifted without redesign.

`daemon` includes `WorkerHost` (`worker_host.hpp`) that implements the spawn sequence below against a job object, plus Discover/Connect/Start/Stop helpers and `drain_events` for `PreviewFrame` / `SegmentSealed` / `HealthSnapshot` / `OverloadEvent`. `CameraWorkerBridge` spawns `capture_worker_camera` per camera source when the worker exe and GStreamer are present (auto), or when `CAPTURE_USE_CAMERA_WORKER=1`. Set `CAPTURE_USE_CAMERA_WORKER=0` to force in-process Media Foundation (timing-only). Override the exe with `CAPTURE_CAMERA_WORKER_EXE`. `SegmentSealed` updates `integrity.json` through `SessionPackage::record_external_segment`. `workers/stub` remains Hello/Identify-only for host tests.

## Process granularity

The obvious options conflict: one process per source gives maximum isolation, one process per plugin matches how vendor SDKs actually behave. Many SDKs (Delsys base station, Xsens receiver) are effectively process-global singletons and cannot be initialized twice, so per-source processes are impossible for them. Cameras are independent devices with crash-prone drivers, where per-source isolation is genuinely valuable.

**Decision: the plugin declares its isolation mode; the daemon honors it.**

| Mode | Meaning | Used by |
|---|---|---|
| `shared` | one worker process hosts every source of that plugin | Delsys, Xsens, any SDK-singleton vendor |
| `per_source` | one worker process per source | cameras, radar boards |

Declared in `SourceManifest.capabilities["isolation"]` at `Identify` time. Unknown or absent means `shared`, because that is the safe assumption for an unfamiliar SDK.

This satisfies ground rule 8 where it is achievable and states plainly where it is not: in `shared` mode a crash affects every source in that process, and each one gets its own `DISCONNECT` gap. The daemon never pretends otherwise.

## Spawn sequence

The daemon is the pipe **server**; the worker connects as a client. Server-first removes the race where a worker starts before its endpoint exists.

1. Daemon creates the worker pipe `\\.\pipe\capturesuite.{instance_id}.worker.{worker_id}` with the DACL from [PROTOCOL.md](PROTOCOL.md)
2. Daemon creates the process with `CREATE_SUSPENDED`
3. Daemon calls `AssignProcessToJobObject`
4. Daemon calls `ResumeThread`
5. Worker connects to the pipe and sends `Hello`
6. Daemon replies `HelloAck`, then `Identify`

Steps 2 through 4 are ordered deliberately. Assigning the job before the process runs any user code is what guarantees no worker can outlive the daemon, even if it crashes during startup. Spawning unsuspended and assigning afterwards leaves a window where a worker escapes the job.

Worker command line: `--pipe <name> --worker-id <id> --plugin <plugin_id>`. Nothing else. No configuration on the command line, because configuration is versioned schema content and belongs in `ApplyConfig` where it can be validated and snapshotted.

On Windows the control pipe is a synchronous handle: the worker main loop is the sole writer. Preview, health, and `SegmentSealed` frames are queued (preview latest-wins) and flushed from that loop so pipeline threads never block behind a pending `ReadFile`. The daemon proxies `GetConfigSchema` / `ApplyConfig` for cameras into the worker; encoder preference and preview rate are applied at the next `Start`.

## Job object

One job object per daemon instance, created before any worker spawns, with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. Every worker joins it.

This is the orphan-prevention mechanism: if the daemon dies for any reason, including `TerminateProcess`, Windows tears down every worker. Without it a crashed daemon leaves processes holding vendor device handles, and the next daemon start cannot open the hardware.

The daemon does **not** set memory or CPU limits on the job. Throttling a capture worker to protect the host trades data loss for tidiness, which is the wrong trade for this application.

## Peer verification

Both directions verify identity before trusting a connection:

- The daemon calls `GetNamedPipeClientProcessId`, opens the process token, and compares the user SID to its own. A mismatch is rejected and logged at `error`.
- A worker only accepts the pipe name passed on its command line by its parent.

## Supervision and liveness

Heartbeat is the `HealthSnapshot` event at 1 Hz — a worker producing health is by definition alive, so there is no separate ping. Three consecutive missed intervals (3 s) declares the worker dead.

Death during recording follows the restart policy already fixed in [STATE_MACHINES.md](STATE_MACHINES.md): journal the last received datum time, open a `DISCONNECT` gap, restart up to 3 times with 1 s / 2 s / 4 s backoff, re-apply the stored configuration snapshot, resume into a **new segment**, and after 3 failures mark the source `FAILED`, leave the gap open, and keep the session recording.

Resuming into a new segment rather than reopening the old one matters: the old tail is whatever the crash left behind, and recovery is entitled to truncate it.

## Who writes raw bytes

**Decision: workers write their own raw stream files directly to the session package. Metadata files stay single-writer in the daemon.**

The topology in [PROTOCOL.md](PROTOCOL.md) already implies this, and it is what keeps a 20 MB/s video stream from being copied through the control pipe.

| Artifact | Writer |
|---|---|
| MCAP segments, video segments, timing sidecars | owning worker |
| `manifest.json`, `integrity.json`, `clock_mappings.json`, `events/*` | daemon |
| `journal.sqlite` | daemon |
| `health/gaps.jsonl`, `health/overloads.jsonl` | daemon |

Consequence: `integrity.json` and the journal are updated by the daemon on the worker's report, not by the worker. Two processes appending to one metadata file is how you get a corrupt manifest, and the atomic-rename rule in [SESSION_FORMAT.md](SESSION_FORMAT.md) assumes a single writer.

### Segment sealing handshake

At every rotation the worker seals its own segment and reports it. The worker computes the hash because it already holds the bytes, and hashing in the daemon would mean reading the file back.

Worker to daemon, `SegmentSealed`: `source_id`, `stream_id`, package-relative `path`, `size_bytes`, `hash_blake3_hex`, `start_session_time_ns`, `end_session_time_ns`, `actual_count`, `segment_index`.

Daemon on receipt: append the `integrity.json` entry with `status=sealed`, journal `SEGMENT_ROTATED`, then acknowledge. The worker does not wait for the acknowledgement before opening the next segment, because blocking acquisition on a metadata write is exactly the coupling this split exists to avoid.

An unreported sealed segment is not lost data: recovery finds it on disk, classifies it as a candidate tail, and validates it. Losing the report costs a verification pass, not bytes.

## Shutdown

Ordered, from [PROTOCOL.md](PROTOCOL.md): stop accepting requests, `Stop` all recording sources, flush and close writers, journal finalization, `Shutdown` each worker, wait the 5 s grace period, `TerminateProcess` stragglers, close the job object.

A worker that ignores `Shutdown` is terminated. It has already flushed by that point in the sequence, so termination costs nothing, and waiting indefinitely for a wedged vendor SDK is not an acceptable alternative.

## What this does not cover

Vendor-specific discovery, pairing, and timestamp semantics are per-adapter and require the [VENDOR_SPIKE.md](VENDOR_SPIKE.md) results on real hardware. They are written into `docs/design/adapters/<vendor>.md` during Milestones 6 through 8, not guessed here.
