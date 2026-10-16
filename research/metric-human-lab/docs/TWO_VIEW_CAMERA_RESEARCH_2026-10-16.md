# Two-view relative camera recovery — 2026-10-16

## Objective

Remove the requirement to type a camera **azimuth** for two perspective views
when correspondences and intrinsics are available. Retain the global scale
ambiguity of uncalibrated RGB. Avoid the classic failure where background
features are mistaken for a rotating person's surface.

## Implementation

- `src/metric_human/multiview_calibration.py`: input matching, normalized
  intrinsics, OpenCV essential-matrix RANSAC and cheirality, robust nonlinear
  epipolar pose refinement, triangulation, explicit gauge choice (first camera
  identity; baseline exactly 1 *nonmetric* unit), reprojection/parallax gates,
  and near-planar homography rejection.
- `src/metric_human/feature_matches.py`: SIFT symmetric mutual-ratio matching
  restricted to explicit subject masks; source-image/mask SHA-256 fingerprints.
- New `match-features` and `calibrate-two-view` CLI operations, with JSON output.
- Tests using withheld known perspective cameras with randomized 3D points,
  added pixel noise, outlier correspondences, low baseline, planar surfaces,
  insufficient feature support, nonfinite and repeated pixels, empty/mismatched
  masks, stable repeats, and missing intrinsics.

## Boundaries / counterexamples

- Relative 3D geometry is **not** dimensionally accurate meters: the baseline
  is defined as unit 1 and absolute scale is unidentifiable.
- No 2D human joint-detection or multi-frame track model is trained here.
- SIFT on organic surfaces may fail or latch onto changing apparel; mask quality
  does not guarantee static identity of matched surface points.
- Pose/feature recovery is not yet wired to shape fitting, photo manifests or
  any learned RGB metric reconstruction mechanism.
- A scene dominated by a single plane or pure rotation must be rejected when
  it has no reliable triangulable depth.
- The known-camera synthetic evaluation is a solver smoke test, not a valid
  real-person dimensional reconstruction benchmark.

## Next strongest objective

Validate against genuinely paired ordinary RGB + known-scale scans, evaluate
pose under moving-subject vs moving-camera capture, and jointly refine the
camera and anatomical prior without claiming metric scale from imagery alone.
