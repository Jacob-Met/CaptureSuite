import numpy as np
import pytest
import trimesh

from metric_human.cameras import Camera
from metric_human.prior import Prior, fit_prior_to_evidence
from metric_human.reconstruct import View
from metric_human.render import render_metric_depth
from metric_human.synthetic import render_silhouette


def test_metric_depth_changes_prior_fit_objective_on_known_shape():
    box=trimesh.creation.box(extents=(.4,.2,1.0))
    box.apply_translation((0,0,.7))
    verts=box.vertices.copy()
    # One axis is front/back depth, observable with a front camera's true surface Z.
    d=np.zeros_like(verts);d[:,1]=verts[:,1]*.5
    p=Prior(verts,box.faces,d[None,:,:],('torso_depth',),{})
    actual=p.generate([.7])
    cam=Camera.look_at([0,-2,.7],[0,0,.7],width=120,height=160,focal=90,model='orthographic')
    depths=render_metric_depth(actual,cam)
    view=View(cam,render_silhouette(actual,cam),depth_m=depths)
    predicted0=render_metric_depth(p.generate([0]),cam)
    center=(cam.height//2,cam.width//2)
    assert abs(predicted0[center]-depths[center])>.02
    # Silhouette is deliberately unchanged by torso thickness from this view.
    assert np.array_equal(view.mask,render_silhouette(p.generate([0]),cam))
    _,without=fit_prior_to_evidence(p,[View(cam,view.mask)],
                           depth_weight=0,regularization=.00001,maxiter=40)
    # Negative control: frontal silhouette can't see front/back thickness.
    assert without['coefficients']['torso_depth']==pytest.approx(0,abs=.05)
    fitted,diag=fit_prior_to_evidence(p,[view],depth_weight=.1,
                           regularization=.00001,maxiter=40)
    assert diag['metric_depth_views_used']==1
    assert diag['depth_error_objective_at_solution']<.01
    assert diag['coefficients']['torso_depth']==pytest.approx(.7,abs=.08)
    assert abs(fitted.bounds[1,1]-actual.bounds[1,1])<.01


def test_no_metric_depth_rejects_positive_depth_weight():
    box=trimesh.creation.box()
    p=Prior(box.vertices.copy(),box.faces,(box.vertices*.05)[None,:,:],('size',),{})
    cam=Camera.look_at([0,-3,0],[0,0,0],width=60,height=80,focal=30)
    view=View(cam,render_silhouette(box,cam))
    with pytest.raises(ValueError,match='requires'):
        fit_prior_to_evidence(p,[view],depth_weight=1.)
