# Extension modalities (brainstorm briefs)

Research date: **2026-09-01**  
Status: **Schema sketches** — not V1 hardware commitments.

Each entry defines: `StreamDescriptor`, preview kind, record schema, analysis family, worker isolation.

**Constraint:** New modalities must not require core session forks ([AGENTS.md](../../../AGENTS.md)).

---

## Summary table

| Modality | schema_id | preview | record schema | isolation | Priority |
|----------|-----------|---------|---------------|-----------|----------|
| Force plate | `force.frame/1` | TRACE_BLOCK / SCALAR_SERIES | `force.frame/1` protobuf | per_source | P2 |
| Audio (sync) | `audio.pcm/1` | TRACE_BLOCK | WAV segment + timing MCAP | shared | P2 |
| TTL / DAQ | `digital.event/1` | SCALAR_SERIES | event JSONL + optional MCAP | shared | P3 |
| Eye tracking | `gaze.sample/1` | IMAGE_THUMBNAIL + trace | `gaze.sample/1` | per_source | P3 |
| Optical mocap | `mocap.rigid/1` | ORIENTATION × N | `mocap.rigid/1` | per_source | P4 |
| Pressure mat | `pressure.grid/1` | MATRIX_2D | low-rate matrix | per_source | P4 |
| NIRS / SpO2 | `physio.trace/1` | TRACE_BLOCK | `physio.trace/1` | per_source | P4 |
| Depth camera | `depth.frame/1` | MATRIX_2D / thumbnail | depth MKV sibling | per_source | P3 |
| Instrument 6-DoF | `tool.pose/1` | ORIENTATION | `tool.pose/1` | per_source | P3 |
| Egocentric video | (reuse video) | IMAGE_THUMBNAIL | same as camera | per_source | P2 |

---

## Force plate / load cell

**Why:** `sim.custom.forceplate` reuses `emg.batch/1` — dishonest for COP/gait.

**Record:** `force.frame/1` — timestamp, Fx,Fy,Fz, Mx,My,Mz optional, calibrated flag.

**Preview:** vertical force trace + COP dot on 2D foot outline (research widget).

**Analysis:** stance phases, peak force, impulse, symmetry index.

**Migration:** deprecate sim force mapping to `emg.batch`.

---

## Audio (room mic)

**Why:** Clap sync anchors in [DATA_COLLECTION_PROTOCOL.md](../DATA_COLLECTION_PROTOCOL.md).

**Record:** FLAC/WAV segments + `audio.frame_timing/1` sidecar (mirror video pattern).

**Preview:** waveform TRACE_BLOCK, low rate.

**Analysis:** onset detection for sync only — **not** speech analytics in V1.

---

## TTL / DAQ digital lines

**Why:** Lab hardware sync without claiming radar HW sync.

**Record:** `events/ttl.jsonl` or MCAP event stream with hardware timestamp source enum.

**Preview:** digital trace SCALAR_SERIES.

**Analysis:** align to session clock via sync anchor editor.

---

## Eye tracking / gaze

**Why:** Surgical attention research; OpenFace adjacency in UrologyMoCap.

**Record:** `gaze.sample/1` — gaze point, pupil, validity.

**Privacy:** opt-in record; face blur in preview optional; see [ETHICS_AND_PRIVACY.md](ETHICS_AND_PRIVACY.md).

**Analysis:** fixation duration, saccade rate (provisional).

---

## Optical marker mocap (Qualisys-class)

**Why:** Alternative teacher for Phase D2 vs video pose.

**Record:** rigid bodies — position + quaternion per marker cluster.

**Analysis:** compare teacher agreement with video pose; higher trust for upper-limb angles.

---

## Pressure mat / seat

**Why:** Ergonomics with Kobayashi pipeline.

**Record:** low-rate pressure grid.

**Preview:** MATRIX_2D downsampled.

**Analysis:** contact area, center of pressure path.

---

## NIRS / SpO2 / physiologic

**Why:** OR context, slow traces.

**Record:** `physio.trace/1` with explicit units and calibrated bit.

**Analysis:** baseline drift, event-related averages (provisional).

---

## Depth camera (ToF/stereo)

**Why:** Spatial pose without RGB overlay issues.

**Record:** depth MKV or zstd frames; **storage cost** research required.

**Preview:** downsampled depth heatmap.

**Analysis:** point-cloud features deferred.

---

## Instrument tracking (EM / optical tool tip)

**Why:** Endoscopic tool path.

**Record:** `tool.pose/1` — 6-DoF pose stream.

**Analysis:** path length, velocity, workspace volume.

---

## Smart glasses / egocentric video

**Why:** Second viewpoint.

**Implementation:** Same [MODALITY_DEPTH_camera.md](MODALITY_DEPTH_camera.md) pipeline; logical slot `egocentric` in naming preset.

---

## Events: checkpoints and sync (cross-cutting)

Not a continuous stream — documented here for capture UX depth.

| Artifact | UX research |
|----------|-------------|
| Checkpoints | Protocol preset names; open-section indicator; spoken label field |
| Sync anchors | Wizard: clap / LED / manual offset; `modalities_targeted` picker |
| Annotations | Tagging for analysis scope |

See [DATA_COLLECTION_PROTOCOL.md](../DATA_COLLECTION_PROTOCOL.md), [REVIEW_AND_EXPORT_UX.md](REVIEW_AND_EXPORT_UX.md).

---

## References

- [ACQUISITION_PLUGIN_CONTRACT.md](ACQUISITION_PLUGIN_CONTRACT.md)
- [SESSION_FORMAT.md](../SESSION_FORMAT.md)
