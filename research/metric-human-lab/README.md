# Metric Human Lab

**Open-source, geometry-first research infrastructure for reconstructing human-shaped 3D volumes from ordinary images and independent physical evidence.**

> **Status: Early engineering prototype.** It is **not** currently an accurate zero-measurement body scanner. The provided benchmark uses known camera poses, known synthetic metric scale and procedurally generated geometry. The photo mode estimates poses and scale using explicit, strong assumptions. It produces a *hypothesis*, not fabrication-grade truth.

## Why this exists

The intended architecture is a collection of independent evidence-producing vision models (segmentation, landmarks, depth, camera geometry, anatomical priors), connected by an explicit geometric optimizer. It does **not** rely on a diffusion model imagining a person.

The fundamental invariant is that a visually plausible avatar does not establish accurate real-world size. In an uncalibrated monocular photograph, global scale is not identifiable. Future inference can offer *estimates with calibrated uncertainty*, not guaranteed dimensions. This research lab is designed to measure that gap, not hide it.

## What's implemented

- Voxel visual-hull reconstruction from calibrated multi-view binary masks, with robust weighted view support.
- Optional **metric** depth free-space carving, which may not be fed uncalibrated relative depth.
- Separate relative-depth-to-metric calibration from at least three independent surface anchors, with regression residual checks.
- Projective and orthographic camera model serialization.
- Multi-view 2D landmark triangulation with degeneracy checks and reprojection error.
- Synthetic figure and exact camera-view render benchmark, 1/2/4/8 view ablation, 3D IoU, surface Chamfer, largest-component cross section and bounding-box errors.
- Import/export test harness for watertight **known-unit** meshes (the operator supplies mesh/source rights; no scans distributed).
- Photo ingestion via alpha/masks, preliminary GrabCut or separately inferred SAM2 masks, with optional view angles, torso-aware image centering and optional known height.
- Optional locally executing SAM2.1 Tiny segmentation and Depth Anything V2 Small relative-depth model adapters, each with source hashes and explicit non-metric provenance (weights downloaded separately, not bundled).
- Robust perspective PnP camera recovery from matched 3D anatomical/template points and 2D image landmarks, with outlier/degeneracy rejection (not intrinsic or scale recovery).
- Explicit unknown-scale provenance, photo-mode assumption labels, leave-one-view-out stability diagnostics, and separate body-accuracy flags.
- Optional supplied blend-shape anatomical prior fitting against silhouette IoU + 3D landmark constraints, **plus an opt-in directly rendered metric-depth residual** (no restricted priors bundled).
- **SHA-256-pinned MakeHuman CC0 core-asset fetcher** and index-preserving OBJ/`.target` converter into the prior contract, with separate positive and negative measurement morphs and source-file provenance. Real anatomical **template**, not observed person anatomy.
- Independent CPU **oracle metric-depth renderer** and known-camera silhouette-vs-depth ablation harness, with all claim boundaries explicit.
- Hard depth-receipt binding to source maps, independently supplied metric depth anchors and verified output bytes. A reconstruction manifest can no longer silently reinterpret an arbitrary `.npy` as calibrated physical depth.
- Silhouette-boundary sensitivity volumes and section-perimeter perturbation reports. This is diagnostic stability, **not calibrated uncertainty**.
- Separate capsule/kinematic motion harness for imported rigid equipment, approximate collision diagnostics, and one-axis fit-offset experiments. Can optionally size a **generic** skeletal proxy from the reconstructed voxel volume (not an inferred validated rig).
- OBJ, GLB, compressed occupancy, JSON provenance/measurements, fully self-contained interactive synthetic demo.
- V0.3 adds local anatomical camera-view planning, direct triangle-plane measurements, controlled shift-robustness experiments and subject-disjoint dataset auditing (real-person accuracy still unvalidated).
- Withhold an existing camera view from anatomical fitting for **predictive out-of-sample image checks**. Held-out foreground reprojection and optional separately calibrated metric-depth residuals are reported; neither establishes real 3D dimensional truth.

