import numpy as np
import pytest

from metric_human.stability import silhouette_boundary_sensitivity,save_silhouette_sensitivity
from metric_human.bench import default_grid,build_scene
from metric_human.reconstruct import View


def test_sensitivity_envelope_nested_and_unvalidated(tmp_path):
    grid=default_grid(27)
    _,_,views=build_scene(grid,max_views=4,width=160,height=240)
    categories,report=silhouette_boundary_sensitivity(views,grid,radius_px=4,
                                                        sample_section_z=[1.10])
    assert categories['eroded'].occupancy.sum() <= categories['nominal'].occupancy.sum()
    assert categories['nominal'].occupancy.sum() <= categories['dilated'].occupancy.sum()
    assert report['voxels_of_occupancy_disagreement']>0
    assert report['uncertainty_calibrated_on_people'] is False
    assert not report['sections'][0]['semantics'].startswith('confidence')
    path=save_silhouette_sensitivity(tmp_path,categories,report)
    assert path.is_file()
    with np.load(tmp_path/'sensitivity_volumes.npz') as array:
        assert array['eroded'].shape==grid.shape


def test_stability_zero_perturbation_and_reject_depth(tmp_path):
    grid=default_grid(22)
    _,_,views=build_scene(grid,max_views=2,width=80,height=120)
    categories,report=silhouette_boundary_sensitivity(views,grid,radius_px=0)
    assert report['voxels_of_occupancy_disagreement']==0
    with pytest.raises(ValueError,match='integer'):
        silhouette_boundary_sensitivity(views,grid,radius_px=20)
    depth=np.ones_like(views[0].mask,dtype=float)
    with pytest.raises(ValueError,match='cannot silently ignore'):
        silhouette_boundary_sensitivity([View(views[0].camera,views[0].mask,depth_m=depth)],grid)
