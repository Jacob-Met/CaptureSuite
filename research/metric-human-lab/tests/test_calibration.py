import numpy as np
import pytest
from metric_human.calibration import solve_perspective_pnp
from metric_human.cameras import Camera


def make_points():
    rng=np.random.default_rng(782)
    a=rng.uniform([-.4,-.2,.25],[.4,.2,1.85],size=(30,3))
    cam=Camera.look_at([1.0,-3.3,1.4],[0,0,1.0],width=512,height=768,
                      focal=800,model='perspective')
    uv,depth=cam.project(a)
    assert (depth>0).all()
    xyz={f'j{i}': p.tolist() for i,p in enumerate(a)}
    pix={f'j{i}': q.tolist() for i,q in enumerate(uv)}
    return xyz,pix,cam


def test_recover_camera_from_noisy_correspondences_with_outlier():
    xyz,pix,truth=make_points()
    rng=np.random.default_rng(2)
    for name in pix:
        pix[name]=(np.array(pix[name])+rng.normal(0,.15,2)).tolist()
    pix['j0']=[30,720]   # intentionally implausible detector keypoint
    out=solve_perspective_pnp(xyz,pix,image_width=512,image_height=768,
                              fx_px=800,fy_px=800,max_accepted_rmse_px=2,
                              coordinate_scale_source='synthetic_meters')
    assert out.n_ransac_inliers>=27
    assert out.n_correspondences==30
    assert 'j0' not in out.inlier_labels
    assert out.reprojection_rmse_px < .6
    assert np.linalg.norm(out.camera.translation-truth.translation)<.03
    assert np.linalg.norm(out.camera.rotation-truth.rotation)<.02
    assert not out.to_dict()['metric_body_geometry_independently_verified']


def test_reject_coplanar_sparse_or_inconsistent_input():
    xyz,pix,_=make_points()
    with pytest.raises(ValueError,match='six'):
        solve_perspective_pnp({k:xyz[k] for k in list(xyz)[:5]},pix,
                              image_width=512,image_height=768,fx_px=800,fy_px=800)
    plane={k:[a[0],a[1],1.0] for k,a in xyz.items()}
    with pytest.raises(ValueError,match='plane'):
        solve_perspective_pnp(plane,pix,image_width=512,image_height=768,fx_px=800,fy_px=800)
    wrong={k:[50,50] for k in pix}
    with pytest.raises(ValueError):
        solve_perspective_pnp(xyz,wrong,image_width=512,image_height=768,fx_px=800,fy_px=800)
