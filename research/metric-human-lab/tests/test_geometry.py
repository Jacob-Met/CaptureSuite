import numpy as np
import pytest

from metric_human.cameras import Camera
from metric_human.landmarks import Observation, triangulate
from metric_human.volume import Grid, intersection_over_union
from metric_human.reconstruct import View, fuse_views, leave_one_out_sensitivity
from metric_human.synthetic import Figure, orbit_cameras, figure_sdf
from metric_human.measurements import geometric_report
from metric_human.bench import default_grid, build_scene


def test_camera_look_at_center_and_behind():
    camera=Camera.look_at([0,-3,1],[0,0,1],model='perspective',focal=420)
    uv,z=camera.project(np.array([[0,0,1],[0,-4,1]]))
    assert uv[0,0] == pytest.approx(camera.cx)
    assert uv[0,1] == pytest.approx(camera.cy)
    assert z[0] == pytest.approx(3)
    assert z[1] < 0
    assert np.allclose(Camera.from_dict(camera.to_dict()).rotation,camera.rotation)


def test_triangulation_recovers_known_point():
    point=np.array([.22,.16,1.38])
    cameras=orbit_cameras(4,model='perspective')
    obs=[]
    for cam in cameras:
        uv,z=cam.project(point.reshape(1,3))
        assert z[0] > 0
        obs.append(Observation('elbow',cam,tuple(uv[0])))
    result=triangulate(obs)['elbow']
    assert result['status']=='triangulated'
    assert np.allclose(result['xyz_world_units'],point,atol=1e-5)
    assert result['reprojection_rmse_pixels']<1e-6


def test_triangulation_rejects_single_view_and_parallel_rays():
    camera=orbit_cameras(1)[0]
    one=Observation('wrist',camera,(45,35))
    assert triangulate([one])['wrist']['status']=='unobservable'
    assert triangulate([one,one])['wrist']['status']=='unobservable'


def test_visual_hull_gains_information_from_more_views():
    grid=default_grid(42)
    truth,mesh,views=build_scene(grid,max_views=8,width=160,height=240)
    one=fuse_views(views[:1],grid)
    four=fuse_views(views[::2],grid)
    eight=fuse_views(views,grid)
    assert intersection_over_union(one.occupancy,truth)<intersection_over_union(four.occupancy,truth)
    assert intersection_over_union(four.occupancy,truth)<=intersection_over_union(eight.occupancy,truth)+.025
    assert one.occupancy.sum() > four.occupancy.sum() >= eight.occupancy.sum()
    assert truth.sum()>0
    assert eight.metadata['scale_source']=='calibrated_camera_geometry'
    assert len(eight.mesh().faces)>100


def test_empty_or_conflicting_views_are_handled():
    grid=default_grid(20)
    camera=orbit_cameras(1,width=100,height=120)[0]
    empty=View(camera,np.zeros((120,100),bool),label='empty')
    no=fuse_views([empty],grid)
    assert not no.occupancy.any()
    with pytest.raises(ValueError):no.mesh()
    with pytest.raises(ValueError):fuse_views([],grid)
    with pytest.raises(ValueError):fuse_views([empty],grid,min_fraction=0)
    with pytest.raises(ValueError):View(camera,np.zeros((99,100),bool))


def test_depth_front_space_carving_reduces_occupancy():
    grid=Grid((-.6,-.6,0),(.6,.6,1),(20,20,20))
    camera=Camera.look_at([0,-3,.5],[0,0,.5],width=100,height=100,focal=60,model='orthographic')
    fg=np.ones((100,100),bool)
    unconstrained=fuse_views([View(camera,fg)],grid)
    # All visible body surfaces must be >=2.9 camera-z (free space in front).
    depth=np.full((100,100),2.9)
    constrained=fuse_views([View(camera,fg,depth_m=depth,depth_tolerance_m=0)],grid)
    assert constrained.occupancy.sum() < unconstrained.occupancy.sum()
    assert constrained.occupancy.sum() > 0
    assert np.all(constrained.occupancy <= unconstrained.occupancy)


def test_metric_report_does_not_claim_unknown_scale():
    grid=default_grid(25)
    voxel=np.zeros(grid.shape,bool)
    voxel[10:15,4:10,2:15]=True
    r=geometric_report(voxel,grid,scale_source='inferred_unvalidated',cross_section_heights=(.75,))
    assert r['metric_scale_verified'] is False
    assert 'x_width' in r['axis_extents_m_if_scaled']
    assert isinstance(r['horizontal_sections'],list)


def test_view_leave_one_out_diagnostic_is_explicitly_not_confidence():
    grid=default_grid(23)
    _,_,views=build_scene(grid,max_views=4,width=120,height=160)
    result=leave_one_out_sensitivity(views,grid)
    assert result['available']
    assert len(result['voxel_classification_change_fraction'])==4
    assert all(v>=0 for v in result['voxel_classification_change_fraction'].values())


def test_anthropometric_shape_prior_is_not_fixed():
    p=np.array([[.35,0,1.35]])
    slim=figure_sdf(p,Figure(width_scale=.7))[0]
    wide=figure_sdf(p,Figure(width_scale=1.4))[0]
    assert wide < slim


def test_unknown_provenance_never_counts_as_calibrated():
    grid=default_grid(23)
    vox=np.zeros(grid.shape,bool);vox[1:3,1:3,1:5]=True
    report=geometric_report(vox,grid,scale_source='some_unrecognized_label')
    assert report['metric_scale_verified'] is False
    assert report['metric_scale_anchored'] is False
    anchored=geometric_report(vox,grid,scale_source='user_height_anchor')
    assert anchored['metric_scale_anchored'] is True
    assert anchored['metric_scale_verified'] is False
    assert anchored['human_measurement_accuracy_validated'] is False


def test_uncalibrated_perspective_projection_has_exact_global_scale_ambiguity():
    # For points x and world->camera transform R*x+t, multiplying both
    # world geometry and camera translation by scale preserves pixel u,v.
    cam=Camera.look_at([1.,-4.,1.1],[0.,0.,1.0],model='perspective',focal=620)
    xyz=np.array([[.13,0,1.2],[-.3,.2,.5],[.01,-.1,1.6]])
    uv,z=cam.project(xyz)
    s=1.4
    scaled=Camera(cam.rotation.copy(),cam.translation*s,cam.width,cam.height,
                  cam.fx,cam.fy,cam.cx,cam.cy,cam.model)
    uv_scaled,z_scaled=scaled.project(xyz*s)
    assert np.allclose(uv,uv_scaled,atol=1e-10)
    assert np.allclose(z*s,z_scaled)
    # Uncalibrated photographs alone cannot pick which of these metric sizes
    # represents a true person; any method predicting one must use priors.
