# Modality depth scorecard: FMCW Radar

Research date: **2026-09-01**  
Schema: `radar.frame/1` — `uint16_le_raw_interleaved` ([RADAR_PIPELINE.md](../RADAR_PIPELINE.md))

---

## Scorecard

| Dimension | Today (sim/replay) | Target (HW) | Gap / action |
|-----------|--------------------|-------------|--------------|
| Proof of life | **4** | 5 | Config hash + measured fps on Focus card |
| Expanded card | **4** | 5 | RD heatmap dims + software-array badge |
| Setup schema | **4** | 5 | Chirp params via setup schema (sim) |
| Preflight | 3 | 5 | USB bandwidth / firmware (Phase 8) |
| Failure modes | **4** | 5 | Overload drops + gap taxonomy |
| Spatial / anatomy | **4** | 4 | Array editor + `radar_array` preset save |
| Record honesty | **5** | 5 | Raw ADC; preview derived never recorded |
| Export / review | **4** | 4 | Stream inventory + config schema id |

**Phase 4 sim gate:** met for FMCW family on sim/replay.

---

## Proof of life

**Add beyond UI_CONTRACT:**
- `configuration_hash` (matches stream.json snapshot)
- `frames_per_second` (measured)
- `host_arrival_jitter_p95` (session rolling)
- Badge: **“Software coordinated”** when in multi-radar array

---

## Expanded card

| Widget | Purpose |
|--------|---------|
| MATRIX_2D heatmap | Range–Doppler preview (Fusion views) |
| View combo | MTI / RD / custom ([RADAR_PIPELINE.md](../RADAR_PIPELINE.md)) |
| Motion energy trace | Proof of subject motion |
| Chirp summary | BW, samples, chirps (read-only during record) |

---

## Setup schema

`radar.ifx/3`: bandwidth, samples, chirps, antennas, gain — mark `x-capture-restart-required` where SDK demands.

---

## Preflight

| Check | Severity |
|-------|----------|
| Board UUID discovered | fail |
| Config applies cleanly | fail |
| Sim radar deselected when real present | info |
| Array membership consistent | warn |

---

## Failure modes

| Event | UX |
|-------|-----|
| Frame gap (DISCONNECT) | Timeline band; no interpolate |
| Overload | OverloadEvent → alert |
| Config drift | Warn if effective ≠ requested |

---

## Timing honesty

HUD footnote: **“Radar timestamps are device-native; host arrival may lag (see TIMING.md).”**

---

## Analysis hooks

Streaming loader → frame features → optional RD `.npy` in `derived/radar/`. See [FEATURE_CATALOG_RESEARCH.md](FEATURE_CATALOG_RESEARCH.md).

---

## References

- [RADAR_PIPELINE.md](../RADAR_PIPELINE.md)
- [adapters/infineon_bgt60tr13c.md](../adapters/infineon_bgt60tr13c.md)
- [capture_worker_radar](../../workers/radar/)
