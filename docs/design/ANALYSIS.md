# Offline Analysis

Post-capture science tooling. Opens a sealed (or recovered) `.mmsession`, writes
derived products under `processing/jobs/`, and never touches raw streams.

Pinned companion to the product notes in
[`FUTURE_ANALYSIS_NOTES.md`](../../docs/spec/FUTURE_ANALYSIS_NOTES.md).

## Constraints

1. No daemon RPCs, no worker imports, no analysis during `RECORDING` / `ARMING`.
2. Raw is immutable: never rewrite MCAP/MKV/`sources/**`; only create under
   `processing/jobs/`.
3. Native rates are preserved. Any common-axis resample is an explicit
   `AnalysisGrid` recorded in the job manifest (source streams, rate, method,
   params).
4. Gaps are first-class. Feature jobs use `gap_policy` of `mask` (default),
   `split`, or `fail`. Silent interpolation across a DISCONNECT is forbidden.
5. Dual-radar membership from `arrays.json` is labeled **software coordinated** —
   never a hardware-sync claim.
6. Radar host-arrival timing uncertainty is stated on QC and radar figures.
7. Sample rate and units come from `StreamDescriptor` (`nominalRateHz` /
   `nominal_rate_hz`, `units`). A missing rate **fails the job**; the suite
   never invents a timebase by spacing samples between batch timestamps.
8. Pose overlays (Milestone 12) land under `processing/…/pose/` only; source
   MKV is never rewritten.

## Package layout

```text
<session>.mmsession/processing/jobs/<job_id>/
  job_manifest.json          # capture.analysis_job/1
  params.json
  features/                  # Phase B+
  derived/                   # Phase B+ (radar RD maps, etc.)
  figures/                   # Phase B+
  pose/                      # Phase D / M12
  kinematics/                # Phase D2
  ml_bundle/                 # Phase E
  eval/                      # Phase F
  reports/qc.json
  reports/qc.html
  logs/job.log
```

`job_id` format: `YYYYMMDDTHHMMSSZ_<first 8 hex of params_digest>`.

Schema: [`schemas/session/jsonschema/analysis_job.schema.json`](../../schemas/session/jsonschema/analysis_job.schema.json).

## Memory / streaming

| Stream | Rule |
|---|---|
| Radar FMCW / Doppler | Iterator only — never materialize a full soak |
| Video MKV | Segment index + sequential decode; never load whole file |
| EMG / IMU | May materialize behind `max_ram_bytes` (default 2 GiB); over budget fails naming the stream |

## Units honesty

Feature columns carry the descriptor's `units` string and `calibrated: bool`.
Radar ADC counts and sim IMU `a.u.` are `calibrated: false`. Feature names must
not imply a physical quantity the device did not provide.

## Provisional defaults

EMG window/envelope/band defaults and IMU still/cadence thresholds are
**provisional** until real Delsys/Xsens data exists. Sim packages prove
implementation correctness (analytic tests); they do not prove physiological
usefulness.

## Library

`libs/python/capture_analysis` — depends on `capture_session` and
`capture_protocol` only. Desktop may import it; daemon/workers must not.

Optional extras: `[analysis]` (numpy/scipy/pandas/pyarrow/matplotlib),
`[analysis-pose]` (opencv-headless, av, plus per-model backends — never
assume MediaPipe-only). Capture CI stays light.

CLI: `tools/run_analysis.py qc|features|plots|all|pose|kinematics|ml_bundle|eval`.

## Pose / mocap model registry (Phase D+)

MediaPipe is **one backend**, not the product. CaptureSuite pose jobs use a
**pluggable registry** whose first catalog is the stack already validated in
[`UrologyMoCap`](../../../UrologyMoCap/) (`pose_models.MODEL_CATALOG`,
`face_models.FACE_MODEL_RUNNERS`, `landmark_fusion.py`).

### Canonical layout

All body backends normalize into a shared paper/MediaPipe-index layout
(`PaperLandmarks` / Kobayashi-compatible indices) so metrics and overlays do
not fork per vendor. Native denser outputs (e.g. whole-body 133, hand 21, face
mesh) may also be stored under `pose/native/<model_id>/` for research.

### Body / whole-body catalog (from UrologyMoCap)

