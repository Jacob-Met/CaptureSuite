"""Two-stage silhouette fit: translation-invariant shape, then pixelwise refine.

Experimental solver for small principal-point/cropping disturbances; no
claims of true camera calibration or calibrated real-human uncertainty.
"""
from __future__ import annotations
import numpy as np
from .prior import Prior,fit_prior_to_evidence
from .reconstruct import View
from .view_centering import recenter_views_from_prior


def fit_prior_coarse_to_fine(prior:Prior,views:list[View],*,
                             shift_limit_px:int=3,regularization:float=.0001,
                             coarse_maxiter:int=18,fine_maxiter:int=18,
                             **common):
    if not isinstance(shift_limit_px,int) or not 0<=shift_limit_px<=8:
        raise ValueError('shift_limit_px must be integer 0..8')
    if 'initial' in common or 'silhouette_loss_mode' in common or 'alignment_radius_px' in common:
        raise ValueError('The coarse-to-fine strategy owns initialization and silhouette loss')
    coarse,initial_report=fit_prior_to_evidence(prior,views,
                          regularization=regularization,maxiter=coarse_maxiter,
                          silhouette_loss_mode='profile',**common)
    x=np.array([initial_report['coefficients'][name] for name in prior.parameter_names],float)
    corrected,centering=recenter_views_from_prior(prior,views,baseline=x,
                                                   max_shift_px=shift_limit_px)
    fine,report=fit_prior_to_evidence(prior,corrected,initial=x,
                          regularization=regularization,maxiter=fine_maxiter,
                          silhouette_loss_mode='pixel_iou',**common)
    report['fit_strategy']='coarse_translation_invariant_then_small_center_adjustment_then_pixel_iou'
    report['coarse_coefficients']=initial_report['coefficients']
    report['coarse_optimization_success']=initial_report['optimization_success']
    report['centering_diagnostic']=centering
    report['limitations'].append('The initial silhouette profile can bias estimated center shifts when model and actual anatomy differ.')
    return fine,report
