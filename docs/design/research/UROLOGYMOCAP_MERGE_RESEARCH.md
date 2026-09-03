# UrologyMoCap merge research

Research date: **2026-09-01**  
Goal: Port validated pose/hand/face/kobayashi stack into CaptureSuite Phase D+ without forked semantics.

**Constraint:** Session-native paths under `processing/jobs/`; no pickle as canonical store.

---

## 1. Source inventory (UrologyMoCap)

| Asset | Path | CaptureSuite target |
|-------|------|---------------------|
| Body model catalog | `pose_models.py` | `pose/registry/body.yaml` |
| Hand manifest | `hand_model_manifest.yaml` | `pose/registry/hand.yaml` |
| Face runners | `face_models.py` | `pose/registry/face.yaml` |
| Canonical layout | `paper_landmarks.py` | shared lib or vendored |
| Fusion maps | `landmark_fusion.py` | `pose/fusion_config.json` in job |
| Offline infer | `infer_full_video_cache.py` | `jobs/pose_job.py` |
| Hand benchmark | `benchmark_hand_models.py` | research only → registry defaults |
| Kobayashi | `run_kobayashi_metrics_from_cache.py` | kinematics Tier B job |
| Realtime reference | `realtime_pipeline.py` | metric definition parity doc |

---

## 2. Port order

| Phase | Deliverable | Depends on |
|-------|-------------|------------|
| P0 | Shared `PaperLandmarks` schema in parquet | Phase D schema |
| P1 | MKV segment decoder in analysis | video loader |
| P2 | Body pose job (`rtmo_l` default) | P0, P1 |
| P3 | Hand native 21-pt optional output | hand bake-off on uncached clips |
| P4 | Fusion job mode | regional rankings frozen |
| P5 | Kinematics Tier A | P2 |
| P6 | Kobayashi Tier B | external `furs_ergonomic_metrics` license |
| P7 | Face registry (deferred D+) | face benchmark |

---

## 3. Cache format migration

| UrologyMoCap | CaptureSuite |
|--------------|--------------|
| `benchmark_output/hand_cache/**/*.pkl` | `pose/native/<model_id>/hand.parquet` |
| `model_cache/*.pkl` body | `pose/native/<model_id>/body.parquet` |
| Pickle `HandLandmarks` | Arrow columns + schema version |

One-time migration tool: `tools/migrate_urologymocap_cache.py` (implementation later).

---

## 4. Schema mapping

### `pose/landmarks.parquet` columns

| Column | Type | Notes |
|--------|------|-------|
| `session_time_ns` | int64 | Session clock |
| `frame_index` | int32 | Video frame |
| `joint_index` | int16 | 0–24 paper indices |
| `x`, `y`, `z` | float32 | Full-frame coords |
| `confidence` | float32 | |
| `source_model` | string | provenance |

### `pose/model_card.json`

From ANALYSIS.md — model_ids, versions, device, fusion map, benchmark date.

---

## 5. Registry defaults (interim)

| Role | Default | Source |
|------|---------|--------|
| Body teacher | `rtmo_l` | UrologyMoCap realtime + ANALYSIS.md |
| Hand (live) | `rtmw_balanced` | Prior benchmark — **revalidate** on 5714/6517/6612 |
| Hand (21-pt research) | bake-off winner | [POSE_HAND_TEACHER_POLICY.md](POSE_HAND_TEACHER_POLICY.md) |
| Fusion | regional map from `landmark_fusion.py` | freeze after benchmark |

---

## 6. Kobayashi / furs_ergonomic_metrics

| Question | Decision |
|----------|----------|
| License | Research vendoring — legal review required |
| CI | Optional extra `[analysis-kobayashi]` |
| Fallback | Tier A only if lib missing |

---

## 7. Metric parity

Document 1:1 mapping: `realtime_metrics.py` ↔ offline kinematics columns. Single source of truth for angle definitions ([KINEMATICS_PIPELINE.md](../KINEMATICS_PIPELINE.md)).

---

## 8. Dependencies (extras)

```
[analysis-pose-rtm]   # rtmlib, onnxruntime-gpu
[analysis-pose-yolo]  # ultralytics
[analysis-pose-mp]    # mediapipe
[analysis-hand]       # hand manifest runners
```

Missing extra fails **that model only**, not QC job.

---

## 9. References

- [ANALYSIS.md](../ANALYSIS.md)
- [UrologyMoCap/docs/INTEGRATION.md](../../../UrologyMoCap/docs/INTEGRATION.md)
- [POSE_HAND_TEACHER_POLICY.md](POSE_HAND_TEACHER_POLICY.md)
