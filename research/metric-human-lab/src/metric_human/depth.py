"""Calibrate model-specific *relative* depth using independent metric anchors.

A relative-depth image cannot be interpreted as meters without evidence of
both affine scale and offset (or a stronger camera model). This adapter never
pretends that a depth neural network provides metric physical information.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.optimize import least_squares


@dataclass(frozen=True)
class DepthAlignment:
    slope: float
    intercept_m: float
    anchor_rmse_m: float
    anchor_max_error_m: float
    n_anchors: int
    status: str = 'metric_anchors_affine_regression'

    def transform(self, relative_map):
        raw = self.slope * np.asarray(relative_map, float) + self.intercept_m
        return np.where(np.isfinite(raw) & (raw > 0), raw, np.nan).astype(np.float32)

    def to_dict(self):
        return {key:getattr(self,key) for key in self.__dataclass_fields__}


def align_relative_depth(relative_depth, anchors, *, max_rmse_m=.05):
    """Fit affine mapping relative depth -> meters from surface-point anchors.

    anchors: [{"u":pixel_x,"v":pixel_y,"camera_z_m":known_surface_depth},...]
    Must come from an independent calibrated source, not from the same depth map.
    """
    image=np.asarray(relative_depth,float)
    if image.ndim!=2:
        raise ValueError('Depth map must be a 2D array')
    if len(anchors)<3:
        raise ValueError('Need >=3 independent metric surface depth anchors')
    xs=[]; ys=[]
    for anchor in anchors:
        u,v=int(anchor['u']),int(anchor['v'])
        if u<0 or v<0 or u>=image.shape[1] or v>=image.shape[0]:
            raise ValueError('Calibration anchor outside image')
        raw=float(image[v,u]); z=float(anchor['camera_z_m'])
        if not np.isfinite(raw) or not np.isfinite(z) or z<=0:
            raise ValueError('Calibration anchor must have finite positive metric depth')
        xs.append(raw);ys.append(z)
    x=np.asarray(xs);y=np.asarray(ys)
    if np.ptp(x)<1e-5:
        raise ValueError('Degenerate identical relative depth anchors')
    A=np.column_stack((x,np.ones_like(x)))
    initial=np.linalg.lstsq(A,y,rcond=None)[0]
    def residual(p):return A@p-y
    opt=least_squares(residual,initial,loss='huber',f_scale=.02)
    slope,intercept=(float(t) for t in opt.x)
    errors=A@opt.x-y
    rmse=float(np.sqrt(np.mean(errors**2)))
    if rmse>max_rmse_m:
        raise ValueError(f'Depth alignment anchor RMSE {rmse:.4f} m exceeds {max_rmse_m:.4f} m tolerance')
    aligned=DepthAlignment(slope,intercept,rmse,float(np.max(np.abs(errors))),len(anchors))
    return aligned.transform(image),aligned
