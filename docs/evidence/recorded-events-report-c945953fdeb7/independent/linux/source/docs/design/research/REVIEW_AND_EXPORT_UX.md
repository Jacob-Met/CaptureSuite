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


## Decision 2026-10-08: Explicit recorded-video segment inspection

**Reason:** The current Review inventory counts retained MKV files but cannot show
them. The desired unified session timeline depends on a trustworthy segment-to-
session mapping; the current timing loader has an explicit segment-index stub.
This bounded first viewer makes retained video inspectable without inventing that
mapping or changing its owner's timing work.

Review adds a collapsible Recorded video section using the existing stream
discovery and PySide6 multimedia backend. Each explicit choice includes source,
stream and package-relative file identity. Package load only builds the inventory;
selection lazily loads one media file, and Play remains an explicit operator action.
The native media clock is labeled segment-local. No camera/checkpoint alignment,
gap interpolation, continuous segment join, audio playback or integrity assurance
is inferred. Only finalized and finalized_recovered packages are admitted.

Changing selections or clearing/failing a package load retires the old player,
output and active controls before loading another. Every native media callback is
bound to both its player and selection generation. Missing files and decoder
errors retain an actionable identity and explicit reload path, without an old
picture under a new selection. Hiding the section or Review pauses playback.
The existing event browser, timeline, analysis, export and raw bytes retain their
separate ownership and behavior.

**Files:** `desktop/capture_desktop/review_video.py`,
`desktop/capture_desktop/widgets_review_video.py`, and seven additive lines in
`desktop/capture_desktop/screen_review.py`. Operator steps are in
[Recorded video review](../../operator/RECORDED_VIDEO_REVIEW.md). Native source,
actual-decoder qualification, independent stale-signal receiving and the explicit
GPU-screenshot limitation are retained in
[the receiving record](../../evidence/review-video-0378a7b6/README.md).

A subsequent actual MainWindow receiver showed its existing global checkpoint
Space shortcut intercepting focused video-button activation. The viewer therefore
accepts unmodified Space ShortcutOverride only on its own Play, Reload and
disclosure buttons. Native button activation proceeds normally; other keys,
modifiers, controls and the application shortcut implementation remain unchanged.
The exact before/after witness is in the receiving record's keyboard correction.
