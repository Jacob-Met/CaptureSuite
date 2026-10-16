"""Synthetic negative control: silhouette cannot identify front/back thickness.

Run: python examples/recover_hidden_depth.py
Optional: python examples/recover_hidden_depth.py /path/to/output

Everything is derived from known box geometry and a known camera. It does NOT
claim to reconstruct a person's torso from RGB photographs.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

import numpy as np
import trimesh
from metric_human.cameras import Camera
from metric_human.prior import Prior, fit_prior_to_evidence
from metric_human.reconstruct import View
from metric_human.render import render_metric_depth
from metric_human.synthetic import render_silhouette


def run(out_dir):
    out=Path(out_dir)
    out.mkdir(parents=True,exist_ok=True)
    box=trimesh.creation.box(extents=(.4,.2,1.0))
    box.apply_translation((0,0,.7))
    verts=box.vertices.copy()
    delta=np.zeros_like(verts)
    delta[:,1]=verts[:,1]*.5
    prior=Prior(verts,box.faces,delta[None,:,:],('front_back_depth',),{},
                source='fully_synthetic_depth_negative_control')
    true_parameter=.7
    truth=prior.generate([true_parameter])
    cam=Camera.look_at([0,-2,.7],[0,0,.7],width=120,height=160,focal=90,model='orthographic')
    mask=render_silhouette(truth,cam)
    rendered_depth=render_metric_depth(truth,cam)
    view=View(cam,mask,label='known_front_camera',depth_m=rendered_depth)
    no_depth,_=fit_prior_to_evidence(prior,[View(cam,mask)],regularization=1e-5,
                                 maxiter=45)
    with_depth,diag=fit_prior_to_evidence(prior,[view],depth_weight=.1,
                              regularization=1e-5,maxiter=45)
    p0=(float(no_depth.extents[1])/.2-1)/.5
    p1=float(diag['coefficients']['front_back_depth'])
    equal_silhouettes=bool(np.array_equal(render_silhouette(no_depth,cam),mask))
    result={
        'experiment':'synthetic_ambiguous_frontal_silhouette_vs_known_metric_depth',
        'true_shape_parameter':true_parameter,
        'silhouette_only_parameter_estimate':p0,
        'depth_informed_parameter_estimate':p1,
        'depth_informed_parameter_absolute_error':abs(true_parameter-p1),
        'silhouette_only_projection_equal_to_ground_truth':equal_silhouettes,
        'does_not_demonstrate_neural_relative_depth_accuracy':True,
        'does_not_demonstrate_unmeasured_real_human_body_accuracy':True,
        'camera_is_known':True,
        'physical_scale_is_known':True,
        'observed_depth_is_oracle_mesh_render':True,
        'summary':'Frontal silhouettes cannot identify front/back thickness; exact independently supplied depth breaks this ambiguity under known camera and scale.'
    }
    truth.export(out/'source_mesh.glb')
    with_depth.export(out/'fitted_with_depth.glb')
    no_depth.export(out/'fitted_without_depth.glb')
    prior.save(out/'signed_parameter_prior.npz')
    (out/'report.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result

if __name__=='__main__':
    location=sys.argv[1] if len(sys.argv)>1 else 'demo/shape-depth-identifiability'
    print(json.dumps(run(location),indent=2))
