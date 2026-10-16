# View-planning and measurement experiments — 2026-10-15

## Scope and claim boundary

These experiments use *synthetic* anatomy (a corresponding 1,088-vertex
procedural mesh and a three-coefficient parametric basis). The source body's
coefficients were hidden from the optimizer, but the optimizer was given the
*exact same shape basis*. The cameras, pose, dimensions, binary masks and mesh
correspondences were known. This is an in-basis identifiability experiment,
**not** generalization to people photographed in the real world.

The objective of these experiments is to isolate whether a camera-view planner
extracts complementary 2D geometric constraints, how fragile silhouette fits
are to a few pixels of image-centering error, and whether a robust-fit prototype
can reduce that sensitivity.

## Observed results (saved machine-readable receipts)

| Experimental condition | Subjects | Planned views mean vertex error | Fixed front/rear mean vertex error | Receipt |
|---|---:|---:|---:|---|
| Clean synthetic silhouettes; pixelwise IoU fit | 6 | 0.779 mm | 5.401 mm | `demo/view-planning/view_planning_validation.json` |
| Up to ±2 px horizontal/vertical whole-mask shift; pixelwise IoU fit | 6 | 9.179 mm | 9.038 mm | `demo/view-planning/view_planning_shift2.json` |
| Same shifts; naive center-on-average-prior prealignment | 6 | 15.848 mm | 15.723 mm | `demo/view-planning/view_planning_shift2_prealign.json` |
| Same shifts; translation-invariant profile fit | 6 | 8.097 mm | 12.634 mm | `demo/view-planning/view_planning_shift2_profile.json` |
| **Clean** images with translation-invariant profile fit | 6 | 8.097 mm | 12.634 mm | `demo/view-planning/view_planning_clean_profile.json` |
| Up to ±2 px mask shift; two-stage profile/centering/pixel IoU fit | 2 | 1.566 mm | 7.449 mm | `demo/view-planning/view_planning_shift2_two_stage_small.json` |

The translation-invariant profiles give *identical scores under the deliberate
integer shifts* and on clean images. Their worse clean-mask accuracy proves the
trade-off: invariance removed measurement-relevant geometric information.

The two-stage experiment is still **only two synthetic subjects**, and cannot
be used to claim a reliably better fitting method. Larger two-stage and
four-view optimization experiments exceeded the runtime bound; neither is
recorded as a successful or validated evaluation. Keep those failures in the
research log and address computational cost before scaling.

## Shape sensitivity, not actual accuracy

- The view planner evaluates finite-difference shape-coefficient sensitivity
  to rendered silhouette signed-distance boundaries, then selects cameras
  greedily using a regularized log determinant of information.
- The resulting information eigenvalues are **not** calibrated covariance,
  credible intervals, or millimeter accuracy estimates.
- The current planner chose 45° and 225° (diagonal and opposite diagonal)
  for the 2-view procedural benchmark. A frontal/rear comparison is known to
  be weak for front/back thickness and is not a representative optimal baseline.
- The same identity basis is used for inference and truth. A realistically
  different source anatomy could defeat all of these methods.
- Entire-mask shift is a limited perturbation that models image cropping or
  principal-point error; it is **not** a diverse segmentation-error benchmark.

## Surface-measurement unit test

A high-resolution triangulated cylinder of radius 0.18 m and 256 angular
segments was intersected directly with three horizontal planes. The measured
perimeters were within 0.2 mm of the ideal circle's mathematical circumference.
This validates the code on known mathematical geometry only. Real anatomy,
clothing, camera scale, mesh reconstruction bias, and landmark association are
still completely unvalidated.

## Immediate next gates

1. Test view selection against **out-of-basis** body variations and nonuniform
   shapes, not only the fitted prior's own coefficient family.
2. Admit a properly licensed, independently measured and RGB-paired dataset
   using `audit-dataset`; use strictly held-out subjects for reporting.
3. Recover camera intrinsics/extrinsics and metric scale from image evidence;
   never substitute the renderer's oracle cameras for real-camera inference.
4. Quantify per-measurement error (body girths and bone-segment lengths) in mm,
   including failures, demographic coverage and the impact of clothing.
5. Calibrate uncertainty envelopes against independent real-subject errors.
6. Accelerate the fitter and institute bounded runtime budgets before running
   many camera configurations or a large model-parameter space.

The independent motion/armor tester remains separate from the body scanner; it
must not present its provisional rig as personalized joint anatomy.

## Holdout camera and independently metric-depth checking

A procedural box-body test varied its hidden front-to-back thickness without
changing the projected frontal silhouette. A prior fit trained on only the
front silhouette achieved 1.0000 front-view IoU but only **0.6053** held-out
side-view IoU. Including the side view in optimization moved the depth morph
coefficient from 0 toward the generated target (0.9) but did not recover it
exactly (observed fit ~0.68 under 128×160 rasterization).

A second withheld camera-Z-depth check on the same frontal view has exact
silhouette agreement even with the wrong thickness, yet reports nonzero
calibrated surface-depth residuals. These are controlled synthetic tests, **not
real-body measurement accuracy claims**. A holdout view is genuinely excluded
from shape optimization and from triangulation of joint-anchor training data.

Failure modes remain: view count and camera pose are supplied, synthetic body
shape is within a known basis, and withheld RGB imagery is not independently
collected from real subjects. These checks can expose some overfits, but good
held-out image agreement does not guarantee correct unobserved anatomy.