| model_id | Family | Role |
|---|---|---|
| `mediapipe` | MediaPipe | Per-frame pose (IMAGE mode) |
| `mediapipe_smooth` | MediaPipe | VIDEO mode temporal tracking |
| `mediapipe_hands` | MediaPipe | Pose + Hand Landmarker for paper hand indices |
| `yolo11x_pose` | Ultralytics | Large YOLO11 pose |
| `yolov8x_pose` | Ultralytics | YOLOv8-X pose |
| `rtmpose_x` | RTMPose | Body via rtmlib |
| `rtmo_l` / `rtmo_m` / `rtmo_s` | RTMO | One-stage body (L = realtime primary in UrologyMoCap) |
| `vitpose_l` / `vitpose_b` | ViTPose | COCO-25 + detector |
| `dwpose` | DWPose/RTMW | Whole-body performance |
| `rtmw_balanced` | RTMW | Whole-body balanced (hands/wholebody realtime pick) |

Unavailable / deferred backends stay listed with reasons (mmpose_full,
alphapose, sapiens, vitpose_h, sam_3d_body, …) — same honesty as
`UNAVAILABLE_LIBRARIES` in UrologyMoCap — rather than silently omitted.

### Face catalog (existing UrologyMoCap; more TBD)

`mediapipe_pose` (coarse face from pose), `mediapipe_face`,
`mediapipe_face_smooth`, `face_alignment`, `insightface_68`,
`insightface_106`, `dwpose_face`, `rtmo_coarse`, `dlib`, `openface`.

**Hand- and face-specialist expansion** (additional models beyond this list)
is explicitly deferred until a short spike ranks accuracy/latency on lab
surgical/clinical footage. New entries only need: `model_id`, runner, landmark
map into the canonical layout (or a documented native schema), and a
`model_card.json` version pin.

### Fusion

Optional `pose_mode: single | fused` — fused uses region→best-model maps
(`landmark_fusion.py` / regional rankings) so missing landmarks can be filled
from specialists without claiming a single network produced the full set.
Every fused point records its source `model_id` in provenance.

### Job outputs under `pose/`

```text
pose/
  model_card.json          # selected model_ids, versions, device, fusion map
  landmarks.parquet        # canonical layout + session_time_ns + conf + source_model
  native/<model_id>/...    # optional denser native tracks
  overlay.mp4              # never overwrites source MKV
```

### UI / CLI

- CLI: `run_analysis.py pose <package> --model rtmo_l` (repeatable / `--models a,b`)
- Analysis tab: model multi-select from registry (installed backends only);
  unavailable models show install reason, not a crash
- Default for a first CPU-friendly smoke: `mediapipe`; default for GPU lab
  work: `rtmo_l` (+ optional `rtmw_balanced` for hands) — matching UrologyMoCap
  realtime guidance — not MediaPipe-only

### Dependency isolation

Pose backends live behind extras / optional imports (`[analysis-pose]`,
`[analysis-pose-yolo]`, `[analysis-pose-rtm]`, …). Missing a weight or package
fails that model only; QC and non-pose analysis still run.

## Phases

| Phase | Delivers | Status |
|---|---|---|
| A | discover, QC report, job manifest, loader contracts, CLI `qc` | implemented |
| B | Streaming radar loaders, EMG/IMU materialize+guard, features, sync plots, gap masks, analytic tests, CLI `features`/`plots`/`all` | implemented |
| C | Desktop Analysis tab over `jobs.run` (QThread progress/cancel, no daemon RPCs) | implemented |
| D | Segment-indexed video decode + **pose registry** (UrologyMoCap catalog) under `processing/` | planned (M12) |
| D2 | **Kinematics job** → `kinematics.parquet`, angle QC figures | planned |
| E | **ML bundle** — aligned `(radar_window, y_kinematics)` + manifest | planned |
| F | **Eval reports** — radar-only replay vs teacher on held-out sessions | planned |
| D+ | Hand/face specialist spike → add models to registry without schema break | deferred |

Research track mapping: [PROJECT_OUTLINE.md](../../../docs/PROJECT_OUTLINE.md). Kinematic targets: [KINEMATICS_PIPELINE.md](KINEMATICS_PIPELINE.md).

---

## Phase D2 — Kinematics job

Converts Phase D landmarks (and optional IMU) into **Tier A kinematic targets** for ML. Does not rewrite `pose/landmarks.parquet`.

### Inputs

- Completed Phase D job (`pose/landmarks.parquet`, `pose/model_card.json`)
- Optional IMU stream from session package
- Session checkpoints (activity windows) and sync anchors from job manifest
- Params: smooth method, visibility threshold, gap_policy, optional IMU fusion

### Outputs

```text
kinematics/
  kinematics.parquet       # Tier A columns — see kinematics_columns.schema.json
  kinematics_qc.json       # detection rates, masked intervals, teacher_source
  kobayashi_summary.json   # optional session/activity ATD/MS/MA/MR/AFR
  figures/
    angles_<joint>.png
    omega_<joint>.png
```

