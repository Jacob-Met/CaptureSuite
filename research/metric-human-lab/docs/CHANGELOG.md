# Changelog

## v0.3.0 — 2026-10-15

- Added anatomical view planning using local signed-distance silhouette sensitivities, numerical information matrices and complementary camera selection.
- Added holdout-coefficient camera-planning benchmark, including deliberate whole-mask shifts and recorded counterexamples where centering heuristics **worsened** results.
- Added direct triangle-plane sectional measurements and independent contour handling, eliminating voxel stair-stepping from the section-measurement operation.
- Added translation-invariant profile, optional bounded 2D nuisance alignment, opt-in coarse-to-fine fitting, and audit diagnostics; all remain experimental.
- Added rights-aware RGB/reference-mesh dataset admission, SHA-256 integrity checks, and subject-disjoint split assignment without including scans or photographs.
- New CLI commands: `plan-views`, `bench-view-planning`, `measure-mesh`, and `audit-dataset`.
- Independent `fit-prior --holdout-label` evaluation so withheld camera masks and landmarks cannot leak into anatomical parameter optimization. Reports predictive silhouette errors and, with verified metric depth, withheld camera-Z residuals.
- Repaired missing `fit-prior --silhouette-loss-mode` CLI option; added nonfinite evidence-weight rejection.
- 76 automated tests passing; no real-person dimensional accuracy or zero-measurement metric scale is claimed.


## v0.2.0 — 2026-10-15

- Import a native MakeHuman CC0 base mesh and sparse anatomical morphs without using MakeHuman app code. Support independent negative and positive morph directions and legacy prior compatibility.
- Operator-initiated downloader for seven SHA-256-pinned official core assets from a historical MakeHuman commit. Caches fail closed on digest mismatches.
- Explicit CPU triangle reference-depth rendering for orthographic and perspective cameras, including analytic z-buffer regression tests.
- Synthetic known-depth ablation: 8-view IoU ~0.866→~0.959 when calibrated cameras and oracle metric depth are supplied. Real-world predictive depth performance unknown.
- Strict reconstructed-depth provenance receipts: `align-depth` binds calibrated output to model relative depth and independently supplied metric anchors by digest, and `reconstruct` enforces receipt presence or synthetic oracle origin.
- Silhouette boundary-perturbation sensitivity report (not statistically calibrated uncertainty).
- Direct metric-depth residual added to the parametric prior optimizer. Synthetic hidden-depth negative control recovers shape 0.699929 with true value 0.7, while identical silhouette alone does not identify the parameter.
- Perspective scale-ambiguity invariant and stricter handling of nonfinite calibration receipts.
- 51 tests passing, normal MIT package boundaries retained.

## v0.1.0 — 2026-10-15

- Initial geometry-first research framework, synthetic multi-view visual hull, optional model adapters, camera/landmark triangulation, parametric prior fitter, and approximate independent motion/gear tester.
