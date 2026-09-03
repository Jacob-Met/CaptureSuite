# Data Collection Protocol — Radar-to-Kinematics ML

Protocol for acquiring ML-ready multimodal sessions: **radar + video** (minimum), with optional IMU, across a **scripted activity catalog**. Companion to [PROJECT_OUTLINE.md](../../../docs/PROJECT_OUTLINE.md) and [RADAR_PIPELINE.md](RADAR_PIPELINE.md).

---

## Purpose

Every session recorded under this protocol must support offline alignment of:

1. Radar FMCW frames (`radar.frame/1`)
2. Video timing sidecar (landmarks computed post-capture)
3. Activity labels via global checkpoints (not physical stream cuts)
4. Sync anchors for cross-modality offset estimation

Optional IMU improves teacher label quality but is not required for v1 capture.

---

## Session composition

### Required streams

| Stream | Schema | Rate (typical) | Notes |
|--------|--------|----------------|-------|
| FMCW radar | `radar.frame/1` | ~20 Hz | Raw `uint16_le_raw_interleaved`; see [RADAR_PIPELINE.md](RADAR_PIPELINE.md) |
| Camera video | MKV + timing sidecar | ~30 Hz | Pixels for post-capture pose only; not processed during `RECORDING` |

### Required metadata

| Artifact | Location | Purpose |
|----------|----------|---------|
| Checkpoints | Session checkpoint log | Activity block boundaries (`activity_id` in metadata) |
| Sync anchors | `events/sync_anchors.json` | Measured cross-modality alignment |
| Spatial preset | `arrays.json` + session notes | Radar placement; camera checklist |
| Subject/session IDs | Session manifest / project metadata | Cohort tracking, train/val splits |

### Optional streams

| Stream | When to include |
|--------|-----------------|
| Xsens IMU (torso + upper arm) | When hardware available; gold teacher for angular rates |
| Second radar board | Multi-view micro-Doppler; label **software coordinated** only |
| Doppler LTR11 | Separate research track; not mixed into v1 FMCW model without spec revision |

---

## Sync anchor protocol

Radar timestamps are **host-arrival QPC** with tens-of-ms jitter ([RADAR_PIPELINE.md](RADAR_PIPELINE.md)). Video uses its own clock. Do not assume sub-millisecond alignment without anchors.

### Before each session

1. Confirm all required sources are `READY` in preflight.
2. Place subject in documented orientation (facing camera, distance band per spatial preset).
3. Run one **practice sync anchor** and verify it appears in the timeline.

### Anchor types (use at least two per session)

| Mechanism | `metadata` suggestion | When |
|-----------|----------------------|------|
| `clap` | `{"type":"acoustic","mic":"optional"}` | Session start, after each major activity block |
| `led_flash` | `{"type":"visual","duration_ms":"50"}` | Session start/end |
| `sharp_tap` | `{"type":"vibration","target":"radar_mount"}` | If acoustic clap is unreliable in OR-like noise |

Record anchors via the Capture UI sync control or equivalent daemon RPC. Each anchor must list `modalitiesTargeted` including `radar` and `video` when both are active.

### Offline alignment (analysis)

Analysis jobs apply anchor-based offset estimation plus per-stream latency models. Results are recorded in `job_manifest.json` → `syncAnchorsApplied` and `analysisGrids`. See [ANALYSIS.md](ANALYSIS.md).

---

## Activity catalog

Activities are defined in the versioned catalog:

**Schema:** [`schemas/activity_catalog/activity_catalog.schema.json`](../../schemas/activity_catalog/activity_catalog.schema.json)  
**Instance:** [`schemas/activity_catalog/1.json`](../../schemas/activity_catalog/1.json)

### Checkpoint tagging convention

At the **start** of each activity block, create a checkpoint with metadata:

```json
{
  "activity_id": "elbow_flex_slow_L",
  "activity_catalog_version": "1",
  "side": "L",
  "repetitions_expected": 10,
  "operator_notes": ""
}
```

At block **end**, create a second checkpoint with the same `activity_id` and `"boundary": "end"`.

Checkpoints are global session metadata — they do not cut MCAP segments. Offline jobs slice by timestamp range between start/end checkpoints.

### Starter activity set (catalog v1)

The catalog defines ~20 blocks covering:

