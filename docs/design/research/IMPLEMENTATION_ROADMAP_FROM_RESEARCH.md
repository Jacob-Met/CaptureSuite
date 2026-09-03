# Implementation roadmap (from research)

Research date: **2026-09-01**  
Synthesizes [research/README.md](README.md) into a phased build order.

**Do not re-decide** items pinned in existing design docs without recording a reason in the relevant doc.

---

## Industry-quality target

CaptureSuite should read and behave like a **professional lab instrument**, not a research prototype:

| Layer | Standard | Enforced via |
|-------|----------|--------------|
| **Machine** | Stable long captures, bounded RAM, honest gaps, diagnostic bundles | [PERFORMANCE_SLO_RESEARCH.md](PERFORMANCE_SLO_RESEARCH.md), soak scripts, AGENTS core rules |
| **Presentation** | Design tokens, light/dark, no demo chrome, competitive density | [DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md), [COMPETITIVE_AUDIT.md](COMPETITIVE_AUDIT.md) checklist |
| **Operator** | Clear IA, preflight/recovery honesty, export provenance, learnable docs | [IA_AND_PRODUCT.md](IA_AND_PRODUCT.md), [ETHICS_AND_PRIVACY.md](ETHICS_AND_PRIVACY.md), operator manual outline |

Each phase gate below includes a **quality check** in addition to the functional deliverable.

---

## Development path: sim and replay first

**Hardware bench validation is last.** All phases through 6 proceed on sim workers, `tests/fixtures/mini_session`, sealed packages, and vendor sample/replay files. Features stay `provisional` until a tagged `hardware_validated` fixture exists — but that tag never blocks shipping the sim/replay path.

---

## Success criteria (research phase — met)

- [x] V1 modality depth scorecards  
- [x] Acquisition + analysis plugin contracts sketched  
- [x] Analysis workbench IA + plot stack chosen  
- [x] Brainstorm modalities sketched  
- [x] Competitive polish checklist  
- [x] This roadmap references research notes  

---

## Phase 0 — Foundation (4–6 weeks)

| Item | Research source | Deliverable |
|------|-----------------|-------------|
| Design system tokens + light theme | [DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md) | Refactor `theme.py` |
| SessionHeader + SessionTimeline widget | [IA_AND_PRODUCT.md](IA_AND_PRODUCT.md) | `widgets_session_timeline.py` |
| Product chrome (remove milestone banner) | [COMPETITIVE_AUDIT.md](COMPETITIVE_AUDIT.md) | `app.py` |
| Preferences window (core keys) | [PRESETS_AND_SETTINGS_UX.md](PRESETS_AND_SETTINGS_UX.md) | `screen_settings.py` |
| Data honesty banners | [ETHICS_AND_PRIVACY.md](ETHICS_AND_PRIVACY.md) | Review + Capture |

**Gate:** Usability review on 2 h mock session navigation.  
**Quality:** Theme tokens on all touched widgets; milestone banner removed; settings persist across restart.

---

## Phase 1 — Review + export (3–4 weeks)

| Item | Research source | Deliverable |
|------|-----------------|-------------|
| Review workbench layout | [REVIEW_AND_EXPORT_UX.md](REVIEW_AND_EXPORT_UX.md) | `screen_review.py` |
| Export wizard | same | `export_wizard.py` |
| Recovery UX | [RECOVERY.md](../RECOVERY.md) | banners + doctor link |
| Project/protocol create flow | [IA_AND_PRODUCT.md](IA_AND_PRODUCT.md) | transport wizard |

**Gate:** Export checkpoint section with provenance sidecar on mini_session.  
**Quality:** Export wizard matches competitive checklist; recovered-session banner visible and accurate.

---

## Phase 2 — Analysis plugin infrastructure (5–7 weeks)

| Item | Research source | Deliverable |
|------|-----------------|-------------|
| YAML manifest registry | [ANALYSIS_PLUGIN_ARCHITECTURE.md](ANALYSIS_PLUGIN_ARCHITECTURE.md) | `plugins/registry.py` |
| Migrate EMG/IMU/radar to manifest | [FEATURE_CATALOG_RESEARCH.md](FEATURE_CATALOG_RESEARCH.md) | no `pipeline.py` elif |
| AnalysisGrid engine + sync anchors | same + [ANALYSIS_SCOPE_SEMANTICS.md](ANALYSIS_SCOPE_SEMANTICS.md) | `grids.py` |
| Job DAG in manifest | [schemas/analysis_job_dag.schema.json](schemas/analysis_job_dag.schema.json) | `jobs.py` |
| Plugin test template | [OPERATOR_AND_PLUGIN_DOCS_OUTLINE.md](OPERATOR_AND_PLUGIN_DOCS_OUTLINE.md) | `tests/analysis/test_plugin_*.py` |

**Gate:** Third-party dummy extractor loads via manifest only.  
**Quality:** Job failures surface actionable messages + log path; no silent RAM overruns.

---

## Phase 3 — Analysis workbench UI (5–6 weeks)

| Item | Research source | Deliverable |
|------|-----------------|-------------|
| Workbench shell | [ANALYSIS_WORKBENCH.md](ANALYSIS_WORKBENCH.md) | refactor `screen_analysis.py` |
| PyQtGraph sync dashboard | same | `widgets_analysis_plots.py` |
| Figure gallery + job inspector | same | gallery widget |
| Scope picker binding | [ANALYSIS_SCOPE_SEMANTICS.md](ANALYSIS_SCOPE_SEMANTICS.md) | SessionHeader signal |

**Gate:** Features+plots job fully in-app without `os.startfile`.  
**Quality:** PyQtGraph sync dashboard matches workbench IA; scope picker bound to SessionHeader.

---