## New geometry/validation tools (v0.3 research checkpoint)

**Choose complementary camera directions** on a user-provided body-shape prior:

```bash
python -m metric_human plan-views \
  --prior demo/parametric-prior/licensed-free-procedural-prior.npz \
  --candidates 8 --select 2 --out outputs/view_plan.json
```

The planner estimates *local geometric observability*, not camera poses for
unknown photographs, absolute-scale certainty or real-subject accuracy.

**Reproduce the held-out synthetic experiment** using a procedural body prior:

```bash
python -m metric_human bench-view-planning \
  --prior demo/parametric-prior/licensed-free-procedural-prior.npz \
  --samples 6 --seed 17 --select 2 --candidates 8 \
  --out outputs/clean_holdout.json
python -m metric_human bench-view-planning \
  --prior demo/parametric-prior/licensed-free-procedural-prior.npz \
  --samples 6 --seed 17 --select 2 --candidates 8 --mask-shift-px 2 \
  --out outputs/shifted_holdout.json
```

**Measure an existing metric mesh directly**, with independent closed-loop
surface contours rather than voxel-staircase perimeters:

```bash
python -m metric_human measure-mesh --mesh existing_person.glb --units m \
  --height-fractions .5 .7 .85 --out outputs/sections.json
```

These are *horizontal geometric sections*, not automatically named anatomical
circumferences. When a mesh is inaccurate or its scale is inferred without a
metric anchor, its perimeters inherit those errors.

**Audit paired data and identity-disjoint evaluation splits** without copying
or bundling biometric images/scans:

```bash
python -m metric_human audit-dataset \
  --manifest /path/to/dataset/dataset.json --out outputs/dataset_audit.json
```

See [Dataset admission](docs/DATASET_ADMISSION.md) and
[New experiment results](docs/RESEARCH_RESULTS_2026-10-15.md).

### Predictive unseen-view checking (no training-image leakage)

When a mask manifest contains individually labeled views, preserve one of the
views completely outside anatomical shape optimization:

```bash
python -m metric_human fit-prior --input camera_manifest.json \
  --prior anatomical_prior.npz --out outputs/holdout \
  --holdout-label side --maxiter 30
```

The `prior_fit_report.json` records training-view and independent withheld-view
reprojection, and optional metric-depth residuals in millimeters only if the
manifest supplies independently calibrated and receipt-verified depth evidence.
The held-out camera is not used to fit shape or triangulate 3D joint anchors.
Validation of a silhouette on one withheld view cannot prove unseen surface
geometry, metric scale, or fit to the actual individual. A controlled fixture
illustrates a *perfect* frontal silhouette despite a wrong chest depth; the
withheld side silhouette detects the error.

### Experimental reconstruction fitting modes

For `fit-prior`, the default is the existing pixel-IoU loss. Optional
`--silhouette-loss-mode profile` discards global pixel translations but can
lose enough other information to **worsen** the shape fit. An experimental
`--silhouette-loss-mode coarse_to_fine` runs a profile fit, estimates bounded
per-view centering, then refines with pixel-IoU. It improved *two* shifted-mask
synthetic cases, not enough for a reliability claim. Opt-in `--prealign-radius-px`
and `--alignment-radius-px` are research ablations, not verified camera calibration.

