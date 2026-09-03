# Information architecture and product identity

Research date: **2026-09-01**  
Status: **Research complete** — input to UI implementation pass.

**Constraints:** PySide6 desktop; raw immutable; gaps explicit; depth preserved via progressive disclosure ([AGENTS.md](../../../AGENTS.md)).

---

## 1. Product promise (one sentence)

**CaptureSuite** is a multimodal research platform where operators seal honest raw packages during capture, then run reproducible analysis jobs on the same session clock—without leaving one application or losing provenance.

---

## 2. Current IA (baseline)

| Tab | Today | Maturity |
|-----|-------|----------|
| **Capture** | Rail + Timeline/Focus/Grid, transport, live previews | Strong |
| **Setup** | Schema-driven per-source config | Strong |
| **Review** | Summary cards, gap list, export trigger | Thin |
| **Analysis** | Job launcher, external HTML/PNG | Thin |

**Problem:** Capture feels like a product; Review and Analysis feel like utilities bolted on. There is no shared **session navigator** (timeline + scope) across live and sealed modes.

---

## 3. Target IA — unified session shell

### 3.1 Primary navigation (top level)

Keep four tabs but redefine their contract:

| Tab | Mode | Primary question |
|-----|------|------------------|
| **Capture** | Live (daemon connected) | “Are all sources healthy and recording honestly?” |
| **Setup** | Live or idle | “Are devices configured correctly for this protocol?” |
| **Review** | Sealed package open | “Is this package intact and ready for science?” |
| **Analysis** | Sealed package open | “What derived products do I need from this package?” |

**Decision:** Do **not** merge tabs into a single mode switcher. Researchers expect capture vs analysis separation for safety (no analysis during RECORDING). Instead, **share components** across Review and Analysis.

### 3.2 Shared session chrome (new)

A persistent **SessionHeader** appears whenever a package is open (live or sealed):

```
┌─────────────────────────────────────────────────────────────────┐
│ Project: Urology-R1 · Participant P042 · Visit 2                │
│ Session: 2026-08-30T14:22Z · status: recording | sealed | recovered │
├─────────────────────────────────────────────────────────────────┤
│ [SessionTimeline ───●─────────── gaps ░░ checkpoints ◆]         │
│ Scope: ○ Full  ○ Section: VP_Insertion  ○ Range [____–____]     │
└─────────────────────────────────────────────────────────────────┘
```

**SessionTimeline** (single component, two data sources):

| State | Data source |
|-------|-------------|
| Live | Daemon session clock + gap events + checkpoints |
| Sealed | `events/checkpoints.json`, gap JSONL, stream segment index |

Default scrub action: move **analysis scope** and **review playhead** together; video decode is lazy (timing MCAP first).

### 3.3 Capture tab (refined, not replaced)

Preserve [UI_CONTRACT.md](../UI_CONTRACT.md) layout. Add:

- **Protocol chip** — active checkpoint protocol preset name.
- **Array chip** — radar array name + “software coordinated” badge.
- **Honesty strip** — one line: native rates, no resample, raw path status.

Expanded cards per modality (see modality scorecards) use **Focus** as the expanded inspector; Timeline stays glanceable.

### 3.4 Review tab (target)

| Region | Content |
|--------|---------|
| Left | Source list with integrity badges (segments sealed, gap count, recovered flag) |
| Centre | SessionTimeline + per-source segment map |
| Right | Export panel + recovery summary |

Actions: open folder, run session_doctor, export matrix (see [REVIEW_AND_EXPORT_UX.md](REVIEW_AND_EXPORT_UX.md)).

### 3.5 Analysis tab (target)

| Region | Content |
|--------|---------|
| Left | Job palette (QC, Features, Plots, Pose, Kinematics, ML bundle, Eval) |
| Centre | Figure gallery (embedded) + scope from SessionHeader |
| Right | Job inspector (params, outputs, provenance, logs) |

See [ANALYSIS_WORKBENCH.md](ANALYSIS_WORKBENCH.md).

---

## 4. Depth-preserving UX principles

