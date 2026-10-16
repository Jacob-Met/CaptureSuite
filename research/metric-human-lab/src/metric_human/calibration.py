"""Recover perspective camera extrinsics from independently matched 3D/2D anchors.

The method does NOT estimate true body size from unscaled template points.
World coordinates, including any global similarity ambiguity, are inherited
from the supplied 3D anchor frame.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import cv2
from .cameras import Camera


@dataclass(frozen=True)
class PnPResult:
    camera: Camera
    reprojection_rmse_px: float
    reprojection_median_px: float
    n_correspondences: int
    n_ransac_inliers: int
    inlier_labels: tuple[str, ...]
    coordinate_scale_source: str

    def to_dict(self):
        return {
            'camera': self.camera.to_dict(),
            'reprojection_rmse_px': self.reprojection_rmse_px,
            'reprojection_median_px': self.reprojection_median_px,
            'n_correspondences': self.n_correspondences,
            'n_ransac_inliers': self.n_ransac_inliers,
            'inlier_labels': list(self.inlier_labels),
            'coordinate_scale_source': self.coordinate_scale_source,
            'camera_pose_from_known_3d_2d_correspondences': True,
            'metric_body_geometry_independently_verified': False,
        }


def solve_perspective_pnp(
    anchors_world: dict[str, list[float] | tuple[float,float,float]],
    pixels: dict[str, list[float] | tuple[float,float]], *,
    image_width: int, image_height: int, fx_px: float, fy_px: float,
    cx_px: float | None = None, cy_px: float | None = None,
    reprojection_threshold_px: float = 4.0,
    max_accepted_rmse_px: float = 3.0,
    coordinate_scale_source: str = 'unknown',
    random_seed: int = 42,
) -> PnPResult:
    """Robust PnP: >=6 common *noncoplanar* correspondences, known intrinsics.

    Only inlier agreement is reported. A physically wrong 3D body template can
    have good PnP reprojections, so this never certifies body geometry.
    """
    common = sorted(set(anchors_world) & set(pixels))
    if len(common) < 6:
        raise ValueError('At least six shared 2D/3D anchor labels required for stable PnP')
    xyz = np.asarray([anchors_world[k] for k in common], dtype=np.float64)
    uv = np.asarray([pixels[k] for k in common], dtype=np.float64)
    if xyz.shape != (len(common),3) or uv.shape != (len(common),2):
        raise ValueError('Each anchor needs world [x,y,z] and pixel [u,v]')
    if not np.all(np.isfinite(xyz)) or not np.all(np.isfinite(uv)):
        raise ValueError('PnP anchors must contain only finite coordinates')
    if np.linalg.matrix_rank(xyz-xyz.mean(axis=0),tol=1e-8)<3:
        raise ValueError('3D PnP anchors must not all lie in one plane')
    if np.linalg.matrix_rank(uv-uv.mean(axis=0),tol=1e-6)<2 or min(np.ptp(uv,axis=0))<6:
        raise ValueError('2D PnP points are degenerate or insufficiently dispersed')
    if image_width<=1 or image_height<=1 or not all(np.isfinite([fx_px,fy_px])) or fx_px<=0 or fy_px<=0:
        raise ValueError('Valid positive camera intrinsics and image dimensions required')
    if reprojection_threshold_px<=0 or max_accepted_rmse_px<=0:
        raise ValueError('Error thresholds must be positive')
    cx = (image_width-1)/2 if cx_px is None else float(cx_px)
    cy = (image_height-1)/2 if cy_px is None else float(cy_px)
    K=np.array([[fx_px,0,cx],[0,fy_px,cy],[0,0,1]],np.float64)
    if not np.all(np.isfinite(K)):
        raise ValueError('Nonfinite camera intrinsics')
    # Explicit seed makes RANSAC runs reproducible for fixed OpenCV implementation.
    cv2.setRNGSeed(int(random_seed))
    success,rvec,tvec,inliers = cv2.solvePnPRansac(
        xyz,uv,K,np.zeros((4,1),np.float64),
        reprojectionError=float(reprojection_threshold_px),
        iterationsCount=400,confidence=.999,flags=cv2.SOLVEPNP_EPNP)
    if not success or inliers is None or len(inliers)<6:
        raise ValueError('PnP RANSAC found fewer than six consistent anchors')
    if len(inliers) < max(6,int(np.ceil(.60*len(common)))):
        raise ValueError('PnP matched fewer than 60% of supplied anchors; camera is unreliable')
    inlier_index = np.asarray(inliers).reshape(-1)
    # Optimize only RANSAC-consistent correspondences.
    success,rvec,tvec = cv2.solvePnP(
        xyz[inlier_index],uv[inlier_index],K,np.zeros((4,1),np.float64),
        rvec=rvec,tvec=tvec,useExtrinsicGuess=True,flags=cv2.SOLVEPNP_ITERATIVE)
    if not success:
        raise ValueError('PnP inlier refinement did not converge')
    R,_ = cv2.Rodrigues(rvec)
    camera=Camera(R,tvec.reshape(3),image_width,image_height,float(fx_px),float(fy_px),cx,cy,'perspective')
    pred, z = camera.project(xyz[inlier_index])
    if not (z > 0).all():
        raise ValueError('PnP projects some inlier anchors behind camera')
    errors=np.linalg.norm(pred-uv[inlier_index],axis=1)
    rmse=float(np.sqrt(np.mean(errors**2)))
    if rmse>max_accepted_rmse_px:
        raise ValueError(f'PnP inlier reprojection error {rmse:.2f} px exceeds {max_accepted_rmse_px:.2f} px')
    return PnPResult(camera,rmse,float(np.median(errors)),len(common),len(inlier_index),
                     tuple(common[i] for i in inlier_index),coordinate_scale_source)
