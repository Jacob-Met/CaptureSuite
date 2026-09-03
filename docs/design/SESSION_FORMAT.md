# Session Format

The canonical session package. Directly reopenable by the app; export is for interoperable copies, never a requirement for using the data.

## Package layout

```text
<session_name>.mmsession/
  manifest.json                 # schema version, identity, T0, state
  journal.sqlite                # append-only operational journal
  integrity.json                # per-file hash, size, counts, status
  events/
    checkpoints.json
    annotations.json
    sync_anchors.json
  clock_mappings.json
  arrays.json                   # RadarArray / DeviceArray definitions
  sources/
    <source_id>/
      source.json               # SourceInstance + PhysicalDevice snapshot
      sensors.json              # multi-sensor systems only
      streams/
        <stream_id>/
          stream.json           # StreamDescriptor
          segments/
            000000.mcap
            000001.mcap
          # video streams instead contain:
          #   segments/000000.mkv  + segments/000000.timing.mcap
      health/
        gaps.jsonl
        overloads.jsonl
  mappings/                     # anatomical and spatial snapshots
  calibrations/
  presets_snapshot/             # full preset content, not references
  processing/                   # empty until Milestone 12
  logs/
  recovery/                     # intent records, repair reports
```

A session may sit inside a project folder carrying Project / Participant / Visit metadata, but the session always embeds the full identity chain so a moved package stays self-describing.

## manifest.json

Required fields:

| Field | Notes |
|---|---|
| `session_schema_version` | semver, starts at `1.0.0` |
| `session_id` | GUID |
| `state` | `preparing`, `recording`, `finalized`, `finalized_recovered`, `failed` |
| `project` / `participant` / `visit` | identity chain; participant and visit may be null |
| `t0_qpc_ticks`, `qpc_frequency` | monotonic base |
| `t0_wall_utc`, `t0_uncertainty_ns` | wall anchor and honest uncertainty |
| `created_utc`, `finalized_utc` | |
| `app_version`, `daemon_version` | |
| `plugin_versions` | map of plugin_id to version |
| `sdk_versions`, `firmware_versions` | provenance |
| `source_ids` | sources participating in this session |

Written atomically: serialize to `manifest.json.tmp`, flush, then `MoveFileEx` with `MOVEFILE_REPLACE_EXISTING`. Same rule for every JSON metadata file.

Unknown fields encountered on read are preserved and written back unchanged. That is what makes an older reader safe against a newer writer.

## Numeric and structured streams: MCAP

One MCAP file per segment per stream.

### Self-describing schemas

Each stream registers exactly one MCAP channel. The channel's schema record carries:

- `name` = the `data_schema_id`, for example `emg.batch/1`
- `encoding` = `protobuf`
- `data` = the serialized `FileDescriptorSet` for that message, taken from `capture_v1.desc`

This means a session opens in any MCAP-aware tool without CaptureSuite installed.

### Message time fields

- `log_time` = `session_time_ns` of the first datum in the batch
- `publish_time` = `host_arrival_ns` of the first datum in the batch

### Batching

Never one message per sample. Each batch message contains a `TimingHeader` for its first datum plus the shape needed to reconstruct the rest.

| Stream class | Batch trigger | Payload shape |
|---|---|---|
| EMG and other high-rate sampled | 50 ms or 4096 samples | channel list plus `[channels x samples]` matrix, plus per-batch quality flags |
| IMU and structured | 100 ms | synchronized multi-sensor frames |
| Radar array frames | 1 frame | raw frame plus configuration hash reference |
| Video timing sidecar | per frame | one record per frame, index and timestamps only |

Compression: zstd level 1 for numeric chunks. No compression for video sidecars or already-compressed payloads.

Flush policy: writers flush to the OS every 1 s and at every rotation. No `FlushFileBuffers` per batch, because the journal plus segment rotation already bound worst-case loss.

## Video streams

Crash-tolerant segmented recording. Encoded segments in Matroska (`.mkv`) because it tolerates truncation far better than MP4, with a per-frame timing sidecar in MCAP alongside.

Pose overlays are never burned into source video. Derived visualizations belong in `processing/`.

Rewrapping to MP4 happens only on export.

## Segment rotation

Rotate when either threshold is hit:

- 512 MiB, or
- 300 s of session time

Rotation procedure, in order:

1. Finish the in-progress batch
2. Close and flush the current segment
3. Compute the segment hash (see below) and append its entry to `integrity.json`
4. Journal `SEGMENT_ROTATED` with the segment path, byte size, and exact session time range
5. Open the next segment

Because each closed segment is hashed and journaled at rotation, a crash can only ever leave the single tail segment unverified.

## Integrity manifest

`integrity.json` holds one entry per output file:

| Field | Notes |
|---|---|
| `path` | relative to package root |
| `size_bytes` | |
| `hash` | BLAKE3, hex; chosen for speed on large files |
| `source_id`, `stream_id` | provenance |
| `start_session_time_ns`, `end_session_time_ns` | exact range |
| `expected_count`, `actual_count` | samples or frames |
| `status` | `sealed`, `open`, `truncated_recovered`, `unverified` |

Hashing is incremental at rotation, never a single pass at finalize. Finalize hashes only the tail segment.

## Journal

SQLite with `journal_mode=WAL` and `synchronous=FULL`. Event rate is low, so durability is worth the cost.

Single append-only `events` table: `id`, `session_time_ns`, `wall_utc`, `kind`, `source_id`, `stream_id`, `payload_json`.

Event kinds: `SESSION_CREATED`, `SESSION_STARTED`, `SOURCE_STARTED`, `SOURCE_STOPPED`, `WORKER_FAILED`, `WORKER_RESTARTED`, `RECONNECTED`, `CHECKPOINT_CREATED`, `CHECKPOINT_EDITED`, `ANNOTATION`, `SYNC_ANCHOR`, `CONFIG_CHANGED`, `SEGMENT_ROTATED`, `GAP_OPENED`, `GAP_CLOSED`, `OVERLOAD`, `TIME_DISCONTINUITY`, `DISK_WARNING`, `DISK_CRITICAL`, `WRITE_BLOCKED`, `WRITE_RESUMED`, `ARM_FAILED`, `RECOVERY_INTENT`, `RECOVERY_COMPLETE`, `PARTIAL_FINALIZE`, `FINALIZED`.

Checkpoint edits append `CHECKPOINT_EDITED` rows rather than mutating history. Timestamp moves require a reason string and preserve the original.

## Checkpoints and section derivation

Checkpoint timestamp is captured on the daemon the instant the command arrives, before any naming. A checkpoint closes and names the section preceding it.

Section derivation is a pure function of the checkpoint list plus session start and stop:

- No checkpoints: one section spanning the whole session
- Checkpoint at exactly `t=0`: produces a zero-length section, retained rather than discarded, because deleting it would silently rewrite operator intent
- After the last checkpoint: a trailing section to session end, named `Trailing section` until the operator names it
- A source not recording for a whole section: the section still exists; per-source coverage is derived from segments and gaps, not from section boundaries

Sync anchors never create section boundaries. Annotations never create section boundaries.

## Migrations

`schemas/session/migrations/registry.py` maps each `session_schema_version` to an ordered list of upgrade steps.

Rules:

- Upgrade on open writes an upgraded copy; the original package is never mutated in place
- Every step is independently testable and has a fixture
- `schemas/session/golden/` holds a frozen package per released schema version, and CI opens all of them with current code
- A reader encountering a *newer* major version refuses to open rather than guessing
