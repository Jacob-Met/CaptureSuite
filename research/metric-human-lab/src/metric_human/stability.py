"""Deterministic silhouette-boundary sensitivity analysis, NOT confidence intervals.

Tests geometric responses if foreground masks are wrong by a configured number
of pixels. It does not account for correlated model errors, camera calibration,
clothing, hidden anatomy, or absolute scale errors.
"""
from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path

import cv2
import numpy as np

from .reconstruct import View, fuse_views
from .volume import Grid
from .measurements import slice_components


def _morph_mask(mask,radius,operation):
    mask=np.asarray(mask,dtype=np.uint8)
    if radius==0:return mask.astype(bool)
    kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*radius+1,2*radius+1))
    f=cv2.erode if operation=='erode' else cv2.dilate
    return f(mask,kernel,iterations=1).astype(bool)


def silhouette_boundary_sensitivity(views:list[View],grid:Grid,*,radius_px=2,
                                    min_fraction=1.,sample_section_z=None):
    """Reconstruct eroded/nominal/dilated silhouettes and compare observations.

    Dilated support contains nominal support; nominal contains eroded support
    for hard visual-hull intersection. These are envelope *algorithms*, not
    bounds on the unobserved anatomical shape of the person.
    """
    if not isinstance(radius_px,int) or not 0 <= radius_px <= 15:
        raise ValueError('radius_px must be integer 0..15')
    if not views: raise ValueError('No views')
    if any(v.depth_m is not None for v in views):
        raise ValueError('Silhouette-only stability cannot silently ignore metric-depth constraints')
    categories={}
    for name,op in [('eroded','erode'),('nominal','none'),('dilated','dilate')]:
        altered=[replace(v,mask=(_morph_mask(v.mask,radius_px,op)
                                   if op!='none' else np.asarray(v.mask,bool)),
                        segmentation_margin_px=0) for v in views]
        if any(v.segmentation_margin_px for v in views):
            raise ValueError('Resolve any segmentation margins before sensitivity evaluation')
        categories[name]=fuse_views(altered,grid,min_fraction=min_fraction,
                                  scale_source='geometric_stability_test')
    inner=categories['eroded'].occupancy
    nominal=categories['nominal'].occupancy
    outer=categories['dilated'].occupancy
    if not (np.all(inner<=nominal) and np.all(nominal<=outer)):
        raise RuntimeError('Morphological nesting invariant failed')
    gap=int(np.sum(outer & ~inner))
    sec=[]
    for z in (sample_section_z or []):
        rows={}
        for name,r in categories.items():
            slices=slice_components(r.occupancy,grid,z)
            rows[name]=slices[0]['perimeter_m'] if slices else None
        sec.append({'z_m':float(z), 'largest_section_perimeter_m':rows,
                    'envelope_spread_mm':(1000*(max(rows.values())-min(rows.values()))
                                          if all(v is not None for v in rows.values()) else None),
                    'semantics':'observed silhouette boundary perturbation only; not human body accuracy'})
    report={
        'analysis_type':'segmentation_pixel_boundary_sensitivity_not_probability_or_accuracy',
        'radius_px':radius_px, 'views':len(views),
        'min_support_fraction':min_fraction,
        'occupied_voxels_by_case':{name:int(r.occupancy.sum()) for name,r in categories.items()},
        'voxels_of_occupancy_disagreement':gap,
        'volume_disagreement_m3_if_grid_is_metric':float(gap*np.prod(grid.spacing)),
        'fractions_of_grid_with_disagreement':float(gap/np.prod(grid.shape)),
        'sections':sec,
        'uncertainty_calibrated_on_people':False,
        'actual_absolute_scale_verified':False,
        'limitations':['Morphological erosion/dilation is a diagnostic for segmentation perturbations, not a probabilistic CI.',
                       'This does not bound true human body geometry or clothing offset.',
                       'Camera errors and depth-model errors are not included.'],
    }
    return categories,report


def save_silhouette_sensitivity(out_dir, categories,report):
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'sensitivity_volumes.npz',
                        eroded=categories['eroded'].occupancy,
                        nominal=categories['nominal'].occupancy,
                        dilated=categories['dilated'].occupancy)
    (out/'sensitivity_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return out/'sensitivity_report.json'
