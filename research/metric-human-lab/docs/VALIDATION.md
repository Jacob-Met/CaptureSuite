# Scientific validity gates

## What the prototype tests

The procedural benchmark uses ellipsoid/capsule ground-truth geometry, rasterizes its silhouette from *known, evenly spaced, orthographic cameras*, reconstructs the visual hull and compares at identical physical coordinates.

Recorded checks:
- 3D voxel intersection-over-union against known procedural occupancy.
- Symmetric mean surface nearest-neighbor Chamfer in mm.
- Error in axis-aligned width, depth and height.
- Largest XY cross-section perimeter errors at fixed heights, not named anatomical girths.
- Optional leave-one-view-out classification-change fraction (stability, **not** uncertainty probability).

`demo/benchmark.json` contains the measurements. In the initial 75-high-resolution configuration, eight views yielded 0.8591 voxel IoU, about 7.8 mm average surface distance and about 42.8 mm largest slice-perimeter error at z=1.32 m. This is a **single simple procedural figure**, not clinical accuracy.

## Additional v0.2 geometric evidence

A controlled analytic/procedural figure with source mesh rendered by an explicit
camera-Z triangle rasterizer and known orthographic cameras was evaluated at
resolution 46 with 1/2/4/8 views. The IoU results (silhouette-only → exact
reference-depth carving) were:

| Views | Silhouette IoU | Oracle-depth IoU |
|---:|---:|---:|
| 1 | 0.156 | 0.246 |
| 2 | 0.156 | 0.613 |
| 4 | 0.737 | 0.852 |
| 8 | 0.866 | 0.959 |

This is an ablation under perfect camera calibration, synthetic physical scale
and *oracle* metric surface depth. It does not measure Depth Anything model
performance or the accuracy of the proposed no-measurement body-scanning system.
Full machine-readable outputs: `demo/depth-oracle/depth_ablation.json`.

An independent four-pixel segmentation-boundary sensitivity experiment on the
original 8-view procedural benchmark produced 3,740 eroded, 6,500 nominal and
11,126 dilated occupied voxels; apparent largest-slice perimeter spread at
Z=1.10m was ~545mm. This is an **algorithmic instability diagnostic**
with deliberately exaggerated mask uncertainty, not an actual error interval
or expected error for human scanning. File: `demo/sensitivity/sensitivity_report.json`.

The official MakeHuman base mesh and six paired measurement targets were
separately retrieved at the pinned historical commit and matched known SHA-256
checksums. The base asset contains 19,158 OBJ vertices and has ~1.695m nominal
height under assumed 0.1m/native-unit conversion. It is a **template, not a
real person's 3D scan**; it does not validate user-specific reconstruction.
The importer is unit-tested on independent toy fixtures; the full official
asset download/integration is operator-invoked, not automatically executed by CI.

A separate GPU operational test of SAM2.1 Tiny and Depth Anything V2 Small on
an RTX 4070 completed; segmentation IoU 0.9893 on a deliberately simple
synthetic figure, and a finite 512×512 relative depth map. A Transformers
SAM2 model configuration warning was observed; these are **not** accepted
as metrics of real-human photo segmentation, metric depth or body shape.

## Synthetic identifiability counterexample

`examples/recover_hidden_depth.py` generates a known front-facing cuboid whose
front silhouette is exactly insensitive to its front/back thickness morph. With
its true coefficient set to 0.7, silhouette-only fitting returns approximately
0.0, while a direct known-metric-depth residual yields 0.699929 in a controlled
camera/scale experiment. This is an example of **new information brought by
another evidence modality**, not a learned metric-depth model evaluation.

An independent exact perspective projection invariance test confirms that
simultaneously scaling world coordinates and camera translation cannot be
distinguished from pixel coordinates alone. No zero-measurement metric-scale
claim is supported by the prototype.

## Required future gates for real-world claims

1. Integrate at least one independently licensed body-shape prior (prefer explicitly commercially redistributable assets when bundled).
2. Obtain diverse real scans with sufficiently exact metric coordinates and corresponding RGB viewpoints; fully record permission, clothing and capture conditions.
3. Freeze subject-separated train/validation/test splits with no body identity overlap; evaluate multiple cameras, lighting and clothing types.
4. Reconstruct from RGB photographs where camera intrinsics/extrinsics must be *estimated*, not injected from the renderer.
5. Compare *every* major body length and girth with scan surfaces and tape/laser measurement when available, not simply aggregate mesh IoU.
6. Ablate each independent model (segmentation, depth, multiview, pose, anatomical prior, scale estimator), check for correlated errors and changes across body types.
7. Report scale failure rate for zero-manual-measurement photo sessions; no fabricated absolute metric guarantees.
8. Calibrate credible measurement uncertainty using held-out data. Leave-one-view-out differences cannot substitute for calibrated confidence intervals.
9. Test imported wearables only after body measurement gates are met, with padding/tolerance margins and physical try-on tests.
10. Publish reproducible datasets and pretrained weights *only* when permission actually covers redistribution and downstream use.

## Known physics ambiguities

Any global similarity scaling of an uncalibrated static monocular scene can produce the same photograph. Inferred human height may narrow the estimate distribution but does not mathematically identify absolute scale. Clothing may hide the true body surface. Overlapping front/rear silhouettes do not reveal body concavities. Smooth visually plausible geometry is not evidence of close tolerance.

## Model-adapter and PnP validity

Optional pretrained SAM2.1 Tiny and Depth Anything V2 Small adapters have
mocked-output shape/provenance/negative-path tests, not independently validated
real-image reconstruction accuracy. Never report a relative-depth tensor as
meters. PnP recovers pose *conditioned on* known intrinsic parameters and
corresponding 3D template points; a correct projection of wrong 3D coordinates
is still wrong anatomy. The first-person proportional motion rig similarly
uses a generic template scaled by occupied bounding-box dimensions and carries
no human-joint accuracy guarantee.