## Installation

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
python -m pip install -e '.[test,demo]'
python -m pytest -q
```

Python 3.10+; CPU-only for all implemented paths. No API keys or neural-network weights required.

## Run the reproducible synthetic benchmark

```bash
python -m metric_human bench --out outputs/synthetic --views 1 2 4 8 --resolution 75 --loo
python -m metric_human reconstruct --input outputs/synthetic/reproducible_input.json --out outputs/replayed
python -m metric_human make-viewer --benchmark-dir outputs/synthetic
```

Open the included `demo/viewer.html` locally for an interactive comparison of known procedural truth and 1/2/4/8 view reconstructions. Everything is embedded, including the Plotly JavaScript. The demo geometry does not represent any real person.

## Run on your photographs — experimental

Capture 4 or 8 images **in the same standing pose**. The user rotates by evenly spaced angles (0°, 90°, 180°, 270° for 4 photos), keeping camera level, similar framing and distance. Prefer tight, non-occluding clothing, even light and a neutral background. Edited foreground silhouettes give better results than automatic GrabCut.

```bash
python -m metric_human prepare-photos --images front.jpg right.jpg back.jpg left.jpg \
    --angles-deg 0 90 180 270 --out outputs/session --segmentation grabcut
python -m metric_human reconstruct --input outputs/session/reproducible_input.json \
    --out outputs/body
```

For better segmentation, provide full-size black/white masks with `--masks front.png right.png back.png left.png` (same image order). PNGs with transparency can be passed with `--segmentation alpha`.

**No measurement is required**, but the default `--assumed-height-m 1.70` is a numerical prior used to assign a provisional scale. It is not derived from your photographs or from a trained height estimator. Model output in meters is therefore **not validated as the person's actual dimensions**. You may optionally supply `--known-height-m 1.77` to anchor scale; even that does not verify shoulder, torso, or limb contours. The camera solver here does **not** recover full perspective calibration from ordinary photographs.

### Optional local vision-model inference (requires a model download)

The source distribution bundles no neural weights. These two *optional*
adapters use small, Apache-2.0-licensed Hugging Face checkpoints. Install the
vision extra only when you want to download and run inference locally:

```bash
python -m pip install -e '.[vision]'
# Segmentation: one rough/full bounding box per photo, in source-image pixels.
# If --boxes-json is absent, a weak GrabCut bounding-box proposal is attempted.
python -m metric_human segment-sam2 --images front.jpg side.jpg back.jpg \
    --boxes-json person_boxes.json --out outputs/neural-masks
# person_boxes.json: {"boxes":[[40,20,600,980],[35,18,610,975],[42,25,605,990]]}
python -m metric_human prepare-photos --images front.jpg side.jpg back.jpg \
    --masks outputs/neural-masks/mask_00.png outputs/neural-masks/mask_01.png outputs/neural-masks/mask_02.png \
    --out outputs/photo-evidence
python -m metric_human reconstruct \
    --input outputs/photo-evidence/reproducible_input.json --out outputs/photo-body
# Independent relative depth, NOT physical meters:
python -m metric_human infer-depth --images front.jpg side.jpg back.jpg \
    --out outputs/relative-depth
```

**Status of neural adapters:** The interface and provenance are unit-tested using
injected deterministic predictors. Separately, an RTX 4070 smoke test ran
SAM2.1 Tiny and Depth Anything V2 Small through Transformers 4.57.6 and CUDA
PyTorch 2.11.0. The synthetic figure mask scored IoU 0.9893 against its trivial
synthetic target; the depth adapter returned a finite 512×512 **relative** map.
This is an operational integration check, not real-photograph reconstruction
accuracy, and the checkpoints are not bundled. The SAM2 prompt is *not* a validated
human detector; inspect all masks. A relative-depth `.npy` must **never** be
put directly in `depth_m`; follow the independent calibration procedure below.

Suggested checkpoints: [SAM2.1 Hiera Tiny](https://huggingface.co/facebook/sam2.1-hiera-tiny)
and [Depth Anything V2 Small](https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf).
Use `--revision <exact-commit>` for pinned experiments and review licenses
before substituting any model IDs.

### Optional camera PnP from independently matched anatomical/model landmarks

When you have at least six noncoplanar 3D template/body landmarks and matching
2D image landmarks *and known intrinsics*, estimate the camera pose:

```bash
python -m metric_human calibrate-pnp --anchors-json landmarks.json \
  --width 1024 --height 1536 --fx 1250 --fy 1250 --out outputs/camera-fit.json
