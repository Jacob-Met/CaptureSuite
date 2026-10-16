import numpy as np
import pytest
import trimesh
from metric_human.cameras import Camera
from metric_human.reconstruct import View
from metric_human.synthetic import render_silhouette
from metric_human.prior import Prior,fit_prior_to_evidence


def test_prior_serialization_and_optimizer_uses_two_sources(tmp_path):
    cube=trimesh.creation.box(extents=(.4,.2,1.2))
    cube.apply_translation((0,0,.75))
    v=cube.vertices.copy()
    dx=np.column_stack((v[:,0]*.7, np.zeros(len(v)),np.zeros(len(v))))
    dz=np.column_stack((np.zeros(len(v)),np.zeros(len(v)),(v[:,2]-.75)*.2))
    prior=Prior(v,cube.faces,np.stack((dx,dz)),('width','height'),{'top':int(np.argmax(v[:,2]))},
                source='synthetic_box_two_deformations')
    path=tmp_path/'prior.npz';prior.save(path)
    prior=Prior.load(path)
    known=np.array([.50,.2])
    original=prior.generate(known)
    cameras=[Camera.look_at([0,-3,.75],[0,0,.75],width=140,height=190,focal=100),
             Camera.look_at([3,0,.75],[0,0,.75],width=140,height=190,focal=100)]
    views=[View(cam,render_silhouette(original,cam),label=f'cam{i}') for i,cam in enumerate(cameras)]
    top=original.vertices[prior.landmark_vertex_ids['top']]
    fitted,report=fit_prior_to_evidence(prior,views,landmark_positions_world={'top':top},
                                        regularization=.0001,landmark_weight=5.,maxiter=50)
    assert report['coefficients']['width']==pytest.approx(.5,abs=.16)
    assert report['coefficients']['height']==pytest.approx(.2,abs=.1)
    assert max(report['landmark_euclidean_error_world_units'].values())<.06
    assert all(row['silhouette_iou']>.85 for row in report['per_view_reprojection'])
    assert fitted.is_watertight


def test_prior_dimension_guards(tmp_path):
    with pytest.raises(ValueError):
        Prior(np.ones((10,3)),np.array([[1,2,11]]),np.ones((2,10,3)),('w','h'),{})
    mesh=trimesh.creation.box()
    v=mesh.vertices
    p=Prior(v,mesh.faces,np.stack((v*.1,)),('size',),{})
    with pytest.raises(ValueError):p.generate([1,2])
