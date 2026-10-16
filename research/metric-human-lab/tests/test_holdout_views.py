"""Image-view holdouts test predictive silhouette validity, not actual mm body accuracy."""
import json
import subprocess
import sys

import cv2
import numpy as np
import pytest
import trimesh

from metric_human.cameras import Camera
from metric_human.cli import fit_prior_manifest
from metric_human.prior import Prior, fit_prior_to_evidence
from metric_human.reconstruct import View
from metric_human.synthetic import render_silhouette


def front_side_fixture():
    box=trimesh.creation.box(extents=(.4,.2,1.0))
    box.apply_translation([0,0,.7])
    verts=box.vertices.copy()
    delta=np.zeros_like(verts)
    delta[:,1]=verts[:,1]*.8
    prior=Prior(verts,box.faces,delta[None],('torso_depth',),{},source='synthetic_hidden_depth')
    target=prior.generate([.9])
    cameras=[Camera.look_at([0,-3,.7],[0,0,.7],width=128,height=160,focal=110,model='orthographic'),
             Camera.look_at([3,0,.7],[0,0,.7],width=128,height=160,focal=110,model='orthographic')]
    views=[View(cam,render_silhouette(target,cam),label=label)
           for cam,label in zip(cameras,['front','side'])]
    return prior,views


def test_train_silhouette_can_be_perfect_with_hidden_geometry_wrong():
    prior,(front,side)=front_side_fixture()
    fitted,diagnostics=fit_prior_to_evidence(prior,[front],validation_views=[side],
                                             regularization=.0001,maxiter=22)
    assert diagnostics['per_view_reprojection'][0]['silhouette_iou']==1.0
    assert diagnostics['coefficients']['torso_depth']==pytest.approx(0,abs=.05)
    holdout=diagnostics['held_out_validation']
    assert holdout['available']
    assert holdout['num_views']==1
    assert holdout['weighted_silhouette_iou']<.75
    # Acquiring the missing side view disambiguates the deliberately concealed depth.
    improved,reported=fit_prior_to_evidence(prior,[front,side],regularization=.0001,maxiter=22)
    assert reported['coefficients']['torso_depth']>.55
    assert not reported['held_out_validation']['available']
    assert improved.bounds[1,1]>fitted.bounds[1,1]


def test_reject_holdout_leakage_and_duplicate_labels():
    prior,(front,side)=front_side_fixture()
    with pytest.raises(ValueError,match='cannot also be trained'):
        fit_prior_to_evidence(prior,[front],validation_views=[front],maxiter=2)
    with pytest.raises(ValueError,match='must be unique'):
        fit_prior_to_evidence(prior,[front,front],validation_views=[side],maxiter=2)


def test_manifest_holdout_and_cli_reprojection(tmp_path):
    prior,views=front_side_fixture()
    prior_file=tmp_path/'prior.npz';prior.save(prior_file)
    entries=[]
    for view in views:
        name=view.label+'.png'
        assert cv2.imwrite(str(tmp_path/name),view.mask.astype(np.uint8)*255)
        entries.append({'label':view.label,'mask':name,'camera':view.camera.to_dict()})
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'views':entries,'scale_source':'synthetic_world_coordinates'}))
    result=subprocess.run([sys.executable,'-m','metric_human','fit-prior',
                           '--input',str(manifest),'--prior',str(prior_file),
                           '--out',str(tmp_path/'out'), '--holdout-label','side',
                           '--silhouette-loss-mode','pixel_iou','--maxiter','22'],
                          capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)['held_out_validation']['weighted_silhouette_iou']<.75
    report=json.loads((tmp_path/'out'/'prior_fit_report.json').read_text())
    assert report['holdout_labels']==['side']
    assert report['trained_view_count']==1
    assert report['mesh_is_confirmed_real_body'] is False
    with pytest.raises(ValueError,match='missing'):
        fit_prior_manifest(manifest,prior_file,tmp_path/'bad',holdout_labels=['overhead'])
    with pytest.raises(ValueError,match='cannot remove every'):
        fit_prior_manifest(manifest,prior_file,tmp_path/'bad2',holdout_labels=['side','front'])


def test_holdout_ignores_landmarks_from_validation_camera(tmp_path):
    prior,views=front_side_fixture()
    mesh=prior.generate([.9]);p=np.array([0.,0.,.7]);entries=[]
    for view in views:
        assert cv2.imwrite(str(tmp_path/(view.label+'.png')),view.mask.astype('uint8')*255)
        entries.append({'label':view.label,'mask':view.label+'.png','camera':view.camera.to_dict()})
    # Malformed 2D point on validation camera must never leak into training triangulation.
    obs=[{'label':'made_up','view':'side','uv':[999.,999.]}]
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'views':entries,'landmark_observations':obs}))
    pp=tmp_path/'prior.npz';prior.save(pp)
    report=fit_prior_manifest(manifest,pp,tmp_path/'out',holdout_labels=['side'],maxiter=5)
    assert report['landmark_euclidean_error_world_units']=={}
    assert report['held_out_validation']['num_views']==1


def test_withheld_metric_depth_reports_mm_mismatch_even_when_masks_agree():
    from metric_human.render import render_metric_depth
    from metric_human.quality import heldout_view_diagnostics
    prior,(front,_)=front_side_fixture()
    ground_truth=prior.generate([.9])
    no_depth_fit=prior.generate([0.])
    view=View(front.camera,front.mask,label='front-depth-holdout',
              depth_m=render_metric_depth(ground_truth,front.camera))
    rows=heldout_view_diagnostics(no_depth_fit,[view])
    assert rows[0]['silhouette_iou']==1.0
    depth=rows[0]['metric_depth_validation']
    assert depth['predicted_surface_coverage_fraction']==1.0
    assert depth['surface_depth_mae_mm']>50
    assert depth['overlap_pixels']>100
    matched=heldout_view_diagnostics(ground_truth,[view])[0]['metric_depth_validation']
    assert matched['surface_depth_mae_mm']==pytest.approx(0,abs=.001)


def test_invalid_holdout_depth_and_evidence_weight_rejected():
    prior,(front,_)=front_side_fixture()
    with pytest.raises(ValueError,match='positive foreground'):
        from metric_human.quality import heldout_view_diagnostics
        heldout_view_diagnostics(prior.generate([0]),[
            View(front.camera,front.mask,label='depth',depth_m=np.zeros(front.mask.shape))])
    for weight in [0.,float('nan'),float('inf')]:
        with pytest.raises(ValueError,match='weight'):
            View(front.camera,front.mask,weight=weight)
