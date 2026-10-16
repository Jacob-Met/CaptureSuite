import json
import numpy as np
import pytest
import trimesh
from metric_human.body_rig import approximate_rig_from_volume
from metric_human.volume import Grid
from metric_human.motion import sample_shoulder_motion,Gear,evaluate_clip


def make_volume(height=1.6,width=.95):
    grid=Grid((-.7,-.5,0),(.7,.5,2.),(36,28,55))
    c=grid.centers
    inside=((c[:,0]/(width/2))**2+(c[:,1]/.17)**2+((c[:,2]-height/2)/(height/2))**2)<1
    return inside.reshape(grid.shape),grid


def test_bbox_scaled_rig_changes_from_generic_and_executes_motion():
    occ,grid=make_volume(height=1.55,width=.84)
    rig,provenance=approximate_rig_from_volume(occ,grid)
    assert 'bbox' in provenance['method']
    assert not provenance['anatomical_joint_positions_validated']
    assert len(rig.joints)>=10
    left=rig.pose({})['left_wrist'][:3,3]
    right=rig.pose({})['right_wrist'][:3,3]
    assert left[0]<right[0]
    cap=list(rig.capsules({}).values())
    assert min(r for a,b,r in cap)>0
    gear=Gear('armor',trimesh.creation.box(extents=(.15,.2,.1)),
              'chest',(0,.28,.05))
    report=evaluate_clip(rig,[gear],sample_shoulder_motion(7))
    assert report['summary']['armor']['frames_evaluated']==7


def test_rig_does_not_accept_bad_grids():
    occ,grid=make_volume()
    with pytest.raises(ValueError,match='disagree'):
        approximate_rig_from_volume(occ[:3],grid)
    with pytest.raises(ValueError,match='Too few'):
        approximate_rig_from_volume(np.zeros_like(occ),grid)
    narrow=np.zeros_like(occ);narrow[12:22,12:18,0:2]=True
    with pytest.raises(ValueError):
        approximate_rig_from_volume(narrow,grid)