```

`landmarks.json` has `points_world:{"shoulder":[x,y,z],...}` and
`pixels_by_label:{"shoulder":[u,v],...}` with matching labels. The solver
rejects degenerate matches and outliers. This can replace *assumed* camera pose
in future workflows, but it does not independently recover camera intrinsics,
real body dimensions or any physical scale missing from its input points.

### Feed depth-model output safely

A relative-depth estimator, even one that makes plausible heatmaps, does not produce proven metric camera depths. First obtain independently calibrated **surface** depths at 3+ pixels (not internal skeleton-joint depths) and store them in a JSON file:

```json
{"anchors":[
  {"u": 105, "v": 42, "camera_z_m": 2.52},
  {"u": 116, "v": 100, "camera_z_m": 2.60},
  {"u": 92, "v": 159, "camera_z_m": 2.75}
]}
```

```bash
python -m metric_human align-depth --relative-npy relative_depth.npy \
   --anchors-json anchors.json --out metric_depth.npy
```

If the independent-anchor residual exceeds the configured `--max-rmse-m` (default 5 cm), this step rejects the depth map. Add the resulting `.npy` to a view in `reproducible_input.json` as `"depth_m":"metric_depth.npy"`; the reconstructed result is then constrained by independently calibrated free-space evidence.

## v0.2: reproducible anatomical-prior integration

MakeHuman's *core mesh and targets* are CC0 according to its official asset license; MakeHuman **application code** is AGPL and is not used here. This command explicitly downloads **seven asset-data files only** at pinned commit `1f508f6083b2f823dab15de924b3bde72e08d77c`, validates each SHA-256 digest (including offline cached versions), and converts the base mesh and six paired targets for shoulder distance, chest circumference and thigh circumference:

```bash
python -m metric_human fetch-makehuman-cc0 --out-dir outputs/anatomical-prior
# repeat with --offline to prove exact cached bytes can be reused without internet
```

The result `makehuman_cc0_body_prior.npz` includes the corresponding 19,158-vertex template and signed deformation basis. Each parameter can range from -1 (MakeHuman decreasing target) to +1 (increasing target). **No claim of learned body-shape inference is implied.** Try it with a calibrated silhouette manifest:

```bash
python -m metric_human fit-prior --prior outputs/anatomical-prior/makehuman_cc0_body_prior.npz \
  --input outputs/session/reproducible_input.json --out outputs/anatomical-fit
```

If you already possess appropriately licensed `.obj` + `.target` files, use `import-makehuman --base-obj ... --positive-target shoulder=... --negative-target shoulder=... --out prior.npz`. The documented `--native-unit-m` conversion defaults to 0.1 m per native asset unit; its provenance is explicitly **assumed** and must be validated separately for physical measurement.

## v0.2: known-depth ablation and input sensitivity

```bash
python -m metric_human bench-depth --out outputs/depth-oracle \
  --resolution 46 --views 1 2 4 8 --tolerance-voxels 0.65
python -m metric_human mask-stability \
  --input demo/reproducible_input.json --out outputs/mask-sensitivity \
  --radius-px 4 --section-heights-m 1.10 1.32
```

`bench-depth` computes camera-forward depth directly from the known synthetic source mesh; it is **not** a monocular-neural-depth test. Eight-view synthetic IoU rose from ~0.866 silhouette-only to ~0.959 using exact source depth at resolution 46; this says nothing about real-photograph height or measurement accuracy. `mask-stability` provides eroded/nominal/dilated silhouette reconstructions to expose how much the result depends on a chosen ±pixel boundary perturbation. They are *not* guaranteed bounds on body dimensions or confidence intervals.

### Depth evidence file provenance

`align-depth` now writes `metric_depth.alignment.json` containing exact SHA-256 hashes for the relative-depth array, independent surface-depth anchor JSON, and produced metric array. For an ordinary reconstruction manifest, a depth-equipped view must specify both:

```json
{"depth_m":"metric_depth.npy","depth_alignment_receipt":"metric_depth.alignment.json"}
```

A malformed receipt or a byte-changed `.npy` fails closed. *Only* controlled synthetic experiments can instead declare `"depth_evidence_source":"synthetic_known_reference_mesh"` with synthetic grid-scale provenance. This check guarantees file identity, **not correct physical anchors**.

## Evaluate on known-scale human meshes

```bash
python -m metric_human bench-mesh --mesh /path/to/licensed_scan.obj --units mm \
  --out outputs/scan-benchmark --resolution 75 --views 1 2 4 8
