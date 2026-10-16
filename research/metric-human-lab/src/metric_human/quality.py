"""Reprojection tests, volume diagnostics and intentionally strict status labels."""
from __future__ import annotations
import numpy as np
from scipy.ndimage import binary_erosion
from scipy.spatial import cKDTree
from .reconstruct import View
from .synthetic import render_silhouette


def mask_iou(a,b):
    a=np.asarray(a,dtype=bool);b=np.asarray(b,dtype=bool)
    if a.shape!=b.shape:raise ValueError('Masks differ in shape')
    den=np.sum(a|b)
    return float(np.sum(a&b)/den) if den else 1.0


def view_reprojection_diagnostics(mesh,views:list[View]):
    """An observation-space fit diagnostic, never physical ground-truth accuracy."""
    rows=[]
    for v in views:
        projected=render_silhouette(mesh,v.camera)
        rows.append({"view":v.label,"silhouette_iou":mask_iou(projected,v.mask),
                     "false_positive_pixel_fraction":float(np.mean(projected&~v.mask)),
                     "false_negative_pixel_fraction":float(np.mean(v.mask&~projected))})
    return rows


def heldout_view_diagnostics(mesh,views:list[View]):
    """Predict withheld masks and, when supplied, known-metric surface depth.

    This is image-domain predictive evidence; it is NOT a metric scan-error
    distribution and requires same camera/world metric scale as the body mesh.
    Any valid observed foreground pixels with missing predicted depth are
    accounted for as coverage failures rather than silently dropped.
    """
    from .render import render_metric_depth
    rows=view_reprojection_diagnostics(mesh,views)
    for row,v in zip(rows,views):
        if v.depth_m is None:
            row['metric_depth_validation']=None
            continue
        truth=np.asarray(v.depth_m,dtype=float)
        valid=np.asarray(v.mask,bool) & np.isfinite(truth) & (truth>0)
        if not valid.any():
            raise ValueError('Withheld calibrated depth has no valid positive foreground pixels')
        predicted=render_metric_depth(mesh,v.camera)
        overlap=valid & np.isfinite(predicted) & (predicted>0)
        errs=np.abs(predicted[overlap]-truth[overlap])
        row['metric_depth_validation']={
            'valid_reference_pixels':int(valid.sum()),
            'overlap_pixels':int(overlap.sum()),
            'predicted_surface_coverage_fraction':float(overlap.sum()/valid.sum()),
            'surface_depth_mae_mm':float(errs.mean()*1000) if len(errs) else None,
            'surface_depth_rmse_mm':float(np.sqrt(np.mean(errs**2))*1000) if len(errs) else None,
            'status':'measured_in_camera_Z_not_ground_truth_3d_mesh_accuracy',
        }
    return rows


def surface_chamfer_mm(estimated,reference,grid,*,sample_limit=10000,seed=3):
    """Voxel-surface symmetric nearest-neighbor Chamfer, in mm, synthetic truth only."""
    surf_a=estimated&~binary_erosion(estimated)
    surf_b=reference&~binary_erosion(reference)
    pa=np.argwhere(surf_a).astype(float)
    pb=np.argwhere(surf_b).astype(float)
    if not len(pa) or not len(pb):raise ValueError('Empty surface')
    rng=np.random.default_rng(seed)
    if len(pa)>sample_limit:pa=pa[rng.choice(len(pa),sample_limit,replace=False)]
    if len(pb)>sample_limit:pb=pb[rng.choice(len(pb),sample_limit,replace=False)]
    pa*=grid.spacing;pb*=grid.spacing
    return float(500*(cKDTree(pa).query(pb)[0].mean()+cKDTree(pb).query(pa)[0].mean()))
