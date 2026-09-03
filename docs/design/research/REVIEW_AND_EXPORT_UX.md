# Review and export UX

Research date: **2026-09-01**  
Status: **Research complete**

**Constraint:** Export is non-destructive; registry.sqlite is never authoritative ([SETTINGS_REGISTRY.md](../SETTINGS_REGISTRY.md)).

---

## 1. Goals

1. Sealed packages as navigable as live capture ([IA_AND_PRODUCT.md](IA_AND_PRODUCT.md)).
2. Integrity visible before analysis spend.
3. Export matrix: format × scope × provenance sidecar.

---

## 2. Unified timeline (sealed)

| Layer | Source | Default load cost |
|-------|--------|-------------------|
| Session bounds | `session.json` | O(1) |
| Gaps | `sources/*/health/gaps.jsonl` | O(n gaps) |
| Checkpoints | `events/checkpoints.json` | O(1) |
| Segment index | `sources/*/streams/*/segments/` | O(segments) |
| Video frames | MKV decode | **Lazy** — only when operator scrubs video lane |

**Shared component:** `SessionTimeline` — same widget as Analysis scope picker.

Scrub actions:
- Move playhead (review)
- Set analysis scope `[t0, t1]`
- Optional: spawn preview frame at playhead (low-res grab)

---

## 3. Review workbench layout

```
┌──────────────┬────────────────────────────┬──────────────┐
│ Sources      │ SessionTimeline + gaps     │ Export       │
│ integrity    │ segment map per source     │ wizard       │
│ badges       │ checkpoint markers         │              │
│ recovered ⚠  │                            │ recovery     │
└──────────────┴────────────────────────────┴──────────────┘
```

### 3.1 Source integrity badges

| Badge | Meaning |
|-------|---------|
| Sealed | All segments have integrity hash |
| Gaps | N open/closed gaps |
| Recovered | Package `finalized_recovered` |
| Sim | Source id prefix `sim.` |
| Uncalibrated | units `a.u.` on descriptor |

### 3.2 Recovery UX

When `session_doctor` recovered package:
- Banner: **“Recovered session — explicit gaps preserved”**
- Link to [RECOVERY.md](../RECOVERY.md) operator steps
- Disable “export as pristine” wording

---

## 4. Export format decision table

| Format | Owner tab | Scope options | Provenance sidecar |
|--------|-----------|---------------|-------------------|
| Continuous MKV/MCAP copy | Review | Full session | manifest.json copy |
| Checkpoint-organized folders | Review | Per checkpoint section | section metadata |
| Parquet (features) | Analysis | Job outputs only | `job_manifest.json` |
| HDF5 (large tensors) | Analysis | ML bundle, RD stacks | `ml_bundle/manifest.json` |
| CSV | Analysis | Feature tables | column units in `_schema.json` |
| PNG/PDF report bundle | Analysis | QC + figures | job_id stamped |
| External tool (OpenCap-style) | Review | Video + timing | export preset |

**Decision:** Review owns **raw and structural** export; Analysis owns **derived** export. Never export derived over raw without operator confirmation.

---

## 5. Export wizard (Review)

Steps:
1. **Scope** — full / checkpoint sections / time range  
2. **Streams** — subset by source_id  
3. **Format** — from table above  
4. **Options** — include gaps sidecar, include arrays.json, anonymize paths  
5. **Destination** — remember `last_export_path`  

Preset type: `export` ([PRESETS_AND_SETTINGS_UX.md](PRESETS_AND_SETTINGS_UX.md)).

---

## 6. Multi-session library

| Feature | Storage | Note |
|---------|---------|------|
| Recent sessions | `registry.sqlite` | Convenience only |
| Project filter | `project_id` in session metadata | |
| Tags | registry + optional session tags file | |
| Search | filename, participant_id, date | |

**Open package** always reads from disk path — registry miss must still work.

---

## 7. Implementation mapping

| Feature | File target |
|---------|-------------|
| Review layout | `screen_review.py` |
| SessionTimeline | new `widgets_session_timeline.py` |
| Export wizard | `screen_review.py` or `export_wizard.py` |
| Continuous export | existing `tools/export_session.py` |

---

## 8. References

- [RECOVERY.md](../RECOVERY.md)
- [SESSION_FORMAT.md](../SESSION_FORMAT.md)
- [IMPLEMENTATION_PLAN.md](../../../docs/spec/IMPLEMENTATION_PLAN.md) M11