```

The mesh must be watertight, **Z-up**, and have known length units. Bench-mesh centers it and renders controlled orthographic masks with *known camera poses*. Results include voxel IoU and errors compared to a voxelized version of the reference. The synthetic-view benchmark does **not** validate camera-pose-free reconstruction on real photographs. The program records the exact source file hash and doesn't bundle your mesh in the source distribution.

## Files and formats

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for data contracts, and [docs/VALIDATION.md](docs/VALIDATION.md) for validity gates and benchmark interpretations.

### Fit a properly licensed parametric body prior

Supply `prior.npz` containing `vertices_m` (N×3), `faces` (F×3), `shape_deltas_m` (P×N×3), plus JSON-string fields `parameter_names_json`, `landmark_vertex_ids_json`, and `source`. See `Prior.save()` in `src/metric_human/prior.py` to generate this format. Then:

```bash
python -m metric_human fit-prior --prior /path/to/permitted_prior.npz \
  --input outputs/session/reproducible_input.json --out outputs/shape-prior-fit
```

This explicit optimizer weights silhouette agreement and any metrically triangulated 3D landmarks recorded in the manifest. **v0.2 also supports direct metric-depth residuals** for regions that can look identical in silhouette but differ in front/back thickness. Only use this with independently calibrated, file-bound metric surface depth:

```bash
python -m metric_human fit-prior --prior outputs/anatomical-prior/makehuman_cc0_body_prior.npz \
  --input outputs/independently-calibrated-views/reproducible_input.json \
  --depth-weight 0.1 --out outputs/anatomical-depth-fit
```

A test of a deliberately hidden torso-depth parameter can be replayed offline:

```bash
python examples/recover_hidden_depth.py outputs/shape-identifiability
```

On this known synthetic box, the front-view silhouette-only optimizer predicts a shape coefficient of **0.0000** while a second run with exact reference-mesh depth recovers **0.69993** against the true **0.70000**. Camera pose, scale and depth are supplied as ground truth; this is *not* AI reconstruction from a real photograph, but it verifies the solver uses depth information that the silhouette does not contain.

A template is not automatically a valid person-specific body; priors may be wrong, and no learned training weights are bundled. A procedural self-test prior is included under `demo/parametric-prior/`.

### Separately test imported equipment during a preset movement

```bash
python -m metric_human test-gear --mesh my_armor.obj --gear-units mm \
  --anchor-joint chest --offset-m 0.22 0 0.04 \
  --optimize-axis 1 0 0 --out outputs/gear-test.json
```

This stage currently uses a **generic procedural skeletal capsule proxy**, not the reconstructed person's body. It supports a standard arm-raising clip and an approximate gear offset sweep. Results do not establish safe fitting or comfort, and intersections between entire triangle surfaces can be missed by the sampled collision method. It is a separate interface prototype while body reconstruction is being validated.

If you have an experimental body reconstruction, a generic skeletal proxy
can be **scaled to its observed voxel bounding box** before testing equipment:

```bash
python -m metric_human test-gear --mesh my_armor.obj --gear-units mm \
  --anchor-joint chest --offset-m 0.22 0 0.04 \
  --body-npz outputs/photo-body/reconstruction.npz \
  --body-input outputs/photo-evidence/reproducible_input.json \
  --out outputs/motion/body-scaled-clearance.json