## Phase 4 — Modality live depth (parallel tracks, 6–10 weeks)

**Sim/replay first.** EMG/IMU tracks do not wait for bench hardware.

| Track | Research source | Dev path |
|-------|-----------------|----------|
| Camera UVC + expanded cards | [MODALITY_DEPTH_camera.md](MODALITY_DEPTH_camera.md) | Sim + optional UVC |
| Radar array editor | [MODALITY_DEPTH_radar_fmcw.md](MODALITY_DEPTH_radar_fmcw.md) | Sim + probe tools |
| EMG Delsys worker | [MODALITY_DEPTH_emg.md](MODALITY_DEPTH_emg.md) | **Replay fixtures + sim** → `provisional` |
| IMU Xsens worker | [MODALITY_DEPTH_imu.md](MODALITY_DEPTH_imu.md) | **Replay fixtures + sim** → `provisional` |
| Doppler polish | [MODALITY_DEPTH_radar_doppler.md](MODALITY_DEPTH_radar_doppler.md) | Sim |
| Preset library (10 types) | [PRESETS_AND_SETTINGS_UX.md](PRESETS_AND_SETTINGS_UX.md) | Registry + UI |

**Gate:** Each modality scorecard “target” column ≥4/5 for shipped family on sim/replay.  
**Quality:** Expanded cards match modality scorecard UX; preset editor validates before apply.

**Hardware validation (Phase 8):** Bench parity pass flips `provisional` → `hardware_validated` when devices available.

---

## Phase 5 — Pose + kinematics (8–12 weeks)

| Item | Research source | Deliverable |
|------|-----------------|-------------|
| MKV segment decoder | [UROLOGYMOCAP_MERGE_RESEARCH.md](UROLOGYMOCAP_MERGE_RESEARCH.md) | video loader |
| Pose job + registry | [ANALYSIS.md](../ANALYSIS.md), [POSE_HAND_TEACHER_POLICY.md](POSE_HAND_TEACHER_POLICY.md) | Phase D |
| Hand native 21-pt (D+) | hand bake-off on 5714/6517/6612 | optional output |
| Kinematics Tier A | [KINEMATICS_PIPELINE.md](../KINEMATICS_PIPELINE.md) | Phase D2 |
| Anatomical mapping editor | [ANALYSIS_WORKBENCH.md](ANALYSIS_WORKBENCH.md) | Mappings panel |

**Gate:** Pose job on sealed 2-cam session; kinematics parquet validates against registry schema.

**Blocked:** Kobayashi Tier B until `furs_ergonomic_metrics` license resolved.

---

## Phase 6 — ML bundle + eval (6–8 weeks)

| Item | Research source | Deliverable |
|------|-----------------|-------------|
| ML bundle job | [ANALYSIS.md](../ANALYSIS.md) Phase E | `ml_bundle/` |
| Eval reports | Phase F | `eval/` |
| ML bundle UI | [ANALYSIS_WORKBENCH.md](ANALYSIS_WORKBENCH.md) | dialog + gallery |

**Gate:** End-to-end radar→teacher window export on sim+pose session.

---

## Phase 7 — Extension modalities (as needed)

Priority from [EXTENSION_MODALITIES.md](EXTENSION_MODALITIES.md):

1. Force plate honest schema (`force.frame/1`)  
2. Audio sync path  
3. Egocentric second camera slot  
4. TTL/DAQ events  
5. Depth / gaze / instrument (spike-driven)  

Each requires [ACQUISITION_PLUGIN_CONTRACT.md](ACQUISITION_PLUGIN_CONTRACT.md) checklist + scorecard.

---

## Phase 8 — Hardware validation + documentation polish (last)

| Item | Source |
|------|--------|
| EMG/IMU/radar bench parity | [VENDOR_SPIKE.md](../VENDOR_SPIKE.md) — flip `provisional` → `hardware_validated` |
| Operator manual | [OPERATOR_AND_PLUGIN_DOCS_OUTLINE.md](OPERATOR_AND_PLUGIN_DOCS_OUTLINE.md) |
| Plugin author guide | same |
| Performance soak automation | [PERFORMANCE_SLO_RESEARCH.md](PERFORMANCE_SLO_RESEARCH.md) |

Documentation draft starts in Phase 0; Phase 8 completes manual + hardware sign-off.

---

## Effort summary

| Phase | Calendar (1 FTE eng) | Risk |
|-------|----------------------|------|
| 0 Foundation | 1–1.5 mo | Low |
| 1 Review | 1 mo | Low |
| 2 Plugins | 1.5–2 mo | Medium |
| 3 Workbench | 1.5 mo | Medium |
| 4 Modality depth | 2–3 mo parallel | Replay fixture quality |
| 5 Pose/kin | 2–3 mo | GPU + merge |
| 6 ML/eval | 1.5–2 mo | Data availability |
| 7 Extensions | ad hoc | Replay/sim first |
| 8 HW validation | when devices available | **Not on critical path** |

**Total to “full platform V1”:** ~12–18 months elapsed with parallel work; ~9–12 months critical path.

---

## Explicitly deferred (research agreement)

- Web UI rewrite  
- Overlay inpaint salvage product path  
- Multi-radar hardware sync claims  
- Auto cloud upload  
- ProPainter-class video salvage  

---

## Research document index

All paths under `docs/design/research/` — see [README.md](README.md).

---

## Next actions (immediate)

1. Phase 0: design tokens, SessionTimeline, Preferences, honesty banners.
2. Phase 2 (parallel): analysis manifest registry.
3. Ingest vendor **replay fixtures** from downloadable sample exports where available (no bench required).

**Deferred:** hand bake-off ([PROGRESS.md](PROGRESS.md)); hardware bench validation (Phase 8).
