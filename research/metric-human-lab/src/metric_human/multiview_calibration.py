"""Recover two-view relative perspective cameras from 2D feature correspondences.

This is a *similarity-gauge* solver: camera 1 is the origin and the camera
baseline is 1 arbitrary unit. Images and intrinsics alone do NOT establish a
physical baseline, human height, or dimensions in meters. The caller must
provide correspondences for the *same static physical points* across images.

Deliberately refuses low-parallax and near-planar feature arrangements rather
than inventing plausible depth. Not a substitute for a bundle-adjusted SfM
pipeline or anatomical correspondence detector.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
import cv2
from scipy.optimize import least_squares

from .cameras import Camera


@dataclass(frozen=True)
class TwoViewResult:
    first_camera: Camera
    second_camera: Camera
    point_coordinates_baseline_units: dict[str, list[float]]
    inlier_labels: tuple[str, ...]
    ransac_inlier_count: int
    correspondence_count: int
    reprojection_rmse_px: float
    median_parallax_deg: float
    estimated_camera_baseline: float = 1.0

    def to_dict(self):
        return {
            "cameras": [self.first_camera.to_dict(), self.second_camera.to_dict()],
            "points_baseline_units": self.point_coordinates_baseline_units,
            "inlier_labels": list(self.inlier_labels),
            "ransac_inlier_count": self.ransac_inlier_count,
            "correspondence_count": self.correspondence_count,
            "reprojection_rmse_px": self.reprojection_rmse_px,
            "median_parallax_deg": self.median_parallax_deg,
            "camera_baseline_arbitrary_units": self.estimated_camera_baseline,
            "camera_intrinsics_source": "supplied_not_estimated",
            "metric_scale_source": "unknown_global_similarity_gauge",
            "metric_scale_verified": False,
            "person_geometry_verified": False,
            "requires_static_corresponding_points": True,
        }


def _intrinsics(width, height, focal_x, focal_y, cx, cy):
    if width < 2 or height < 2:
        raise ValueError("Image dimensions must exceed one pixel")
    if not all(np.isfinite([focal_x, focal_y, cx, cy])) or focal_x <= 0 or focal_y <= 0:
        raise ValueError("Calibrated positive finite intrinsics required")
    return np.array([[focal_x, 0, cx], [0, focal_y, cy], [0, 0, 1]], dtype=np.float64)


def _pixel_reprojection(R, t, xyz, K):
    c = xyz @ R.T + t
    if np.any(c[:, 2] <= 0):
        raise ValueError("Recovered points must be in front of both cameras")
    norm = c[:, :2] / c[:, 2, None]
    return norm * np.array([K[0, 0], K[1, 1]]) + K[:2, 2]


def recover_relative_cameras(
    points_first: dict[str, tuple[float, float] | list[float]],
    points_second: dict[str, tuple[float, float] | list[float]], *,
    image_width: int, image_height: int,
    first_fx_px: float, first_fy_px: float,
    second_fx_px: float | None = None, second_fy_px: float | None = None,
    first_cx_px: float | None = None, first_cy_px: float | None = None,
    second_cx_px: float | None = None, second_cy_px: float | None = None,
    ransac_threshold_px: float = 1.5,
    max_reprojection_rmse_px: float = 2.5,
    min_median_parallax_deg: float = 1.5,
    random_seed: int = 42,
) -> TwoViewResult:
    """Estimate calibrated relative orientation/translation direction with RANSAC.

    Strong guards prevent fabricated metric scale, accidental static/rotational
    degeneracy, outlier-dominated matches and zero-baseline triangulation. At
    least 12 shared, spatially distributed, *static* correspondences are needed.
    """
    labels = sorted(set(points_first).intersection(points_second))
    if len(labels) < 12:
        raise ValueError("At least 12 matched static image features are required")
    uv1 = np.asarray([points_first[n] for n in labels], dtype=np.float64)
    uv2 = np.asarray([points_second[n] for n in labels], dtype=np.float64)
    if uv1.shape != (len(labels), 2) or uv2.shape != uv1.shape:
        raise ValueError("Each feature must have two pixel coordinates")
    if not np.isfinite(uv1).all() or not np.isfinite(uv2).all():
        raise ValueError("Nonfinite correspondence coordinates")
    for pts in (uv1, uv2):
        if np.linalg.matrix_rank(pts - pts.mean(axis=0), tol=1e-6) < 2:
            raise ValueError("Image feature distribution is degenerate")
        if min(np.ptp(pts, axis=0)) < 12:
            raise ValueError("Image features insufficiently dispersed")
        if len(np.unique(np.round(pts, 5), axis=0)) != len(labels):
            raise ValueError("Repeated feature coordinates")
    cx1 = (image_width - 1) / 2 if first_cx_px is None else first_cx_px
    cy1 = (image_height - 1) / 2 if first_cy_px is None else first_cy_px
    cx2 = (image_width - 1) / 2 if second_cx_px is None else second_cx_px
    cy2 = (image_height - 1) / 2 if second_cy_px is None else second_cy_px
    K1 = _intrinsics(image_width, image_height, first_fx_px, first_fy_px, cx1, cy1)
    K2 = _intrinsics(image_width, image_height,
                     first_fx_px if second_fx_px is None else second_fx_px,
                     first_fy_px if second_fy_px is None else second_fy_px, cx2, cy2)
    if not all(np.isfinite([ransac_threshold_px, max_reprojection_rmse_px, min_median_parallax_deg])) or any(
        v <= 0 for v in (ransac_threshold_px, max_reprojection_rmse_px, min_median_parallax_deg)
    ):
        raise ValueError("Thresholds must be finite and positive")
    norm1 = cv2.undistortPoints(uv1.reshape(-1, 1, 2), K1, None).reshape(-1, 2)
    norm2 = cv2.undistortPoints(uv2.reshape(-1, 1, 2), K2, None).reshape(-1, 2)
    norm_thresh = ransac_threshold_px / float(np.sqrt(np.mean([
        first_fx_px**2, first_fy_px**2, K2[0, 0]**2, K2[1, 1]**2
    ])))
    cv2.setRNGSeed(int(random_seed))
    E, inliers = cv2.findEssentialMat(norm1, norm2, np.eye(3), method=cv2.RANSAC,
                                      prob=0.999, threshold=norm_thresh, maxIters=2000)
    if E is None or inliers is None:
        raise ValueError("Essential-matrix estimation failed")
    if E.shape != (3, 3):
        raise ValueError("Ambiguous multiple essential matrices")
    mask = inliers.ravel().astype(bool)
    required = max(12, int(math.ceil(0.65 * len(labels))))
    if int(mask.sum()) < required:
        raise ValueError("Not enough RANSAC-consistent feature matches")
    count, R, t, good = cv2.recoverPose(E, norm1, norm2, np.eye(3), mask=mask.astype(np.uint8).reshape(-1, 1))
    retained = good.ravel().astype(bool)
    if int(retained.sum()) < required or count < required:
        raise ValueError("Insufficient triangulatable matches with positive depth")
    # Refine the recovered relative pose against all robustly matched rays.
    # Symmetric epipolar (Sampson) error is invariant to unknown 3D scale.
    # This is NOT joint metric calibration; its only outputs are R and t direction.
    matched_1 = np.column_stack((norm1[retained], np.ones(int(retained.sum()))))
    matched_2 = np.column_stack((norm2[retained], np.ones(int(retained.sum()))))
    rvec, _ = cv2.Rodrigues(R)

    def epipolar_residual(params):
        new_r, _ = cv2.Rodrigues(params[:3])
        new_t = params[3:]
        new_t = new_t / max(np.linalg.norm(new_t), 1e-12)
        tx = np.array([[0., -new_t[2], new_t[1]],
                       [new_t[2], 0., -new_t[0]],
                       [-new_t[1], new_t[0], 0.]])
        essential = tx @ new_r
        e1 = (essential @ matched_1.T).T
        e2 = (essential.T @ matched_2.T).T
        numer = np.sum(matched_2 * e1, axis=1)
        denom = np.sqrt(np.sum(e1[:, :2]**2 + e2[:, :2]**2, axis=1) + 1e-15)
        return (numer / denom) * float(np.sqrt(np.mean([K1[0, 0]**2, K1[1, 1]**2, K2[0, 0]**2, K2[1, 1]**2])))

    initial = np.r_[rvec.ravel(), t.ravel()]
    fitted = least_squares(epipolar_residual, initial, method='trf',
                           loss='soft_l1', f_scale=0.7, max_nfev=150,
                           xtol=1e-10, ftol=1e-10, gtol=1e-10)
    if not np.isfinite(fitted.x).all():
        raise ValueError('Relative pose refinement failed')
    R, _ = cv2.Rodrigues(fitted.x[:3])
    t = fitted.x[3:]
    baseline = float(np.linalg.norm(t))
    if not np.isfinite(baseline) or baseline < 1e-8:
        raise ValueError("Degenerate recovered translation")
    t /= baseline
    x1 = norm1[retained]
    x2 = norm2[retained]
    P1 = np.column_stack((np.eye(3), np.zeros(3)))
    P2 = np.column_stack((R, t))
    homo = cv2.triangulatePoints(P1, P2, x1.T, x2.T).T
    if np.any(np.abs(homo[:, 3]) < 1e-9):
        raise ValueError("Triangulation contains points at infinity")
    xyz = homo[:, :3] / homo[:, 3, None]
    if not np.isfinite(xyz).all() or np.any(xyz[:, 2] <= 0):
        raise ValueError("Unstable or behind-camera triangulation")
    px1 = _pixel_reprojection(np.eye(3), np.zeros(3), xyz, K1)
    px2 = _pixel_reprojection(R, t, xyz, K2)
    errors = np.concatenate([np.linalg.norm(px1 - uv1[retained], axis=1),
                             np.linalg.norm(px2 - uv2[retained], axis=1)])
    rmse = float(np.sqrt(np.mean(errors**2)))
    if rmse > max_reprojection_rmse_px:
        raise ValueError(f"Triangulation reprojection error {rmse:.2f}px too high")
    center2 = -R.T @ t
    v1 = xyz
    v2 = xyz - center2
    cosine = np.einsum("ij,ij->i", v1, v2) / (np.linalg.norm(v1, axis=1) * np.linalg.norm(v2, axis=1))
    angles = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))
    median_parallax = float(np.median(angles))
    if median_parallax < min_median_parallax_deg:
        raise ValueError("Insufficient stereo parallax; depth is unobservable")
    # Near-planar image motion is equally explainable by a homography or a
    # rotation. This gate catches that ambiguity even when recoverPose finds a
    # seemingly reasonable essential matrix.
    H, hmask = cv2.findHomography(uv1, uv2, cv2.RANSAC, 0.75)
    if H is not None and hmask is not None and hmask.sum() >= max(12, int(0.95 * len(labels))):
        projected = cv2.perspectiveTransform(uv1.reshape(-1, 1, 2), H).reshape(-1, 2)
        residual = np.linalg.norm(projected - uv2, axis=1)
        if float(np.median(residual)) <= 0.55:
            raise ValueError("Planar or pure-rotation degeneracy: two-view shape unobservable")
    c1 = Camera(np.eye(3), np.zeros(3), image_width, image_height,
                float(K1[0, 0]), float(K1[1, 1]), float(K1[0, 2]), float(K1[1, 2]))
    c2 = Camera(R, t, image_width, image_height,
                float(K2[0, 0]), float(K2[1, 1]), float(K2[0, 2]), float(K2[1, 2]))
    kept_names = tuple(np.asarray(labels)[retained].tolist())
    return TwoViewResult(c1, c2, dict(zip(kept_names, xyz.tolist())), kept_names,
                         int(mask.sum()), len(labels), rmse, median_parallax)
