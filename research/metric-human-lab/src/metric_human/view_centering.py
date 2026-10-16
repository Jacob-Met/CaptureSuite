"""Limited one-time silhouette-centering correction for rigid-pose photo fitting.

Compensates small global image cropping / principal-point offsets by matching
centers of foreground masks. Does not recover actual extrinsics, intrinsics,
subject dimensions, articulated pose or metric scale. Asymmetric silhouettes
and clothing can bias this heuristic. Opt-in and fully reported.
"""
from __future__ import annotations
from dataclasses import replace
import numpy as np
from .prior import Prior
from .reconstruct import View
from .cameras import Camera
from .synthetic import render_silhouette
from .quality import mask_iou


def _mask_center(mask):
    y,x=np.nonzero(mask)
    if len(x)<20:
        raise ValueError('Too little visible foreground for centering')
    # Silhouette bbox center tracks rigid 2D translations exactly for unclipped
    # objects, and doesn't change under symmetric axis-scale morphs.
    return np.array([(x.min()+x.max())/2,(y.min()+y.max())/2],float)


def recenter_views_from_prior(prior:Prior,views:list[View], *, baseline=None,
                              max_shift_px:int=3):
    if not isinstance(max_shift_px,int) or not 0<=max_shift_px<=16:
        raise ValueError('max_shift_px must be integer 0..16')
    n=len(prior.parameter_names)
    coefficients=np.zeros(n,float) if baseline is None else np.asarray(baseline,float)
    if coefficients.shape!=(n,) or not np.isfinite(coefficients).all():
        raise ValueError('Invalid coefficient baseline')
    initial_mesh=prior.generate(coefficients)
    new=[];rows=[]
    for v in views:
        observed=np.asarray(v.mask,bool)
        prediction=render_silhouette(initial_mesh,v.camera)
        delta=np.rint(_mask_center(observed)-_mask_center(prediction)).astype(int)
        clipped=np.clip(delta,-max_shift_px,max_shift_px)
        c=v.camera
        adjusted=Camera(c.rotation,c.translation,c.width,c.height,c.fx,c.fy,
                        c.cx+float(clipped[0]),c.cy+float(clipped[1]),c.model)
        fixed_pred=render_silhouette(initial_mesh,adjusted)
        new.append(replace(v,camera=adjusted))
        rows.append({'view':v.label,'uncapped_pixel_shift_xy':delta.tolist(),
                    'applied_pixel_shift_xy':clipped.tolist(),
                    'clamped':bool(np.any(delta!=clipped)),
                    'baseline_mask_iou_before':mask_iou(prediction,observed),
                    'baseline_mask_iou_after':mask_iou(fixed_pred,observed)})
    return new,{'method':'prior_silhouette_bbox_center_shift_not_camera_calibration',
                'max_shift_px':max_shift_px,'estimated_offsets':rows,
                'camera_orientation_calibrated':False,
                'absolute_metric_scale_calibrated':False,
                'limitations':[
                    'Symmetry-dependent; apparent body-shape and pose differences can mimic camera shifts.',
                    'Corrects only in-plane principal-point/crop offsets, not focal length or rotation.',
                    'Foreground masks and depth evidence must already share the same pixel coordinates.',
                    'Baseline-model silhouette agreement is not validated real camera calibration.',
                ]}
