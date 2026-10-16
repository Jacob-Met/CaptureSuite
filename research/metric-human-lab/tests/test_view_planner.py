"""Tests demonstrate shape identifiability, not real-body measurement accuracy."""
import json
import subprocess
import sys
import numpy as np
import pytest
import trimesh

from metric_human.prior import Prior
from metric_human.cameras import Camera
from metric_human.view_planner import (CandidateView,orbit_candidates,
                                       silhouette_information,plan_views,save_view_plan)


def box_prior():
    mesh=trimesh.creation.box(extents=(.45,.24,1.3))
    mesh.apply_translation((0,0,.75))
    v=mesh.vertices.copy()
    width=np.zeros_like(v); width[:,0]=v[:,0]*.8
    depth=np.zeros_like(v); depth[:,1]=v[:,1]*1.0
    return Prior(v,mesh.faces,np.stack((width,depth)),('body_width','body_depth'),{},
                 source='procedural_parameter_identifiability_fixture')


def test_complementary_views_expose_orthographic_ambiguities():
    prior=box_prior()
    front=Camera.look_at([0,-3,.75],[0,0,.75],width=160,height=200,focal=130)
    side=Camera.look_at([3,0,.75],[0,0,.75],width=160,height=200,focal=130)
    f,front_d=silhouette_information(prior,front)
    g,side_d=silhouette_information(prior,side)
    # Front silhouette can't constrain body thickness; profile can't constrain width.
    assert f[0,0] > 0.005 and f[1,1] < 1e-12
    assert g[1,1] > 0.005 and g[0,0] < 1e-12
    assert np.linalg.eigvalsh(f+g).min() > 0.005
    assert front_d['silhouette_area_pixels']>100
    report=plan_views(prior,[CandidateView('front',front),CandidateView('side',side)],select=2)
    assert {s['label'] for s in report['selected']}=={'front','side'}
    assert report['local_observable_rank_without_prior']==2
    assert report['absolute_scale_inferred'] is False
    assert report['human_measurement_accuracy_validated'] is False


def test_view_planner_is_reproducible_and_marginal_gain_declines(tmp_path):
    prior=box_prior()
    candidates=orbit_candidates(prior,count=8,width=120,height=170)
    a=plan_views(prior,candidates,select=3)
    b=plan_views(prior,candidates,select=3)
    assert a==b
    assert a['selected'][1]['incremental_logdet_information'] <= a['selected'][0]['incremental_logdet_information'] + 1e-7
    assert a['local_observable_rank_without_prior']==2
    dest=tmp_path/'view-plan.json'
    save_view_plan(dest,a)
    assert json.loads(dest.read_text())==a


def test_input_guards_and_duplicate_candidates():
    prior=box_prior()
    candidates=orbit_candidates(prior,count=3)
    with pytest.raises(ValueError, match='candidate count'):
        orbit_candidates(prior,count=0)
    with pytest.raises(ValueError,match='Selection count'):
        plan_views(prior,candidates,select=4)
    with pytest.raises(ValueError,match='Candidate labels'):
        plan_views(prior,[candidates[0],candidates[0]],select=1)
    with pytest.raises(ValueError,match='distinct known'):
        silhouette_information(prior,candidates[0].camera,selected_parameters=['body_width','body_width'])
    with pytest.raises(ValueError,match='step'):
        silhouette_information(prior,candidates[0].camera,step=0)
    with pytest.raises(ValueError,match='prior_precision'):
        plan_views(prior,candidates,select=2,prior_precision=0)


def test_cli_planner_uses_saved_anatomical_prior(tmp_path):
    prior_path=tmp_path/'prior.npz';box_prior().save(prior_path)
    report=tmp_path/'plan.json'
    completed=subprocess.run([sys.executable,'-m','metric_human','plan-views',
                              '--prior',str(prior_path),'--out',str(report),
                              '--candidates','4','--select','2','--width','120','--height','160'],
                             capture_output=True,text=True,check=True)
    data=json.loads(report.read_text())
    assert data['local_observable_rank_without_prior']==2
    assert data['absolute_scale_inferred'] is False
    assert 'real_human_accuracy_validated' in completed.stdout
