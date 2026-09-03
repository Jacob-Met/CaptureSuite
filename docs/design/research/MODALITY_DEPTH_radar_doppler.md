# Modality depth scorecard: Doppler Radar (LTR11)

Research date: **2026-09-01**  
Schema: `radar.doppler/1` — `complex_float32_le` ([RADAR_PIPELINE.md](../RADAR_PIPELINE.md))

---

## Scorecard

| Dimension | Today (sim/replay) | Target (HW) | Gap / action |
|-----------|--------------------|-------------|--------------|
| Proof of life | **4** | 5 | Motion trace path distinct from FMCW MATRIX |
| Expanded card | **4** | 5 | Trace vs matrix branch; slot label |
| Setup schema | 3 | 4 | `disable_internal_detector` (Phase 8 board) |
| Preflight | 3 | 4 | Board class coexistence (Phase 8) |
| Failure modes | **4** | 4 | Same gap taxonomy as FMCW |
| Spatial / anatomy | 2 | 2 | Single-antenna — slot label only |
| Record honesty | **5** | 5 | Complex float trace recorded |
| Export / review | **4** | 4 | Stream inventory same as FMCW |

**Phase 4 sim gate:** met for Doppler family on sim/replay (setup/preflight HW-deferred).

---

## Proof of life

Doppler has **no range** — health must not imply FMCW semantics.

**Show:**
- `modality: radar_doppler` lane color (cyan family)
- Motion detected flag (derived preview)
- Peak Doppler bin / magnitude
- Sample rate (nominal vs measured)

---

## Preview

Reuse `TRACE_BLOCK` or dedicated spectrogram tile. Preview is **motion trace**, not MATRIX_2D.

---

## Setup

LTR11-specific fields from [adapters/infineon_bgt60ltr11aip.md](../adapters/infineon_bgt60ltr11aip.md). Spike: device timestamp source TBD — show “timestamp provisional” until validated.

---

## Coexistence with FMCW

Same worker exe, two `StreamDescriptor`s. UI groups under “Radar” family with sub-badge FMCW vs Doppler.

---

## Analysis hooks

`extract_radar_doppler_features` — extend with spectral features ([FEATURE_CATALOG_RESEARCH.md](FEATURE_CATALOG_RESEARCH.md)).

---

## References

- [RADAR_PIPELINE.md](../RADAR_PIPELINE.md)
- [adapters/infineon_bgt60ltr11aip.md](../adapters/infineon_bgt60ltr11aip.md)
