"""Controlled evidence of image-shift robustness, not accuracy on people."""
import numpy as np
import pytest
import cv2
import trimesh
from metric_human.cameras import Camera
from metric_human.prior import Prior,best_silhouette_alignment
from metric_human.reconstruct import View
from metric_human.view_centering import recenter_views_from_prior
from metric_human.silhouette_profiles import silhouette_profile,silhouette_profile_loss
from metric_human.robust_fit import fit_prior_coarse_to_fine
from metric_human.synthetic import render_silhouette


def fixture():
    mesh=trimesh.creation.box(extents=(.4,.24,1.2))
    mesh.apply_translation((0,0,.7))
    v=mesh.vertices
    width=np.zeros_like(v); width[:,0]=v[:,0]
    depth=np.zeros_like(v); depth[:,1]=v[:,1]
    prior=Prior(v.copy(),mesh.faces,np.stack([width,depth]),('width','depth'),{})
    camera=Camera.look_at([1.5,-3,.7],[0,0,.7],width=160,height=200,focal=125)
    return prior,camera


def shift(mask,dx,dy):
    h,w=mask.shape
    tr=np.float32([[1,0,dx],[0,1,dy]])
    return cv2.warpAffine(np.asarray(mask,np.uint8),tr,(w,h),flags=cv2.INTER_NEAREST)>0


def test_silhouette_profile_is_strictly_translation_invariant():
    p,c=fixture()
    mask=render_silhouette(p.generate([.2,.35]),c)
    moved=shift(mask,3,-2)
    assert np.array_equal(silhouette_profile(mask),silhouette_profile(moved))
    assert silhouette_profile_loss(mask,moved)==pytest.approx(0,abs=1e-12)
    assert silhouette_profile_loss(mask,render_silhouette(p.generate([-.3,.2]),c))>0


def test_bounded_pixel_alignment_recovers_expected_shift():
    p,c=fixture()
    a=render_silhouette(p.generate([0.,0.]),c)
    b=shift(a,-2,2)
    corrected,offset,regularized=best_silhouette_alignment(a,b,search_radius_px=3)
    assert offset==(-2,2)
    assert corrected> .99
    assert regularized<corrected
    uncorrected,offset0,_=best_silhouette_alignment(a,b)
    assert offset0==(0,0)
    assert uncorrected<corrected


def test_one_time_image_centering_recovers_pure_shift_with_known_shape():
    p,c=fixture()
    a=render_silhouette(p.generate([0.,0.]),c)
    b=shift(a,2,-3)
    obs=View(c,b,label='cam0')
    views,diag=recenter_views_from_prior(p,[obs],max_shift_px=3)
    assert diag['estimated_offsets'][0]['applied_pixel_shift_xy']==[2,-3]
    assert diag['estimated_offsets'][0]['baseline_mask_iou_after']> .99
    assert views[0].camera.cx==c.cx+2
    assert views[0].camera.cy==c.cy-3
    assert diag['camera_orientation_calibrated'] is False


def test_bad_inputs_do_not_silently_claim_reliable_fit():
    p,c=fixture()
    m=render_silhouette(p.generate([0,0]),c)
    with pytest.raises(ValueError,match='Invalid silhouette loss mode'):
        from metric_human.prior import fit_prior_to_evidence
        fit_prior_to_evidence(p,[View(c,m)],silhouette_loss_mode='magical_3d')
    with pytest.raises(ValueError,match='integer 0..12'):
        best_silhouette_alignment(m,m,search_radius_px=13)
    with pytest.raises(ValueError,match='integer 0..16'):
        recenter_views_from_prior(p,[View(c,m)],max_shift_px=-1)


def test_coarse_to_fine_produces_finite_model_on_translated_mask():
    p,c=fixture()
    ref=p.generate([.25,.30])
    front=c
    side=Camera.look_at([3,0,.7],[0,0,.7],width=160,height=200,focal=125)
    views=[View(front,shift(render_silhouette(ref,front),1,1),label='front'),
           View(side,shift(render_silhouette(ref,side),-2,1),label='side')]
    fit,report=fit_prior_coarse_to_fine(p,views,shift_limit_px=3,
                        coarse_maxiter=5,fine_maxiter=5)
    assert np.isfinite(fit.vertices).all()
    assert report['fit_strategy'].startswith('coarse_translation_invariant')
    assert len(report['centering_diagnostic']['estimated_offsets'])==2
    assert report['status']=='fit_to_observation_proxies_not_validated_person_geometry'
    assert report['silhouette_loss_mode']=='pixel_iou'
