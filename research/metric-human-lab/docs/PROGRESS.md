# Execution checkpoint · 2026-10-15 UTC

**Current state:** Engineering/prototype. Not scientifically validated on real human photographs.

## Completed and verifiable

- Standalone MIT-licensed Python library with camera/projective geometry, multi-view silhouette fusion, metric depth carving, relative-depth calibration, triangulation, mesh export, cross-sectional metrics, synthetic and external-mesh benchmarks, approximate photo preparation, interchangeable blend-shape fitting, and a separate motion/gear-clearance proxy.
- CLI + source-separated evaluation test harness and browser-viewable synthetic 3D demo.
- Synthetic multi-angle reproducibility manifests and explicit provenance; no dataset or real-subject photographs shipped.
- 35 unit/integration tests passing on Python 3.13, runnable without network/API keys or GPU; wheel build succeeds.

## Demonstrated and not demonstrated

Synthetic baseline: 8 known cameras → roughly 0.86 voxel IoU on one procedural mannequin. **Not evidence of millimeter accuracy on a real human.**

Missing: automatic real multi-photo camera poses (PnP with supplied 2D/3D matches is implemented, but does not infer the matches), real independent body-scans/corresponding RGB for ground truth, licensed anatomically rich prior assets, real pretrained-model end-to-end inference/accuracy validation (optional adapters are wired and mock-tested), validated uncertainty, personalized rig + production-worthy motion/armor collision testing.

## Next best engineering step

Integrate independently verified CC0 MakeHuman/OxiHuman parametric body priors, plus robust silhouette and pose landmark likelihoods. Evaluate against withheld external scanned meshes and recalibrate relative-depth evidence against independent camera geometry. Then collect and validate camera poses and absolute-scale predictions on held-out ordinary RGB photos. Do not quietly replace missing physical evidence with arbitrary shape guesses.

## Remote/GitHub state

Source is staged locally as a distributable repository ZIP; it has not been published as a GitHub repository. Do not claim a remote deployment or published release before remote state has been verified.

## Added integration work

- Optional SAM2.1 Tiny segmentation and Depth Anything V2 Small *relative* depth adapters with source hashes, model version fields and explicit non-metric guardrails. Their data contracts were exercised with deterministic mocked models, not actual checkpoints.
- Robust PnP camera recovery from at least six matched noncoplanar 3D/2D points; synthetic tests include pixel noise, a blatant landmark outlier and degenerate all-same-pixel rejection. PnP is not automatic camera inference without 3D correspondences.
- Provisional volume-to-motion-rig bridge (generic skeleton scaled to reconstructed voxel extents); executed end-to-end using procedural reconstruction volume, imported `.obj` pauldron and 25-frame shoulder elevation clip. It is not a measured anatomical rig.
- 35 passing automated tests before release packaging.


## v0.2 independent checkpoint · 2026-10-15

- Added index-preserving MakeHuman `.obj` and sparse `.target` importer, and
  a pinned seven-file MakeHuman **CC0 asset-only** downloader with content-hash
  verification. Supports real independent `-incr` and `-decr` blend targets.
- Added synthetic reference-depth rasterizer and an 8-view oracle-depth
  reconstruction ablation (0.866 silhouette IoU vs 0.959 oracle-depth IoU,
  resolution 46). No human image inference was needed for this benchmark.
- Depth-to-meters calibration now emits SHA-256 receipts binding the input
  relative map, independent metric anchors, and output metric array; CLI
  reconstruction rejects a depth array without a qualifying receipt.
- Added deterministic boundary-perturbation sensitivity reporting for supplied
  silhouettes. Report explicitly distinguishes sensitivity from confidence.
- Separately verified actual RTX 4070 checkpoint execution of SAM2.1 Tiny
  and Depth Anything V2 Small; no real human/photo accuracy validation.
- **51 unit/integration tests pass** before final packaging and release audit.
- Remaining core blocker: absolutely scaled and anatomically accurate shape
  from uncontrolled real RGB with matched, licensed 3D ground truth. The
  parametric prior has not been trained or validated against real subjects.


### Additional validated depth-shape experiment

`demo/shape-depth-identifiability/report.json` records a geometric negative
control: with the frontal silhouette unchanged, the prior estimator returns a
0.0 torso-depth coefficient; with the same view's oracle surface depth, it
recovers 0.699929 vs known 0.7. This establishes that the added optimizer
actually consumes dimensional evidence that its silhouette term lacks. It does
not demonstrate monocular metric depth or real-human anatomical inference.


## v0.3 continuation checkpoint · 2026-10-15

- Camera-view observability planner uses multi-parameter silhouette sensitivity,
  determinant-based greedy selection and machine-readable information diagnostics.
- The independent synthetic prior's six held-out coefficient sets showed 0.779
  mm mean vertex error for two planned diagonal views versus 5.401 mm for
  front/rear views **only with oracle cameras and clean masks**.
- Simulated ±2px mask translation raised those errors to 9.179/9.038 mm. A naive
  prior-centering correction made results worse (15.848/15.723 mm); keep this
  negative control and do not recommend that method as established.
- A 24-row translation-invariant mask descriptor maintained exactly the same
  numerical score under those pixel shifts, but fit accuracy degraded. A
  coarse-to-fine variant gave 1.566 mm mean error for the selected view pair on
  **only two** synthetic targets; not yet a validated improvement.
- Direct mesh sections avoid voxel perimeter discretization; a cylinder test
  agrees with analytic circumference within 0.2 mm, only for known geometry.
- Licensed external scan/photo manifest audit and subject-disjoint splits added.
- 70 deterministic tests pass; photo-only absolute scale and realistic body
  accuracy remain unvalidated. Training or evaluating on real paired scan
  photographs is the highest-value next step; some sources are research-only.

### v0.3.0 receiving (2026-10-15)
- Implemented and independently exercised holdout-view testing that excludes validation masks and their landmarks from fitting.
- Image-domain held-out frontal-depth / side-mask controls reveal hidden thickness errors despite perfect front silhouette fit.
- A successful image reprojection is not independent metric 3D truth. No real-person measurement validation exists.
- Existing GitHub Actions workflow configuration intentionally omitted from this packaged release; local pytest is the verified test surface.
