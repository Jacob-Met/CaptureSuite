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

## Decision 2026-10-08: Selected export output integrity

**Reason:** Real MCAP receiving of the T68 modality-selection candidate found two
ways for exported contents to disagree with the chosen streams. An IMU stream
after an EMG stream under one neutral source ID was skipped because discovery
looked only at the first message. Reusing an earlier destination retained its
unselected files even though the replacement manifest described only the new
selection.

The continuous exporter matches the registered schema of each decoded message.
One source may contain several modalities, in separate streams or one MCAP; its
ID and first message do not determine its complete contents. EMG/IMU output files
are created only when a selected matching message is decoded. Source timestamps,
raw files and the requested-versus-actual sidecar fields retain their meaning.

Output creation, writing and close failures abort the export with an actionable
message and a nonzero result before a success manifest is written. The existing
policy for unreadable input remains isolated to input consumption; it cannot
suppress a failure to write a selected stream. Partial failed output is retained
for inspection rather than represented as a completed export.

The destination must be a new or empty directory. An existing empty folder from
the desktop picker remains supported. A nonempty destination is rejected before
export writes, with an instruction to choose another folder. Existing output is
preserved; the exporter neither deletes old files nor combines results from
different selections. Default exports still use the package's `exports/` folder.

**Files:** `tools/export_session.py`, `desktop/capture_desktop/export_wizard.py`,
`tests/analysis/test_export_selection_mcap.py`.

The receiving record is in
[`docs/evidence/export-selection-20261008/`](../../evidence/export-selection-20261008/).


## Selected feature-table exports (2026-10-08, #78)

A retained Analysis job may be exported as an explicitly selected, ordered set of
feature columns. Existing full Parquet/CSV job outputs remain the source. The
native `tools/export_feature_table.py` workflow reads all rows in original order,
writes a new directory outside the session package, and carries exact original
job/parameter/feature-schema records with versioned selected schema and hashes.
It validates retained output identity and column metadata before writing, and
does not rerun analysis or alter scientific status. CSV consumers must use the
recorded Arrow types, null/quoted-string rules and multiline parser setting.
Unsupported CSV types require Parquet. See [the workflow guide](../../FEATURE_TABLE_EXPORT.md).

This is an additive Analysis data-handoff decision. Existing Review raw/structural
exports, Analysis figure export, job execution and feature extraction retain their
established contracts.