### CLI (planned)

```bash
python tools/run_analysis.py kinematics <package> --pose-job <job_id> [--imu-fusion]
```

### QC failures

- Missing hips for shoulder angles → mask shoulder columns, warn in QC
- Pose detection rate below activity gate → flag activity in `kinematics_qc.json`
- Missing Phase D job → fail job

Full pipeline spec: [KINEMATICS_PIPELINE.md](KINEMATICS_PIPELINE.md).

---

## Phase E — ML bundle

Builds aligned training examples: **radar input windows → kinematic targets** at a defined analysis grid. Consumes Phase B radar features (or derived RD tensors) and Phase D2 kinematics.

### AnalysisGrid (required in manifest)

Every `ml_bundle` job records one or more grids in `job_manifest.json` → `analysisGrids`:

```json
{
  "gridId": "radar_kinematics_v1",
  "rateHz": 20,
  "method": "sync_anchor_offset + linear_interp_labels",
  "sourceStreams": ["radar.fmcw.primary", "kinematics.teacher"],
  "params": {
    "anchorMechanism": "clap",
    "radarLatencyMs": 45,
    "videoLatencyMs": 33,
    "windowSec": 1.0,
    "windowHopSec": 0.05
  }
}
```

Native stream rates are never silently assumed. Missing `nominalRateHz` on a source **fails the job**.

### Radar input features

Built on Phase B (`capture_analysis/features/`):

| Feature | Shape (typical) | Source |
|---|---|---|
| Range–Doppler map | `(n_range, n_doppler)` per frame | `radar_frame.py` |
| Range profile | `(n_range,)` | FFT magnitude |
| Motion energy | scalar | RD integration |
| Multi-radar | stack or list per `arrays.json` | software coordinated |

Normalization policy (per-session z-score vs global stats) is recorded in `ml_bundle/manifest.json`.

### Window contract

| Field | Description |
|---|---|
| `window_sec` | Radar stack depth (e.g. 1.0 s → 20 frames @ 20 Hz) |
| `target_time` | Center or end of window |
| `y_columns` | Tier A subset from kinematics.parquet |
| `valid_mask` | false if any gap or pose dropout in window |

### Outputs

```text
ml_bundle/
  manifest.json            # capture.ml_bundle/1 — see ml_bundle.manifest.schema.json
  windows.parquet          # index: window_id, session_time_ns, activity_id, fold_hint
  tensors/                 # optional .npy or zarr shards: X radar, y kinematics
```

Schema: [`schemas/ml_bundle/ml_bundle.manifest.schema.json`](../../schemas/ml_bundle/ml_bundle.manifest.schema.json).

### CLI (planned)

```bash
python tools/run_analysis.py ml_bundle <package> \
  --kinematics-job <job_id> \
  --window-sec 1.0 \
  --grid-rate-hz 20
```

### Anatomy maps (Phase E subset)

Editable defaults for muscle → joint → landmark associations (from
[FUTURE_ANALYSIS_NOTES.md](../../docs/spec/FUTURE_ANALYSIS_NOTES.md))
ship as `ml_bundle/anatomy_map.json` when EMG correlation is in scope. Not required
for v1 radar-only upper-limb model.

---

## Phase F — Evaluation reports

Offline evaluation of a trained **RadarKinematicsML** model against teacher kinematics on held-out sessions. Does not modify raw capture.

### Inputs

- `ml_bundle` from held-out sessions (or freshly built windows)
- Model artifact (`model_card.json` + weights / ONNX)
- Optional: re-run teacher kinematics for fresh comparison

### Outputs

```text
eval/
  eval_report.json         # aggregate + per-activity metrics
  eval_report.html
  figures/
    scatter_theta_<joint>.png
    timeseries_replay_<session>.png
  predictions.parquet      # y_hat vs y_teacher per window
```

### Metrics

| Metric | Applies to |
|---|---|
| MAE (deg) | joint angles |
| RMSE (deg/s) | angular velocity |
| Pearson r | AFR, ω on dynamic activities |
| Activity-stratified tables | per `activity_id` from checkpoints |

Baselines recorded in same report: zero-velocity, linear extrapolation, classical RD peak tracker.

### CLI (planned)

```bash
python tools/run_analysis.py eval <package> \
  --ml-bundle-job <job_id> \
  --model ../../RadarKinematicsML/artifacts/<run_id>/model_card.json
```

Training-side eval protocol: [RadarKinematicsML/SPEC.md](../../../RadarKinematicsML/SPEC.md).
