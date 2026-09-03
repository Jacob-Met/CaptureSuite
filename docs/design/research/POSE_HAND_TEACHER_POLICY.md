# Pose, hand, and teacher selection policy

Research date: **2026-09-01**  
Status: **Policy locked for CaptureSuite**; hand bake-off continues in UrologyMoCap on uncached clips.

**Constraints:** Sealed raw video only; overlay salvage legacy-only ([UrologyMoCap/docs/OVERLAY_STRIP_RESEARCH.md](../../../UrologyMoCap/docs/OVERLAY_STRIP_RESEARCH.md)); no overlay-inpaint investment in CaptureSuite product path.

---

## 1. Video source hierarchy

| Priority | Source | Use |
|----------|--------|-----|
| 1 | Sealed MKV from `.mmsession` | All CaptureSuite pose/kinematics |
| 2 | UrologyMoCap legacy clips | Offline benchmark only |
| 3 | `_cleaned` / inpaint salvage | **Disallowed** for CaptureSuite teacher labels |

Capture UI must never imply cleaned video is equivalent to raw.

---

## 2. Body teacher selection

| Criterion | Weight | Measurement |
|-----------|--------|-------------|
| Detection rate | high | % frames with ≥N joints |
| Mean confidence | medium | shoulders/wrists |
| Temporal jitter | high | px RMS on key joints |
| Throughput | medium | sec/frame on lab GPU |
| Surgical failure modes | high | occlusion, drapes, lighting |

**Default body teacher:** `rtmo_l` (GPU lab), `mediapipe` (CPU smoke).

**Selection process:** Rank on segments **without** prior landmark sidecars; pooled across ≥2 surgical clips before changing default.

---

## 3. Hand teacher selection

| Family | When it wins | When it fails |
|--------|--------------|---------------|
| MediaPipe Hand full | Open, well-lit, large hands | Adverse surgical footage (0% det.) |
| RTMO crop + MP | Medium hands with body context | Extra latency |
| RTMW whole-body | Fallback when MP fails | Lower fingertip precision |
| SavGol temporal | Stabilize winning raw backend | Never alone |

**Bake-off clips (decision set):** `5714`, `6517`, `6612` cleaned — no prior hand `.pkl` cache.

**Cached clips (`3338`, `4112`, `IMG_1564`):** sanity comparison only — not for pooled winner score.

**Graduation to CaptureSuite registry (D+):** hand specialist must meet or exceed whole-body wrist tips on decision set for detection + jitter.

---

## 4. Fusion policy

| Mode | Use |
|------|-----|
| `single` | Default for reproducible teacher |
| `fused` | Maximize coverage when models agree |

Fusion rules from `landmark_fusion.py` regional maps. Every fused point records `source_model` in parquet.

**ML valid_mask:** require min confidence per joint; fused points below threshold mask window.

---

## 5. Scale and units

| Quantity | V1 policy |
|----------|-----------|
| Image coords | pixels in full-frame space |
| Angular kinematics | degrees (Tier A) |
| Linear velocity | px/s unless extrinsic calibration preset present |
| Radar ML | radar-relative units OK; no false metric claims |

Document calibration preset type `spatial` when metric lengths required.

---

## 6. Face specialists (D+ deferred)

Spike criteria: same as hand — detection on surgical clips, privacy review ([ETHICS_AND_PRIVACY.md](ETHICS_AND_PRIVACY.md)).

---

## 7. Kinematics alignment

Tier A from [KINEMATICS_PIPELINE.md](../KINEMATICS_PIPELINE.md); Tier B Kobayashi optional with activity windows from checkpoint protocol.

IMU fusion: optional, weights in `kinematics_qc.json`.

---

## 8. Product copy rules

- “Teacher labels” not “ground truth” unless human validated.
- Show `model_id` + `model_card.json` version in analysis reports.
- Legacy overlay clips: warn if opened outside CaptureSuite sealed path.

---

## 9. Hand-off checklist to CaptureSuite Phase D

- [ ] Hand bake-off complete on decision clips  
- [ ] `rtmo_l` body teacher validated on MKV decode path  
- [ ] Fusion map version pinned in `model_card.json`  
- [ ] Kobayashi license resolved or Tier A-only ship  

---

## 10. References

- [UROLOGYMOCAP_MERGE_RESEARCH.md](UROLOGYMOCAP_MERGE_RESEARCH.md)
- [UrologyMoCap/docs/HAND_MODEL_SURVEY.md](../../../UrologyMoCap/docs/HAND_MODEL_SURVEY.md)
- [ANALYSIS.md](../ANALYSIS.md)
