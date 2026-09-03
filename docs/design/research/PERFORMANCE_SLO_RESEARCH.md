# Performance SLO research

Research date: **2026-09-01**  
Target hardware reference: RTX 4070 lab PC, Windows, Python 3.12.

---

## 1. Session soak SLOs (capture)

| Scenario | Duration | SLO | Measurement |
|----------|----------|-----|-------------|
| 2× camera 1080p30 | 120 s | 0 dropped record frames | existing `soak_multi_cam.py` |
| 2× camera + sim EMG/IMU | 120 s | write_ok all sources | extend soak |
| 1× TR13C + 1× LTR11 | 120 s | no DISCONNECT gaps | `probe_radar_*` |
| 2× TR13C software array | 120 s | both seal segments | concurrent throughput |
| 2 h multi-modal | 7200 s | REC uninterrupted; disk alert before fail | long soak (manual/nightly) |

---

## 2. Preview transport

| Mode | SLO | Action if missed |
|------|-----|------------------|
| Pipe JPEG 2 cam | ≤15 Hz effective per cam | consider SHM ([PREVIEW_TRANSPORT.md](../PREVIEW_TRANSPORT.md)) |
| SHM ring (future) | ≤2 ms copy latency p95 | cutover criteria from design doc |

---

## 3. Analysis RAM

| Stream | Policy | Budget |
|--------|--------|--------|
| Radar FMCW | Iterator only | O(1) heap vs session length |
| EMG/IMU | Materialize guard | default 2 GiB (`max_ram_bytes`) |
| Video pose | Segment decode | batch frames; cap in-flight buffers |

Job fails with named stream if over budget — never swap silently.

---

## 4. Analysis throughput (indicative)

| Job | Indicative | Notes |
|-----|------------|-------|
| QC | <30 s / session | |
| Features (sim session) | <60 s | |
| Pose rtmo_l full HD | ~realtime × 0.3–0.5 GPU | parallel segment workers later |
| Hand 47-model sweep | hours | research batch only |
| ML bundle build | minutes | depends on window count |

---

## 5. Disk

| Alert | Threshold |
|-------|-----------|
| Warning | <20 GB free on session volume |
| Critical | <5 GB — block Start |

Review tab shows estimated bytes/source from segment index.

---

## 6. Versioning performance

Reading old job manifests must remain O(open job) — not full package scan.

Plugin manifest cached at app start; invalidate on file change.

---

## 7. CI vs lab SLOs

CI: mini_session fixtures, <2 min analysis tests.

Lab: soak scripts nightly optional; not gating PR.

---

## 8. References

- [OPERATIONS.md](../OPERATIONS.md)
- [ANALYSIS.md](../ANALYSIS.md)
- [tools/soak_multi_cam.py](../../tools/soak_multi_cam.py)
