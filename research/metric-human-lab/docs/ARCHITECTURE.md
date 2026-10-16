# Architecture and data contracts

## Orthogonal subsystems

- `cameras.py`: calibrated pinhole and orthographic projection; `R` world→camera, `t = -R*eye`. World `z` up, `x` lateral, `y` front/back; camera `+y` image downward and `+z` forward.
- `photos.py`: masks and approximate orbit-camera manifests derived from photo bboxes; keeps provenance that angles and scale are assumptions.
- `vision.py`: optional Hugging Face SAM2.1 Tiny foreground-mask and Depth Anything V2 Small *relative* depth adapters. Models are replaceable, processing is local, model weights are not bundled.
- `calibration.py`: perspective PnP using >=6 3D/2D matches and known intrinsics; rejects degenerate anchors and reports outlier filtering, but inherits the template coordinate scale.
- `landmarks.py`: 2D pose detector adapter output + weighted geometric triangulation. Rejects single-view or ill-conditioned ray systems.
- `depth.py`: affine regression converting relative-depth map to metric using independent metric surface point anchors, with residual-based rejection.
- `reconstruct.py`: explicit silhouette-cone intersection and optional free-space carving from **metric** depth. View support fraction is consistency, not calibrated confidence.
- `prior.py`: independently supplied corresponded base mesh / blend-shape basis, now supporting separate signed +/− morph targets, with direct multi-view silhouette and 3D landmark parameter optimization; independently calibrated depth optionally adds a real surface-depth residual. Does not bundle a learned anthropometric prior.
- `makehuman.py` / `makehuman_assets.py`: original format parser + SHA-256 pinned downloader for CC0 MakeHuman *asset data*, NOT MakeHuman application source or scanned-subject ground truth.
- `render.py` / `depth_ablation.py`: CPU reference-mesh camera-Z renderer and synthetic oracle-depth ablation; not depth prediction.
- `evidence.py`: physically independent depth-calibration receipt and hash check at CLI manifest boundary.
- `stability.py`: reproducible silhouette pixel-boundary perturbations; reports geometric sensitivity but not confidence or accuracy.
- `template.py`: older coarse procedural template fitter used for ablative experiments; not trained on humans.
- `motion.py`: separate capsule-body, skeletal kinematics and sample-point collision evaluator; never treated as comfort/fit certification.
- `body_rig.py`: bridge that scales the generic rig by a reconstruction volume’s bounding box, *not* a validated anatomical skeleton or skinning solution.
- `volume.py` / `measurements.py`: occupancy-to-mesh, bounding extents and horizontal section polygons.
- `bench.py` / `external.py`: synthetic and operator-provided-mesh benchmark harnesses, respectively.
- `quality.py`: silhouette reprojection and surface-to-surface error diagnostic. Projection agreement is not shape ground truth.

## Example manifest contract

```json
{
  "grid": {"lower": [-0.6,-0.4,-0.1], "upper": [0.6,0.4,1.9], "shape": [60,40,100]},
  "scale_source": "unknown",
  "views": [{
    "mask": "front_mask.png",
    "label": "front",
    "weight": 1.0,
    "segmentation_margin_px": 0,
    "depth_m": "optional_independently_aligned_metric_depth.npy",
    "depth_alignment_receipt": "optional_metric_depth.alignment.json",
    "depth_tolerance_m": 0.02,
    "camera": {
      "rotation": [[1,0,0],[0,0,-1],[0,1,0]],
      "translation": [0,1,-3],
      "width": 256, "height": 384,
      "fx": 200, "fy": 200, "cx": 127.5, "cy": 191.5,
      "model": "perspective"
    }
  }]
}
```

The camera shown is illustrative, not a tested capture calibration. Grid coordinates and metric depth are in the same units, nominally meters. `scale_source` is an explicit tag, not proof of truth. Unrecognized tags do not certify metric accuracy.

### Model integration boundary

Any segmentation or 2D landmark predictor may supply masks/landmark records without modifying geometry code. Relative depth predictors must go through independent-depth anchoring before use for hard physical carving. Camera geometry may come from trusted calibration, bundle adjustment, or research estimation—with the source and units retained in the manifest. Learned body priors should add soft constraints and spatial uncertainty, not silently replace observed geometry.

### Export validity and expected use

`metric_scale_verified = true` indicates only a known metric coordinate source (known synthetic mesh source or explicit metric camera frame), *not* proof that the reconstructed person's dimensions are correct. `metric_scale_anchored = true` means at least the global scale is anchored, including optional measured height. `human_measurement_accuracy_validated` remains false until independent real-human anthropometric benchmarks are actually run and recorded. This code never promises close-fitting equipment safety from a visual hull alone.

### Separately planned consumers

The body model format should remain independent of downstream applications. A motion subsystem will consume the mesh and independently rigged anatomical joints; a wearable simulation subsystem will consume that plus materials and attachment constraints. Do not bake armor assumptions into the body geometry solver.

### Experimental model-to-motion integration

`test-gear --body-npz ... --body-input ...` can consume voxel occupancy and its original Grid manifest, then scale the generic arm/leg capsule rig. This is useful for early interface and geometry contracts only; there is no algorithmically personalized bone-location inference, soft-tissue deformation, gear/gear contact or accurate wearable attachment. No output is marked fabrication-grade.