1. **Progressive disclosure** — Basic operators see health + record/stop; advanced fields live in Setup “Advanced” groups and Analysis job params. Never remove expert controls.
2. **Dual surface** — Capture = glanceable (≤3 s to answer “are we good?”); Analysis = dense workbench (multi-lane plots, tables, job DAG).
3. **Provenance always visible** — Units, `calibrated: false`, gap policy, AnalysisGrid method, model_id for pose columns.
4. **Power-user density** — Full hotkey map; keyboard checkpoint; optional global hotkeys off by default ([SETTINGS_REGISTRY.md](../SETTINGS_REGISTRY.md)).
5. **Fail loud, recover honest** — `finalized_recovered` banner; no green checkmark on incomplete packages.
6. **No daemon-driven view changes** — UI_CONTRACT guarantee preserved.

---

## 5. Project / cohort metadata UX

### 5.1 Create session flow (two tiers)

**Quick capture** (default): parent path + optional label → record immediately. Writes minimal `session.json`.

**Protocol capture** (expanded): pick **project** → **participant** → **visit** → **activity catalog** → checkpoint protocol preset → then Create. Embeds full preset snapshots in package ([PRESETS_SETTINGS.md](../../../docs/spec/PRESETS_SETTINGS.md)).

### 5.2 `project.json` fields (research recommendation)

| Field | Required | Purpose |
|-------|----------|---------|
| `project_id` | yes | Stable slug |
| `title` | yes | Display name |
| `pi` / `lab` | no | Cohort metadata |
| `default_activity_catalog_id` | no | Links [activity catalogs](../../../schemas/activity_catalog/) |
| `default_naming_preset_id` | no | File naming |
| `default_export_preset_id` | no | Review tab default |

Stored in project folder; **not** in registry.sqlite as authority.

### 5.3 Session-level metadata

Extend sealed `session.json` with optional: `participant_id`, `visit_id`, `operator`, `protocol_version`, `notes`. Analysis jobs inherit these into `job_manifest.json` for report headers.

---

## 6. Branding and chrome

| Today | Target |
|-------|--------|
| “Milestone 4 · daemon-backed capture UI” banner | Product name + session state only |
| Dark-only `theme.py` | Honor `settings.theme`: system / light / dark ([DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md)) |
| Ad-hoc QSS | Token-based stylesheet generation |

**Status grammar** (from UI_CONTRACT health): every card answers: connected? rate? last sample age? gaps? write path ok?

---

## 7. Accessibility and long-session ergonomics

- **Modality lane colors** — keep hue distinction; add shape/icon redundancy for colorblind users (EMG = trace icon, radar = grid, etc.).
- **REC indicator** — high-contrast border + text; optional audible alert on CRITICAL only.
- **Confirm stop** — `confirm_stop_always` default true; daemon token cannot be disabled.
- **Multi-monitor** — `window_geometry` per monitor fingerprint; workspace presets restore rail width, grid columns, popped-out preview windows (future).

---

## 8. Wireframe summary (ASCII)

```
App
├── TransportBar (session create/open, record, checkpoint, stop)
├── SessionHeader (shared Review+Analysis+live optional)
├── Tabs
│   ├── Capture [rail | timeline/focus/grid | dock]
│   ├── Setup   [source list | schema form]
│   ├── Review  [integrity | timeline | export]
│   └── Analysis[jobs | gallery | inspector]
└── StatusBar (daemon link, disk, alerts)
```

---

## 9. Open decisions resolved

| Question | Decision |
|----------|----------|
| Single app vs two apps | Single PySide6 app, tab-separated modes |
| Unified timeline | Yes — one component, live vs sealed backends |
| Analysis during record | Blocked (existing rule) |
| Project metadata blocking quick capture | No — two-tier create flow |

---

## 10. References

- [UI_UX.md](../../../docs/spec/UI_UX.md)
- [FUTURE_ANALYSIS_NOTES.md](../../../docs/spec/FUTURE_ANALYSIS_NOTES.md)
- [screen_capture.py](../../../desktop/capture_desktop/screen_capture.py)
- [COMPETITIVE_AUDIT.md](COMPETITIVE_AUDIT.md)
