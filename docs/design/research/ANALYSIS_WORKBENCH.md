# Analysis workbench

Research date: **2026-09-01**  
Status: **Research complete** — wireframes and tech choices for implementation.

**Constraint:** No analysis during RECORDING/ARMING ([ANALYSIS.md](../ANALYSIS.md)); raw immutable.

---

## 1. Problem statement

Today Analysis tab runs jobs and opens **external** HTML/PNG. Target: in-app multimodal workbench matching capture depth ([IA_AND_PRODUCT.md](IA_AND_PRODUCT.md)).

---

## 2. Workbench layout

```
┌─────────────────────────────────────────────────────────────────┐
│ SessionHeader (timeline + scope — shared with Review)            │
├────────────┬──────────────────────────────────────┬─────────────┤
│ Job        │ Figure gallery (tabs / grid)         │ Inspector   │
│ palette    │ ┌─────────────────────────────────┐  │ params      │
│            │ │ [sync dashboard | EMG | radar | …]│  │ outputs     │
│ QC         │ │  interactive PyQtGraph / static   │  │ provenance  │
│ Features   │ └─────────────────────────────────┘  │ log         │
│ Plots      │                                      │ job DAG     │
│ Pose       │                                      │             │
│ Kinematics │                                      │             │
│ ML bundle  │                                      │             │
│ Eval       │                                      │             │
├────────────┴──────────────────────────────────────┴─────────────┤
│ Job history strip (compare / re-run / open folder)                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Job palette → commands

| Job | Phase | Inputs | Primary outputs |
|-----|-------|--------|-----------------|
| QC | A | package | `reports/qc.html`, `qc.json` |
| Features | B | scope, gap_policy | `features/**/*.parquet` |
| Plots | B | features | `figures/*.png` |
| All | B | — | combined |
| Pose | D | video streams, model_ids | `pose/landmarks.parquet` |
| Kinematics | D2 | pose job | `kinematics/*.parquet` |
| ML bundle | E | features + kinematics | `ml_bundle/` |
| Eval | F | ml_bundle + held-out | `eval/reports/` |

Jobs disabled until prerequisites exist (DAG — see [ANALYSIS_PLUGIN_ARCHITECTURE.md](ANALYSIS_PLUGIN_ARCHITECTURE.md)).

---

## 4. Plotting stack decision

| Use case | Technology | Rationale |
|----------|------------|-----------|
| Interactive traces (EMG, Doppler, timing) | **PyQtGraph** | Qt-native, zoom/pan, large series |
| Range–Doppler heatmaps | **PyQtGraph ImageItem** or matplotlib imshow in FigureCanvas | RD maps need responsive zoom |
| Sync dashboard (multi-lane) | **PyQtGraph** grid | Replace static PNG |
| Orientation cube | Existing **QPainter** widget (reuse preview) | Consistency with capture |
| Printable reports / batch figures | **matplotlib** ([plots/style.py](../../libs/python/capture_analysis/capture_analysis/plots/style.py)) | Reproducible PDF/HTML |
| Future 3D skeleton | **Qt3D or vtk** (deferred) | Phase D+ overlay review |

**Decision:** Dual stack — **PyQtGraph for interactive Analysis tab**; **matplotlib for job artifacts** written to disk. Share color tokens from [DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md).

---

## 5. Figure gallery

| Feature | Spec |
|---------|------|
| Auto-load | Figures from latest job in scope |
| Tabs | By `outputs[].kind`: `figure`, `feature_parquet`, `derived_npy` |
| External open | Retained for HTML QC report |
| Export selection | PNG/SVG bundle from gallery |
| Caption | Units, gap_policy, job_id, params_digest short hash |

---

## 6. Job inspector

| Panel | Content |
|-------|---------|
| Params | JSON editor with schema validation per job type |
| Progress | Stage + fraction (existing QThread pattern) |
| Outputs | Table: path, sha256, kind, open |
| Provenance | Source hash, analysisGrids (when implemented), model_card |
| Log | Tail `logs/job.log` |
| Compare | Diff params vs previous job_id |

---

## 7. Phase D–F wireframes (ASCII)

### 7.1 Pose job dialog

```
Models: [x] rtmo_l  [ ] rtmw_balanced  [ ] mediapipe  (registry status icons)
Mode: ( ) single  ( ) fused
Video: [camera.sagittal v]
Scope: [from SessionHeader]
[Run Pose Job]
```

### 7.2 Kinematics dialog

```
Pose job: [20260830T142200Z_abc12345 ▼]
Smooth: Savitzky-Golay window [11]
IMU fusion: [ ] optional
Gap policy: [mask ▼]
[Run Kinematics]
```

### 7.3 ML bundle builder

```
Grid: radar_kinematics_v1 @ 20 Hz
Radar features: [RD tensor v] + [motion energy v]
Teacher: kinematics.parquet
Window: 500 ms / stride 100 ms
[Build ML Bundle]
```

### 7.4 Eval viewer

```
Bundle: [ml_bundle job ▼]
Fold: held_out_participants.txt
Metrics: MAE, RMSE, Pearson
[Run Eval] → scatter + residual plots in gallery
```

---

## 8. Anatomical / spatial editors

| Editor | Purpose |
|--------|---------|
| Muscle ↔ channel | EMG analysis |
| Segment ↔ landmark | IMU ↔ pose |
| Radar array floor plan | Spatial context for arrays.json |

Location: Analysis tab sub-panel “Mappings” — loads anatomical + spatial presets.

---

## 9. Report packaging

| Output | Format |
|--------|--------|
| Session QC | HTML (evolve template with design tokens) |
| Printable summary | PDF via matplotlib backend |
| Figure bundle | Zip of PNG + manifest.json |

---

## 10. Implementation files

| Component | Target |
|-----------|--------|
| Workbench shell | `screen_analysis.py` refactor |
| PyQtGraph plots | `widgets_analysis_plots.py` |
| Job dialogs | `analysis_job_dialogs.py` |
| Gallery | `widgets_figure_gallery.py` |

---

## 11. References

- [ANALYSIS_SCOPE_SEMANTICS.md](ANALYSIS_SCOPE_SEMANTICS.md)
- [FUTURE_ANALYSIS_NOTES.md](../../../docs/spec/FUTURE_ANALYSIS_NOTES.md)
- [screen_analysis.py](../../desktop/capture_desktop/screen_analysis.py)
