"""Data-independent parametric body-prior fitting from multiple observations.

The repository ships no learned or rights-restricted shape space. Operators
may supply a *licensed* prior (base mesh + corresponded blend-shape deltas).
This explicitly optimizes model parameters against silhouette evidence and
optional metrically triangulated landmark anchors. Nothing is diffused.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
import numpy as np
import cv2
import trimesh
from scipy.optimize import minimize
from .reconstruct import View
from .synthetic import render_silhouette
from .quality import mask_iou
from .render import render_metric_depth
from .silhouette_profiles import silhouette_profile_loss


@dataclass(frozen=True)
class Prior:
    vertices_m: np.ndarray
    faces: np.ndarray
    shape_deltas_m: np.ndarray # [n_parameters, n_vertices,3]
    parameter_names: tuple[str,...]
    landmark_vertex_ids: dict[str,int]
    source: str = 'operator_supplied_body_prior'
    negative_shape_deltas_m: np.ndarray | None = None

    def __post_init__(self):
        v=np.asarray(self.vertices_m)
        f=np.asarray(self.faces)
        d=np.asarray(self.shape_deltas_m)
        if v.ndim!=2 or v.shape[1]!=3 or not len(v):raise ValueError('Invalid base vertices')
        if f.ndim!=2 or f.shape[1]!=3 or not len(f):raise ValueError('Invalid triangle faces')
        if d.ndim!=3 or d.shape[1:]!=v.shape:raise ValueError('Deltas require [parameters, vertices, xyz]')
        if len(self.parameter_names)!=len(d):raise ValueError('One name per shape parameter')
        if self.negative_shape_deltas_m is not None:
            negative=np.asarray(self.negative_shape_deltas_m)
            if negative.shape != d.shape or not np.isfinite(negative).all():
                raise ValueError('Negative shape targets must match and be finite')
        if not np.isfinite(v).all() or not np.isfinite(d).all():raise ValueError('Nonfinite prior coordinates')
        if f.min()<0 or f.max()>=len(v):raise ValueError('Out-of-bounds face')
        if any(i<0 or i>=len(v) for i in self.landmark_vertex_ids.values()):
            raise ValueError('Out-of-bounds landmark vertex mapping')

    def generate(self,coefficients):
        coeffs=np.asarray(coefficients,float)
        if coeffs.shape!=(len(self.shape_deltas_m),):
            raise ValueError('Parameter vector dimension mismatch')
        positive=np.maximum(coeffs,0)
        newv=np.asarray(self.vertices_m,dtype=float)+np.tensordot(
            positive,np.asarray(self.shape_deltas_m,dtype=float),axes=(0,0))
        if self.negative_shape_deltas_m is None:
            # Backwards compatible linear basis: a negative coefficient negates its delta.
            newv+=np.tensordot(np.minimum(coeffs,0),
                    np.asarray(self.shape_deltas_m,dtype=float),axes=(0,0))
        else:
            # Paired MakeHuman targets contain independent decreasing deformations.
            newv+=np.tensordot(np.maximum(-coeffs,0),
                    np.asarray(self.negative_shape_deltas_m,dtype=float),axes=(0,0))
        return trimesh.Trimesh(vertices=newv,faces=self.faces,process=False)

    def save(self,path):
        kwargs=dict(vertices_m=self.vertices_m,faces=self.faces,
                    shape_deltas_m=self.shape_deltas_m,
                    parameter_names_json=json.dumps(list(self.parameter_names)),
                    landmark_vertex_ids_json=json.dumps(self.landmark_vertex_ids),
                    source=self.source)
        if self.negative_shape_deltas_m is not None:
            kwargs['negative_shape_deltas_m']=self.negative_shape_deltas_m
        np.savez_compressed(path, **kwargs)

    @classmethod
    def load(cls,path):
        with np.load(path,allow_pickle=False) as f:
            return cls(f['vertices_m'],f['faces'],f['shape_deltas_m'],
                       tuple(json.loads(str(f['parameter_names_json']))),
                       {str(k):int(v) for k,v in json.loads(str(f['landmark_vertex_ids_json'])).items()},
                       str(f['source']),
                       negative_shape_deltas_m=(f['negative_shape_deltas_m']
                                                if 'negative_shape_deltas_m' in f else None))


def best_silhouette_alignment(predicted, observed, *, search_radius_px:int=0,
                              shift_penalty_per_px_squared:float=.002):
    """Find a limited nuisance 2D principal-point adjustment for one view.

    The result is the best intersection-over-union in a small integer shift
    window, with a quadratic penalty preventing free camera drift. It does NOT
    correct arbitrary segmentation deformation, rotation, or wrong anatomy.
    Offsets represent shifts applied to the predicted silhouette to match the
    observed one. A nonzero fit radius is an EXPLICIT opt-in.
    """
    pred=np.asarray(predicted,bool)
    obs=np.asarray(observed,bool)
    if pred.shape!=obs.shape or pred.ndim!=2:
        raise ValueError('Silhouettes must have matching HxW dimensions')
    if not isinstance(search_radius_px,int) or not 0<=search_radius_px<=12:
        raise ValueError('search_radius_px must be integer 0..12')
    if not np.isfinite(shift_penalty_per_px_squared) or shift_penalty_per_px_squared<0:
        raise ValueError('shift penalty must be finite and nonnegative')
    if not search_radius_px:
        iou=mask_iou(pred,obs)
        return float(iou), (0,0), float(iou)
    padded=np.pad(obs.astype(np.float32),search_radius_px,constant_values=0.)
    corr=cv2.matchTemplate(padded,pred.astype(np.float32),cv2.TM_CCORR)
    predicted_area=float(pred.sum())
    observed_area=float(obs.sum())
    intersections=np.clip(corr,0,min(predicted_area,observed_area))
    union=np.maximum(predicted_area+observed_area-intersections,1.)
    ious=intersections/union
    yy,xx=np.indices(ious.shape)
    dx=xx-search_radius_px
    dy=yy-search_radius_px
    scored=ious-shift_penalty_per_px_squared*(dx**2+dy**2)
    cy,cx=np.unravel_index(np.argmax(scored),scored.shape)
    return float(ious[cy,cx]),(int(dx[cy,cx]),int(dy[cy,cx])),float(scored[cy,cx])


def fit_prior_to_evidence(
    prior:Prior,views:list[View],*,
    landmark_positions_world:dict[str,tuple[float,float,float]] | None=None,
    initial=None,regularization=.004,landmark_weight=1.,depth_weight=0.,maxiter=80,
    lower_bound=-1.,upper_bound=1.,alignment_radius_px=0,
    alignment_penalty_per_px_squared=.002,
    silhouette_loss_mode='pixel_iou',validation_views:list[View] | None=None,
):
    """Optimize blend coefficients against rendered silhouettes and 3D anchors.

    Returns fit diagnostics. Landmark residuals must be supplied in same
    world/frame units as cameras, not uninterpreted normalized model coords.
    """
    if not views:raise ValueError('At least one calibrated silhouette view required')
    validation_views=list(validation_views or [])
    if validation_views:
        training_labels=[v.label for v in views if v.label]
        validation_labels=[v.label for v in validation_views if v.label]
        if len(training_labels)!=len(set(training_labels)) or len(validation_labels)!=len(set(validation_labels)):
            raise ValueError('Nonempty camera labels must be unique within training and validation')
        if set(training_labels)&set(validation_labels):
            raise ValueError('A validation camera label cannot also be trained on')
        if any(a is b for a in views for b in validation_views):
            raise ValueError('A validation view cannot also be a training view')
    if regularization<0 or landmark_weight<0 or depth_weight<0 or maxiter<1:
        raise ValueError('Invalid optimization settings')
    if not isinstance(alignment_radius_px,int) or not 0<=alignment_radius_px<=12:
        raise ValueError('alignment_radius_px must be integer 0..12')
    if not np.isfinite(alignment_penalty_per_px_squared) or alignment_penalty_per_px_squared<0:
        raise ValueError('Invalid alignment penalty')
    if silhouette_loss_mode not in ('pixel_iou','profile'):
        raise ValueError('Invalid silhouette loss mode')
    n=len(prior.parameter_names)
    if n==0:raise ValueError('Prior has zero editable parameters')
    x0=np.zeros(n) if initial is None else np.asarray(initial,float)
    if x0.shape!=(n,):raise ValueError('Initial coefficients do not match prior')
    landmarks=landmark_positions_world or {}
    for key in landmarks:
        if key not in prior.landmark_vertex_ids:
            raise ValueError(f'Prior has no landmark vertex mapping for {key}')
    targets={k:np.asarray(x,float) for k,x in landmarks.items()}
    if any(t.shape!=(3,) or not np.isfinite(t).all() for t in targets.values()):
        raise ValueError('Landmark positions must be finite xyz world coordinates')

    depth_evidence=[v for v in views if v.depth_m is not None]
    if depth_weight and not depth_evidence:
        raise ValueError('Positive depth weight requires independently metric depth evidence')

    def depth_loss(m):
        if not depth_weight:
            return 0.
        errors=[];weights=[]
        for v in depth_evidence:
            observed=np.asarray(v.depth_m,dtype=float)
            valid=np.asarray(v.mask,bool)&np.isfinite(observed)&(observed>0)
            if not np.any(valid):
                raise ValueError('Calibrated metric depth has no foreground surface samples')
            predicted=render_metric_depth(m,v.camera)
            overlapping=valid&np.isfinite(predicted)
            # Normalize to a 5cm dimensional scale, robustly cap large gaps.
            # The number of usable observed pixels stays in the denominator;
            # absent predicted depth receives a penalty too.
            residual=np.minimum(np.abs(predicted[overlapping]-observed[overlapping]), .20)/.05
            numerator=float(np.dot(residual,residual))
            loss=(numerator + float(np.sum(valid&~np.isfinite(predicted)))*4.) / float(np.sum(valid))
            errors.append(loss);weights.append(v.weight)
        return float(np.average(errors,weights=weights))

    def objective(x):
        m=prior.generate(x)
        weighted=np.asarray([v.weight for v in views]);weighted/=weighted.sum()
        if silhouette_loss_mode=='profile':
            losses=np.asarray([silhouette_profile_loss(render_silhouette(m,v.camera),v.mask)
                               for v in views])
            shape_loss=float(np.dot(weighted,losses))
        else:
            silhouettes=np.asarray([best_silhouette_alignment(
                render_silhouette(m,v.camera),v.mask,search_radius_px=alignment_radius_px,
                shift_penalty_per_px_squared=alignment_penalty_per_px_squared)[2] for v in views])
            shape_loss=float(np.dot(weighted,(1-silhouettes)**2))
        prior_penalty=float(regularization*np.dot(x,x))
        if targets:
            vertices=m.vertices
            errors=[np.sum((vertices[prior.landmark_vertex_ids[name]]-point)**2)
                    for name,point in targets.items()]
            point_penalty=float(landmark_weight*np.mean(errors))
        else:point_penalty=0.
        return shape_loss+prior_penalty+point_penalty+depth_weight*depth_loss(m)

    opt=minimize(objective,x0,method='Powell',bounds=[(lower_bound,upper_bound)]*n,
                 options={'maxiter':maxiter,'xtol':2e-3,'ftol':1e-5})
    finished=prior.generate(opt.x)
    per_view=[]
    for v in views:
        img=render_silhouette(finished,v.camera)
        iou,shift,regularized=best_silhouette_alignment(img,v.mask,
            search_radius_px=alignment_radius_px,
            shift_penalty_per_px_squared=alignment_penalty_per_px_squared)
        per_view.append({'view':v.label,'silhouette_iou':mask_iou(img,v.mask),
                         'aligned_silhouette_iou':iou,
                         'pixel_shift_to_align_prediction_xy':list(shift),
                         'regularized_alignment_score':regularized})
    landmark_error={key:float(np.linalg.norm(finished.vertices[prior.landmark_vertex_ids[key]]-p))
                    for key,p in targets.items()}
    # Held-out cameras are never referenced in the fit objective, including
    # the landmark/depth terms. This is predictive image agreement, not mm truth.
    from .quality import heldout_view_diagnostics
    independent_projection = (heldout_view_diagnostics(finished,validation_views)
                              if validation_views else [])
    validation_weighted_iou=(float(np.average([r['silhouette_iou'] for r in independent_projection],
                                         weights=[v.weight for v in validation_views]))
                              if independent_projection else None)
    diagnostics={'status':'fit_to_observation_proxies_not_validated_person_geometry',
                 'source_prior':prior.source,'optimization_success':bool(opt.success),
                 'objective':float(opt.fun),'iterations':int(opt.nit),
                 'coefficients':dict(zip(prior.parameter_names,[float(x) for x in opt.x])),
                 'per_view_reprojection':per_view,
                 'held_out_validation':{
                     'available':bool(validation_views),
                     'num_views':len(validation_views),
                     'weighted_silhouette_iou':validation_weighted_iou,
                     'per_view_reprojection':independent_projection,
                     'status':'separate_view_reprojection_only_not_real_dimension_accuracy',
                     'limitations':['Held-out image agreement can expose overfitting, but cannot prove invisible geometry or metric scale.',
                                    'Views of the same person are not statistically independent subjects.',
                                    'Model or camera errors shared by training and validation can escape this check.']},
                 'landmark_euclidean_error_world_units':landmark_error,
                 'regularization':regularization,
                 'landmark_weight':landmark_weight,
                 'depth_weight':float(depth_weight),
                 'alignment_radius_px':alignment_radius_px,
                 'silhouette_loss_mode':silhouette_loss_mode,
                 'alignment_penalty_per_px_squared':alignment_penalty_per_px_squared,
                 'metric_depth_views_used':len(depth_evidence) if depth_weight else 0,
                 'depth_error_objective_at_solution':depth_loss(finished) if depth_weight else None,
                 'limitations':['Model expressivity restricted to supplied blend-shape basis.',
                                'Fit quality and trusted physical dimensions depend on licenses, cameras, model bias and independent validation.',
                                'High silhouette IoU is not proof of accurate hidden body geometry.',
                                'Any depth residual requires independently calibrated surface depths and correct cameras.',
                                '2D pixel shift alignment is a limited image-centering nuisance fit, not recovery of actual camera pose.',
                                'Translation-invariant silhouettes preserve some measurements but discard potentially useful local correspondence.']}
    return finished,diagnostics