```

This is a deliberately limited bridge between independent systems. Its joint
centers and capsule radii are **proportional guesses**, not anatomically derived
from the wearer's images. It cannot certify real fit or injury-free range of
motion. `demo/body-integration/` includes a reproducible procedural example.

`reconstruction.glb` and `.obj` use meters in the declared frame, but human dimensions should **not** be trusted unless independently validated. `reconstruction.npz` includes voxel occupancy/support fraction. `report.json` includes dimensions, observation reprojection fit, model assumptions, and scale provenance.

## What remains unsolved

- Reliable neural segmentation and depth on messy RGB photos **is not yet measured**; optional model adapters are implemented but no accuracy validation of checkpoint inference has been performed. Human landmark detection and unprompted subject localization are still missing.
- Self-calibrating camera geometry and **absolute scale estimation** without a manual measurement or external reference; a pinned generic MakeHuman prior is now importable, but has not been tested as a calibrated person-specific solution.
- Physiologically realistic, person-specific shapes from a single or few views; visual hull overfills hidden concavities and loose garments.
- Fully automatic personalized rigging; confidence calibrated against diverse external 3D scans (parameterized fitting and silhouette-boundary sensitivity now exist, but do not establish learned anatomy or probabilistic uncertainty).
- Validation of circumference error (and local contact clearance) on genuinely independent subjects captured with ordinary cameras.
- Personalized deformable-body motion, wearable-to-body attachment mechanics, gear/gear collisions and production-grade fabrication tools (only a capsule-proxy motion test exists).

Those are the central research goals; passing the provided synthetic benchmark must **not** be conflated with solving them.

## Open-source / privacy commitments

This repo's original source is MIT. No real-person photographs, commercial datasets, restricted model checkpoints, or imported scan geometry are included in this release. By default processing is local and no images are uploaded. If you integrate an external model, check its weight license separately from source-code licensing. Do not commit private subject images or licensed 3D datasets to the repository.

See [docs/DEPENDENCY_RIGHTS.md](docs/DEPENDENCY_RIGHTS.md) for evaluated options and third-party terms.

## Research update: calibrated two-view geometry without entered camera angles

The experimental two-view module adds a **relative-pose estimator**, not a
person-specific metric reconstruction model. It estimates camera orientation,
translation **direction**, and sparse 3D feature coordinates from at least 12
independently matched static features and **known camera intrinsics**.
Camera 1 is fixed at the origin and the inferred separation is 1 *arbitrary*
unit, never 1 meter. This global scale ambiguity remains, even with excellent
reprojection agreement.

For image-derived features, foreground masks are **required**. Otherwise a
stationary camera watching a turning person could inadvertently match the
background and recover the wrong camera/subject motion. Smooth skin, deforming
clothes, and changing body poses may not provide valid static correspondences.
The adapter rejects insufficient matches rather than silently substituting a
pose guess.

```bash
python -m metric_human match-features \
  --image-first front.png --image-second diagonal.png \
  --mask-first front-mask.png --mask-second diagonal-mask.png \
  --out outputs/sift-pairs.json

python -m metric_human calibrate-two-view \
  --correspondences-json outputs/sift-pairs.json \
  --width 960 --height 720 --fx 920 --fy 920 \
  --out outputs/relative-cameras.json
```

These commands also accept externally measured matching points supplied as
`{"pixels_first":{"feature1":[u,v],...},"pixels_second":{...}}`.
The pose solver performs essential-matrix RANSAC, robust epipolar refinement,
cheirality/triangulation checks, reprojection checks, parallax gating, and a
near-planar homography ambiguity check. It deliberately refuses low-parallax,
planar, repeated, outlier-dominated, or degenerate matches.

**Not yet integrated into automatic photo reconstruction:** The recovered
cameras/landmarks use an arbitrary similarity frame; `prepare-photos` still
uses its separately documented assumptions. Any metric body-fit pipeline must
first resolve units, static correspondence, and consistent body coordinates.
There are no real-person accuracy claims associated with this addition.
