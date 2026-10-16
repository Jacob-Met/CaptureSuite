import numpy as np
import trimesh
import pytest

from metric_human.cameras import Camera
from metric_human.render import render_metric_depth
from metric_human.depth_ablation import run_depth_ablation


def test_depth_renderer_z_buffer_and_background():
    face = np.array([[-1.,-1.,-1.],[1.,-1.,-1.],[0.,-1.,1.]])
    mesh = trimesh.Trimesh(vertices=np.vstack([face,face+[0,1,0]]),
                           faces=[[0,1,2],[3,4,5]],process=False)
    cam = Camera.look_at([0,-3,0],[0,0,0],width=81,height=81,focal=20.,model='orthographic')
    depth=render_metric_depth(mesh,cam)
    assert depth.shape==(81,81)
    assert depth[40,40]==pytest.approx(2,abs=.03)
    assert np.isnan(depth[0,0])
    assert np.isfinite(depth).sum()>100


def test_perspective_depth_interpolation_and_invalid_near():
    mesh=trimesh.Trimesh(vertices=[[-.8,0,-.5],[.8,1,-.5],[0,2,.5]],faces=[[0,1,2]],process=False)
    cam=Camera.look_at([0,-1,0],[0,0,0],width=61,height=61,focal=40.,model='perspective')
    z=render_metric_depth(mesh,cam)
    assert np.isfinite(z).sum()>0
    assert np.nanmin(z)>0
    # Analytic intersection of this triangle plane with the center camera ray.
    assert z[30,30]==pytest.approx(2.25,abs=1e-5)
    with pytest.raises(ValueError):render_metric_depth(mesh,cam,near_m=0)


def test_depth_ablation_completes_on_procedural_truth(tmp_path):
    result=run_depth_ablation(tmp_path,resolution=26,view_counts=(1,2,4),image_width=100,image_height=150)
    assert (tmp_path/'depth_ablation.json').exists()
    assert len(result['rows'])==3
    assert result['human_measurement_accuracy_validated'] is False
    assert result['known_camera_and_metric_scale'] is True
    for r in result['rows']:
        assert 0<=r['silhouette']['voxel_iou']<=1
        assert 0<=r['oracle_metric_depth']['voxel_iou']<=1
        assert r['oracle_metric_depth']['false_positive_voxels']<=r['silhouette']['false_positive_voxels']
