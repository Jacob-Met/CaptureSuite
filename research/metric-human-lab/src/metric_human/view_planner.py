"""Deterministic active-view planning using local silhouette-shape observability.

This is an *experimental camera-placement heuristic*. It asks which directions
make parameters of a supplied anatomical mesh basis most distinguishable in a
silhouette, assuming a rigid pose, known camera framing and corrected masks.
It is NOT an accuracy estimate, a posterior uncertainty distribution, or a
method of recovering absolute physical scale from unknown images.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

from .cameras import Camera
from .prior import Prior
from .synthetic import render_silhouette


@dataclass(frozen=True)
class CandidateView:
    label: str
    camera: Camera


def orbit_candidates(prior: Prior, *, count: int = 12, width: int = 192,
                     height: int = 256, elevation_deg: float = 0.) -> list[CandidateView]:
    """Produce fixed, nominal orthographic viewpoints of a given shape prior.

    The body faces world -Y; views start with the frontal camera at 0 degrees.
    Perspective/scale calibration of actual RGB images is not performed here.
    """
    if not isinstance(count,int) or not 2 <= count <= 72:
        raise ValueError('candidate count must be 2..72')
    if width < 48 or height < 48 or not np.isfinite(elevation_deg) or abs(elevation_deg) > 60:
        raise ValueError('Invalid synthetic camera size or elevation')
    vertices = np.asarray(prior.vertices_m, dtype=float)
    bbox = np.ptp(vertices,axis=0)
    if np.any(bbox <= 1e-5):
        raise ValueError('Degenerate reference mesh')
    target = (vertices.min(axis=0)+vertices.max(axis=0))/2
    focal = min((height-1)*.84/bbox[2], (width-1)*.83/max(bbox[0],bbox[1]))
    r = max(2.5,3.*bbox[2])
    e = np.deg2rad(elevation_deg)
    entries = []
    for i in range(count):
        az = 2*np.pi*i/count
        eye = target + r*np.array([np.sin(az)*np.cos(e),-np.cos(az)*np.cos(e),np.sin(e)])
        entries.append(CandidateView(f'azimuth_{360*i/count:06.2f}deg',
                        Camera.look_at(eye,target,width=width,height=height,
                                       focal=focal,model='orthographic')))
    return entries


def _distance_field(mask: np.ndarray,clip_px: float) -> np.ndarray:
    fg = np.asarray(mask,dtype=bool)
    if fg.ndim != 2 or not np.any(fg) or np.all(fg):
        raise ValueError('Unusable silhouette: object must occupy part of image')
    inside = distance_transform_edt(fg)
    outside = distance_transform_edt(~fg)
    return np.clip(inside-outside,-clip_px,clip_px).astype(np.float64)


def silhouette_information(prior: Prior,camera: Camera, *, baseline=None,
                           selected_parameters=None,step: float = .3,
                           mask_noise_px: float = 2.,band_px: float = 8.):
    """Finite-difference information from changes in rendered mask SDF.

    Returns a PSD matrix in local *shape-coefficient* coordinates. The matrix
    is a relative information score under a hypothetical independent-pixel
    model, not a statistically calibrated covariance on real people.
    """
    n = len(prior.parameter_names)
    coefficients = np.zeros(n,dtype=float) if baseline is None else np.asarray(baseline,float)
    if coefficients.shape != (n,) or not np.isfinite(coefficients).all():
        raise ValueError('Bad coefficient baseline')
    names = tuple(prior.parameter_names if selected_parameters is None else selected_parameters)
    if not names or len(names)>32 or len(set(names))!=len(names) or any(name not in prior.parameter_names for name in names):
        raise ValueError('Choose 1..32 distinct known shape parameters')
    if not np.isfinite(step) or not 0 < step <= 1 or not np.isfinite(mask_noise_px) or mask_noise_px<=0:
        raise ValueError('Invalid finite-difference step or mask noise')
    if not np.isfinite(band_px) or band_px<2 or band_px>50:
        raise ValueError('Boundary band must be 2..50 pixels')
    baseline_mask = render_silhouette(prior.generate(coefficients),camera)
    signed = _distance_field(baseline_mask,band_px)
    boundary = np.abs(signed)<=band_px*.9
    count = int(boundary.sum())
    if count<20:
        raise ValueError('Too few visible silhouette-boundary pixels for observability')
    jac = np.empty((count,len(names)),float)
    for column,name in enumerate(names):
        idx = prior.parameter_names.index(name)
        left=coefficients.copy();right=coefficients.copy()
        left[idx]-=step;right[idx]+=step
        minus = _distance_field(render_silhouette(prior.generate(left),camera),band_px)
        plus = _distance_field(render_silhouette(prior.generate(right),camera),band_px)
        jac[:,column] = ((plus-minus)/(2*step))[boundary]
    # Normalize by sampled boundary size to avoid rewarding large images only.
    fisher=jac.T@jac / (count*mask_noise_px**2)
    fisher=(fisher+fisher.T)*.5
    return fisher, {'boundary_pixels':count,
                    'per_parameter_rms_boundary_shift_px_per_coefficient':
                        dict(zip(names,np.sqrt(np.mean(jac**2,axis=0)).round(5).tolist())),
                    'silhouette_area_pixels':int(np.asarray(baseline_mask).sum())}


def plan_views(prior: Prior,candidates: list[CandidateView], *, select: int=4,
               baseline=None, selected_parameters=None,step: float=.3,
               mask_noise_px: float=2.,band_px: float=8.,
               prior_precision: float=.25) -> dict:
    """Greedily maximize logdet(prior_precision*I + cumulative information).

    This chooses complementarity of *expected* silhouettes; it does not use
    observed photos, and cannot guarantee shape uniqueness or camera coverage.
    """
    if not candidates or not 1 <= select <= len(candidates):
        raise ValueError('Selection count must be within candidate count')
    if len({c.label for c in candidates})!=len(candidates):
        raise ValueError('Candidate labels must be unique')
    if not np.isfinite(prior_precision) or prior_precision<=0:
        raise ValueError('prior_precision must be positive')
    names = tuple(prior.parameter_names if selected_parameters is None else selected_parameters)
    matrices=[];meta=[]
    for candidate in candidates:
        M,m=silhouette_information(prior,candidate.camera,baseline=baseline,
                selected_parameters=names,step=step,mask_noise_px=mask_noise_px,band_px=band_px)
        matrices.append(M)
        meta.append({'label':candidate.label,'camera':candidate.camera.to_dict(),**m,
                     'information_trace':float(np.trace(M))})
    P=len(names)
    F=np.zeros((P,P),float)
    order=[];selected=[]
    base=np.eye(P)*prior_precision
    logdet0=np.linalg.slogdet(base)[1]
    for slot in range(select):
        scores=[]
        for j,M in enumerate(matrices):
            if j in selected:
                scores.append(-np.inf)
            else:
                sign,ld=np.linalg.slogdet(base+F+M)
                scores.append(float(ld) if sign>0 else -np.inf)
        best=int(np.argmax(scores))
        previous=np.linalg.slogdet(base+F)[1]
        F+=matrices[best]
        selected.append(best)
        ev=np.linalg.eigvalsh(F)
        order.append({'rank':slot+1,'label':candidates[best].label,
                      'incremental_logdet_information':float(scores[best]-previous),
                      'relative_logdet_gain_since_prior':float(scores[best]-logdet0),
                      'local_information_rank':int(np.sum(ev>max(float(ev.max())*1e-5,1e-8))),
                      'information_eigenvalues':ev.round(8).tolist()})
    eig=np.linalg.eigvalsh(F)
    return {
        'method':'local_silhouette_fisher_greedy_view_selection',
        'camera_setup':'synthetic_known_orthographic_not_inferred_from_person_photos',
        'parameter_names':list(names),'selected':order,'candidates':meta,
        'information_eigenvalues':eig.round(8).tolist(),
        'local_observable_rank_without_prior':int(np.sum(eig>max(float(eig.max())*1e-5,1e-8))),
        'parameter_count':P,
        'step':float(step),'assumed_boundary_noise_px':float(mask_noise_px),
        'band_px':float(band_px),'prior_precision':float(prior_precision),
        'reconstruction_quality_validated':False,
        'human_measurement_accuracy_validated':False,
        'absolute_scale_inferred':False,
        'limitations':[
            'A design-time camera proposal using a generic shape basis, not acquired user images.',
            'The local coefficient information model assumes independent silhouette-boundary perturbations.',
            'Depth, clothing, camera calibration error, pose change, and scale ambiguity are not represented.',
            'Eigenvalues are local heuristic sensitivity values, not calibrated dimensional confidence.',
            'View selection must be tested against held-out geometry and actual photographs before relying on it.',
        ]}


def save_view_plan(path,plan):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(plan,indent=2),encoding='utf-8')
    return path