- Static baseline (standing, arms at sides)
- Slow / fast elbow flexion (L, R)
- Shoulder abduction arcs (L, R)
- Forward reach and hold
- Fine wrist / hand motion
- Compound surgical-like gestures (reach + retract)
- Walking in place
- Seated vs standing posture
- Garment variation blocks (document scrubs vs lead if applicable)

Each entry specifies duration, repetitions, joints exercised, and radar visibility notes.

---

## Spatial and anatomical preset (M10 precursor)

Before full 3D avatar UI (Milestone 10), record a **spatial preset checklist** in session notes or a attached JSON sidecar:

| Field | Example | Purpose |
|-------|---------|---------|
| `camera_height_m` | 1.4 | Rough extrinsics |
| `camera_distance_m` | 2.0 | Subject to lens |
| `subject_facing` | `camera` | Frame convention |
| `radar_board_ids` | from `arrays.json` | Which boards recorded |
| `radar_boresight_description` | `upper_torso, slight elevation` | LOS vs limbs |
| `subject_height_m` | 1.75 | Scale prior for angle lift |

Store radar array geometry from auto-snapshotted [`arrays.json`](../../schemas/session/jsonschema/radar_array.schema.json) at prepare time.

---

## Capture procedure (operator checklist)

1. Load activity catalog preset (or follow printed script).
2. Preflight all sources; resolve OVERLOAD/health warnings before Record.
3. **Session start:** sync anchor + checkpoint `activity_id: static_baseline`, `boundary: start`.
4. Perform static baseline (~30 s).
5. End baseline checkpoint; anchor optional.
6. For each catalog activity:
   - Start checkpoint + optional anchor
   - Perform scripted motion (count reps aloud or use metronome)
   - End checkpoint
7. **Session end:** sync anchor + final checkpoint.
8. Stop recording; verify package seals without fatal gaps on radar.

Target session length: **20–40 minutes** for full catalog v1 (adjust for pilot cohort).

---

## Quality gates

Sessions **fail ML inclusion** if any gate fails. Log exclusion reason in cohort spreadsheet.

### Session-level gates

| Gate | Criterion |
|------|-----------|
| Radar continuity | No `IFX_ERROR_FIFO_OVERFLOW` / OVERLOAD gaps in activity blocks |
| Video present | At least one camera MKV with timing sidecar |
| Anchors | ≥ 2 sync anchors recorded |
| Activity coverage | ≥ 80% of catalog activities attempted with valid start/end checkpoints |
| Metadata | `subject_id`, `session_id`, catalog version recorded |

### Per-activity gates (offline QC)

| Gate | Criterion |
|------|-----------|
| Pose detection rate | ≥ 85% frames with shoulder + elbow visible (Phase D QC) |
| Duration | Within ±20% of catalog `duration_s` |
| Repetitions | Within ±2 of `repetitions_expected` (operator count) |
| Radar SNR | Motion energy above floor in RD preview (Phase B QC figure) |

### Flags (include with warning)

- Brief pose occlusion (mask in kinematics job)
- Single missed anchor mid-session if start/end anchors valid
- Sim IMU substituted for real Xsens (teacher = video only)

---

## Subject and consent metadata

Record alongside session (project-level or session manifest extension):

| Field | Required |
|-------|----------|
| `subject_id` | Anonymous study ID |
| `session_id` | Unique per visit |
| `consent_version` | IRB protocol reference |
| `dominant_hand` | L / R |
| `garment` | scrubs / lead / other |
| `activity_catalog_version` | e.g. `"1"` |
| `capture_protocol_version` | `"1"` |

Do not store PHI in checkpoint names. Use structured metadata only.

---

## ML dataset criteria extension

Add to soak / reliability planning in [RELIABILITY_TESTING.md](../../docs/spec/RELIABILITY_TESTING.md):

- Cohort spreadsheet: subject × session × activities × pass/fail gates
- Export path for analysis: continuous export mode per [STORAGE_EXPORT.md](../../docs/spec/STORAGE_EXPORT.md)
- Transfer to Linux training box: `ml_bundle` directory + manifests only (video optional for eval replay)

---

## Related documents

- [PROJECT_OUTLINE.md](../../../docs/PROJECT_OUTLINE.md)
- [KINEMATICS_PIPELINE.md](KINEMATICS_PIPELINE.md)
- [ANALYSIS.md](ANALYSIS.md) — Phase D2/E alignment
- [RADAR_PIPELINE.md](RADAR_PIPELINE.md)
