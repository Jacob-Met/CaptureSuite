# Agent progress log

Agents: **read at session start, update at session end.**  
Plan: [AUTONOMOUS_EXECUTION_PLAN.md](AUTONOMOUS_EXECUTION_PLAN.md)

---

## Current phase

| Field | Value |
|-------|-------|
| **Active phase** | **Public release prep** (plugin registry + SDK shipped); Phases 0→6 still green on sim |
| **Next implementation** | Cut `v0.1.0` on GitHub + Zenodo DOI; Phase 8 hardware validation when devices available |
| **Parallel workstream** | None required for 0–6 gate |

---

## Operator directives

| Date | Directive |
|------|-----------|
| 2026-09-01 | **Hardware last** — sim/replay/fixtures only until Phase 8 |
| 2026-09-01 | **Industry-quality bar** — cross-cutting every phase |
| 2026-09-01 | **No hand tracker** / overlay salvage until re-enabled here |

---

## Phase status

| Phase | Status | Gate evidence |
|-------|--------|---------------|
| Research (Tracks A–H) | **Done** | [README.md](README.md) |
| 0 Foundation | **Done** | Theme, SessionTimeline, Preferences, honesty banners |
| 1 Review + export | **Done** | Export wizard + provenance sidecar; Review stream inventory |
| 2 Analysis plugins | **Done** | Manifest registry; dummy plugin; pipeline dispatch |
| 3 Analysis workbench | **Done** | In-app PyQtGraph; no plot `startfile` |
| 4 Modality depth | **Done** (sim) | Scorecards ≥4/5 on sim-applicable dims; HW setup/preflight → Phase 8 |
| 5 Pose + kinematics | **Done** (sim) | `pose` + `kinematics` + mappings panel; registry-valid parquet |
| 6 ML bundle + eval | **Done** (sim) | Schema-valid `ml_bundle`; radar→teacher test; Analysis UI commands |

---

## Blockers (product / legal only)

| Blocker | Workstream | Mitigation |
|---------|------------|------------|
| Kobayashi license | Tier B metrics | Tier A only |
| Hand tracker bake-off | UrologyMoCap | **Deferred by operator** |

---

## Last verified (update each session)

| Check | Date | Result |
|-------|------|--------|
| `pytest tests/protocol` + `tests/analysis` | 2026-09-03 | green (incl. Python SDK + LSL unit tests) |
| `tools/check_licenses.py --enforce-spdx` | 2026-09-03 | OK |
| Protocol minor | 2026-09-03 | **1.5** (`ListPlugins`) |

---

## Session log (newest first)

### 2026-09-03 — Public release plan (Phases A–E)

**Shipped:**
- Standalone product tree (lab sidecar dirs relocated out of CaptureSuite)
- GPL/Apache split + community health files + SPDX
- `PluginRegistry` + `plugin.json` discovery + `ListPlugins`
- Core cleanup: `generic.numeric_batch/1`, neutral sim aliases
- Python worker SDK, example sine + LSL bridge plugins
- Docs: `docs/spec/`, `docs/plugins/`, `docs/operator/`, README rewrite
- CI (`ci.yml`) + release workflow; `tools/run-demo.ps1`

**Remaining for human operator:** create GitHub repo, push, enable Zenodo, tag `v0.1.0`, paste DOI into `CITATION.cff` / README.

### 2026-09-01 — Phase 4 scorecards + Phase 6 Analysis UI (goal closure)

**Shipped:**
- Analysis workbench: pose / kinematics / ml_bundle / eval commands + dependency pickers (`widgets_analysis_jobs.py`)
- Anatomical/spatial mappings panel (`widgets_mappings.py`)
- Review stream inventory (schema, rate, dims, units, segments)
- Deeper Focus modality strips (EMG channel grid, IMU segments, radar/camera slots)
- Radar→teacher `ml_bundle` fixture test + schema validation
- Modality scorecards updated for sim/replay ≥4/5 (HW-deferred dims noted)

**Gate:** Phases 0→6 automated gates green on sim/fixtures. Phase 8 HW remains last.

### 2026-09-01 — Phase 5 kinematics + Phase 6 ML bundle/eval (sim)

**Shipped:**
- `capture_analysis/kinematics/` — Tier A from pose landmarks; registry column validation
- `capture_analysis/ml_bundle/` — aligned windows + `capture.ml_bundle/1` manifest
- `capture_analysis/eval/` — identity baseline eval report
- `tools/run_analysis.py` — `kinematics`, `ml_bundle`, `eval` subcommands

### 2026-09-01 — Phase 4 modality depth + Phase 5 pose sim teacher

**Shipped:** Expanded Focus cards, preset library, radar array preset, vendor replay, sim pose teacher.
