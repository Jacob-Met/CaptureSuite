# Modality depth scorecard: IMU

Research date: **2026-09-01**  
Schema: `imu.frame/1` — today **sim** `sim.imu.upper` (7 sensors); target **Xsens** M7 ([adapters/xsens.md](../adapters/xsens.md))

---

## Scorecard

| Dimension | Today (sim/replay) | Target (HW) | Gap / action |
|-----------|--------------------|-------------|--------------|
| Proof of life | **4** | 5 | Mag disturbance + per-sensor validity (Phase 8 Xsens) |
| Expanded card | **4** | 5 | Segment tree default + quaternion + |a| |
| Setup schema | 2 | 5 | Xsens spike → shared worker (Phase 8) |
| Preflight | 3 | 4 | Packet health on card; radio link on HW |
| Failure modes | **4** | 4 | Drops/gaps surfaced |
| Spatial / anatomy | 3 | 5 | Segment map field; fusion map Phase 5 |
| Record honesty | **4** | 5 | Multi-sensor frame; units honest |
| Export / review | **4** | 4 | Stream inventory in Review |

**Phase 4 sim gate:** non-HW-blocked dimensions ≥4/5.

---

## Proof of life

UI_CONTRACT: ORIENTATION preview for **one selected sensor** (default). Card shows which sensor is previewed + count of active sensors in frame.

**Add:**
- Magnetic field disturbance indicator
- Calibration state (Xsens)
- Packet loss counter

---

## Expanded card

| Mode | Preview kind |
|------|--------------|
| Native | ORIENTATION cube ([SETTINGS_REGISTRY.md](../SETTINGS_REGISTRY.md) `preview_kind_styles`) |
| Graph | Accel/gyro traces |

Segment tree: pelvis → thorax → upper arms → … (operator assigns logical slots).

---

## Xsens spike checklist

Complete [adapters/xsens.md](../adapters/xsens.md):

1. MVN vs raw streaming mode for record  
2. Timestamp alignment with session clock  
3. Multi-sensor frame layout  
4. Worker isolation: **shared** receiver ([WORKER_HOST.md](../WORKER_HOST.md))  
5. Pairing workflow UX  

---

## Preflight

| Check | Severity |
|-------|----------|
| Minimum sensor set for protocol | warn |
| Stillness calibration optional step | info |
| Nominal rate achievable | fail |

---

## Kinematics fusion (Phase D2)

Optional IMU fusion into teacher kinematics — record weights in `kinematics_qc.json` ([KINEMATICS_PIPELINE.md](../KINEMATICS_PIPELINE.md)).

---

## Analysis hooks

Phase B: accel/gyro magnitude stats. Extend: orientation Euler, jerk, still detection ([FEATURE_CATALOG_RESEARCH.md](FEATURE_CATALOG_RESEARCH.md)).

---

## References

- [adapters/xsens.md](../adapters/xsens.md)
- [UI_CONTRACT.md](../UI_CONTRACT.md) — single-sensor default preview
