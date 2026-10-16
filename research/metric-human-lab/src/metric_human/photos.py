"""Experimental camera-and-silhouette preparation from ordinary photographs.

THIS IS NOT automatic camera calibration or verified metric body recovery.
The rotation angles must be supplied or deliberately assigned from an evenly
spaced stationary-camera/rotating-person sequence. A height prior (not a true
measurement) sets an approximate scale. Every assumption is persisted.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from .cameras import Camera
from .reconstruct import mask_from_image
from .volume import Grid


def _read_mask(image: Path, *, mask: Path | None, segmentation: str) -> np.ndarray:
    if mask is not None:
        x = cv2.imread(str(mask), cv2.IMREAD_UNCHANGED)
        if x is None:
            raise ValueError(f"Cannot read supplied mask {mask}")
        if x.ndim == 3:
            x = cv2.cvtColor(x[:, :, :3], cv2.COLOR_BGR2GRAY)
        result = x > 127
    elif segmentation == "alpha":
        x = cv2.imread(str(image), cv2.IMREAD_UNCHANGED)
        if x is None or x.ndim != 3 or x.shape[2] != 4:
            raise ValueError(f"Transparent PNG with alpha required: {image}")
        result = x[:, :, 3] > 127
    elif segmentation == "grabcut":
        result = mask_from_image(image)
    else:
        raise ValueError("Choose mask files, --segmentation alpha, or --segmentation grabcut")
    if not result.any():
        raise ValueError(f"Foreground empty in {image}")
    n, labels, stats, _ = cv2.connectedComponentsWithStats(result.astype(np.uint8), 8)
    if n <= 1:
        raise ValueError(f"No connected foreground region in {image}")
    largest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    clean = labels == largest
    if clean.sum() < 100:
        raise ValueError(f"Foreground is too small to reconstruct: {image}")
    return clean


def prepare_photographs(
    images: Sequence[str | Path],
    output_dir: str | Path,
    *,
    masks: Sequence[str | Path] | None = None,
    angles_deg: Sequence[float] | None = None,
    segmentation: str = "grabcut",
    assumed_height_m: float = 1.70,
    known_height_m: float | None = None,
    resolution: int = 75,
    centering: str = "torso",
) -> dict:
    """Create calibrated-*approximation* manifest + foreground masks.

    Assumptions: similar pose, level cameras, subject rotates around vertical axis,
    no camera foreshortening; each image's foreground bbox roughly represents
    the same standing human height. Ground coordinates are provisionally meters.
    """
    if not images:
        raise ValueError("At least one photograph required")
    if centering not in ("torso", "image", "bbox"):
        raise ValueError("centering must be torso, image or bbox")
    img_paths = [Path(s).expanduser().resolve() for s in images]
    if masks is not None and len(masks) != len(images):
        raise ValueError("One mask per photograph is required")
    if angles_deg is not None and len(angles_deg) != len(images):
        raise ValueError("One azimuth angle per photograph is required")
    if known_height_m is not None and not (0.5 < known_height_m < 2.8):
        raise ValueError("Invalid known human height")
    if not (0.5 < assumed_height_m < 2.8):
        raise ValueError("Invalid assumed human height")
    if resolution < 25 or resolution > 320:
        raise ValueError("resolution must be between 25 and 320")
    height = known_height_m if known_height_m is not None else assumed_height_m
    angles = (list(angles_deg) if angles_deg is not None
              else np.linspace(0, 360, len(images), endpoint=False).tolist())
    pitch = height / resolution
    half_width = 0.43 * height
    grid = Grid(
        tuple(float(v) for v in (-half_width, -half_width, -0.10)),
        tuple(float(v) for v in (half_width, half_width, height + .10)),
        tuple(int(np.ceil((v-u)/pitch)) for u, v in zip(
            (-half_width, -half_width, -0.10), (half_width, half_width, height+.10))),
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    diagnoses = []
    for i, (src, azimuth) in enumerate(zip(img_paths, angles)):
        mask = _read_mask(src,mask=Path(masks[i]) if masks is not None else None,segmentation=segmentation)
        ys, xs = np.where(mask)
        h, w = mask.shape
        pix_height = float(ys.max() - ys.min() + 1)
        if pix_height < .18 * h:
            raise ValueError(f"Very small detected body in image {src}")
        # Orthographic projected size assumes the subject is standing straight.
        px_per_m = pix_height / height
        if centering == "image":
            midx = float((w-1)/2)
        elif centering == "bbox":
            midx = float((xs.min()+xs.max())/2)
        else:
            # A whole-person bbox can be heavily shifted by feet/props in
            # profile. Use median centers of the torso-height silhouette rows.
            center_candidates=[]
            for t in (.30,.36,.42,.49):
                row=int(np.clip(round(ys.min()+t*(ys.max()-ys.min())),0,h-1))
                row_x=np.flatnonzero(mask[row])
                if len(row_x):
                    center_candidates.append(float((row_x.min()+row_x.max())/2))
            midx=float(np.median(center_candidates)) if center_candidates else float((xs.min()+xs.max())/2)
        midy = float((ys.min()+ys.max())/2)
        az = float(np.deg2rad(azimuth))
        focal_point = np.array([0., 0., height / 2])
        eye = focal_point + np.array([3 * np.sin(az), -3 * np.cos(az), 0.])
        cam = Camera.look_at(eye,focal_point,width=w,height=h,focal=px_per_m,
                             model="orthographic")
        # Camera principal point follows the foreground bbox; this is not a
        # calibrated optical center, so absolute geometry remains approximate.
        cam = Camera(cam.rotation,cam.translation,w,h,px_per_m,px_per_m,midx,midy,"orthographic")
        mask_name = f"mask_{i:02d}.png"
        cv2.imwrite(str(out/mask_name), (mask.astype(np.uint8)*255))
        entries.append({"mask":mask_name,"label":f"photo_{i:02d}",
                        "camera":cam.to_dict(),"weight":1.0,
                        "segmentation_margin_px":1})
        diagnoses.append({"image":str(src),"azimuth_deg":float(azimuth),
                         "mask_area_fraction":round(float(mask.mean()),5),
                         "bounding_box_pixels":[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())],
                         "orthographic_px_per_m_assumed":round(px_per_m,5),
                         "principal_point_assumed":[round(midx,2),round(midy,2)],
                         "centering_strategy":centering})
    config = {
        "grid":grid.to_dict(),"views":entries,
        "scale_source":"user_height_anchor" if known_height_m is not None else "inferred_unvalidated",
        "calibration_status":"approximate_uncalibrated_photographs",
        "height_prior_m":float(height),
        "method":"orthographic_orbit_assumption_not_camera_pose_estimation",
        "centering_strategy":centering,
        "notes":[
            "Predicted millimeter units are NOT independently validated without real-person ground truth.",
            "A height prior is not actual metric information and does not resolve global scale ambiguity.",
            "View azimuths are provided/assumed, not automatically estimated.",
            "All photos must show the same body pose at roughly level camera elevation.",
            "Loose clothing is treated as part of the silhouette, not separated from anatomy.",
            "1-2 views leave most depth and concavity unobservable."
        ],"image_diagnostics":diagnoses,
    }
    path = out / "reproducible_input.json"
    path.write_text(json.dumps(config,indent=2),encoding="utf8")
    return {"manifest":str(path),"views":len(entries),"scale_source":config["scale_source"],
            "camera_calibration":config["calibration_status"]}
