# Modality depth scorecard: EMG

Research date: **2026-09-01**  
Schema: `emg.batch/1` — today **sim** `sim.emg.main`; target **Delsys** M8 ([adapters/delsys.md](../adapters/delsys.md))

---

## Scorecard

| Dimension | Today (sim/replay) | Target (HW) | Gap / action |
|-----------|--------------------|-------------|--------------|
| Proof of life | **4** | 5 | Per-channel last-sample + ref electrode (Phase 8 Delsys) |
| Expanded card | **4** | 5 | Channel grid + units + dropout; muscle map when preset set |
| Setup schema | 2 | 5 | Complete Delsys spike → `capture_worker_emg` (Phase 8) |
| Preflight | 3 | 4 | Sim rate/gap checks; baseline noise on hardware |
| Failure modes | **4** | 4 | Gaps + dropped_last_10s surfaced on Focus card |
| Spatial / anatomy | 3 | 5 | Anatomical preset field on card; full muscle editor Phase 5+ |
| Record honesty | **4** | 5 | Native Hz; units honest (`a.u.` until calibrated) |
| Export / review | **4** | 4 | Stream inventory lists schema/dims/units/segments |

**Phase 4 sim gate:** dimensions that apply without bench hardware average ≥4/5 (setup schema deferred to Phase 8).

---

## Proof of life

| Field | Sim today | Delsys target |
|-------|-----------|---------------|
| Channel count | 8 | Up to 16 |
| Effective rate | 2000 Hz nominal | Device-native |
| Clip/sat indicator | — | per channel |
| Wireless RSSI | — | optional |

---

## Expanded card

- **TRACE_BLOCK** preview (256 samples × N ch)
- Channel → muscle name from anatomical preset
- Toggle: raw vs band-pass preview (preview only, not record)

---

## Delsys spike checklist (research → adapter)

Complete [adapters/delsys.md](../adapters/delsys.md) §1–8 from [VENDOR_SPIKE.md](../VENDOR_SPIKE.md):

1. Discovery / pairing API  
2. Stable device key  
3. Timestamp source (host vs device)  
4. Batch shape + dropout behavior  
5. Trigger / external sync lines  
6. Credential storage (DPAPI)  
7. Config schema revision  
8. Soak ≥ 30 min multi-sensor  

---

## Preflight

| Check | Severity |
|-------|----------|
| All logical slots mapped | warn |
| Reference electrode connected | warn |
| 60 Hz line noise floor | info |
| Sample rate matches descriptor | fail |

---

## Anatomical mapping

Required for analysis: EMG channel → muscle → joint/segment for coupling plots ([FUTURE_ANALYSIS_NOTES.md](../../../docs/spec/FUTURE_ANALYSIS_NOTES.md)). Editor in Analysis workbench; preset type `anatomical`.

---

## Analysis hooks

Phase B: RMS, MAV, WL, ZC, SSC. Extend per [FEATURE_CATALOG_RESEARCH.md](FEATURE_CATALOG_RESEARCH.md). Mark provisional until real Delsys data ([ANALYSIS.md](../ANALYSIS.md)).

---

## References

- [adapters/delsys.md](../adapters/delsys.md)
- [DATA_COLLECTION_PROTOCOL.md](../DATA_COLLECTION_PROTOCOL.md)
