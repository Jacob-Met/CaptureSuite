import numpy as np
import pytest
import trimesh
from metric_human.motion import (Joint,Rig,Gear,MotionFrame,MotionClip,signed_distance_to_capsule,
                                 evaluate_clip,optimize_offset_along_axis,sample_rig,sample_shoulder_motion)


def test_capsule_exact_signed_distance():
    a=np.array([0,0,0]);b=np.array([0,0,1])
    p=np.array([[0,0,.5],[.2,0,.5],[0,0,2.]])
    dist=signed_distance_to_capsule(p,a,b,.1)
    assert dist.tolist()==pytest.approx([-.1,.1,.9])


def test_fk_moves_elbow_when_shoulder_moves():
    rig=sample_rig()
    initial=rig.pose({})['left_elbow'][:3,3]
    raised=rig.pose({'left_shoulder':(0,1.3,0)})['left_elbow'][:3,3]
    assert raised[2]>initial[2]
    assert raised[0]!=pytest.approx(initial[0])


def test_collision_offset_can_remove_penetration():
    rig=Rig((Joint('pelvis',None,(0,0,0),.0),
             Joint('chest','pelvis',(0,0,1),.12),
             Joint('gear_anchor','pelvis',(0,0,.5),0.0)))
    gear=Gear('plate',trimesh.creation.box(extents=(.06,.06,.12)),anchor_joint='gear_anchor')
    clip=MotionClip('static', (MotionFrame(0,{}), MotionFrame(1,{})))
    before=evaluate_clip(rig,[gear],clip)
    assert before['summary']['plate']['worst_sampled_penetration_mm']>50
    chosen=optimize_offset_along_axis(rig,gear,clip,axis=(1,0,0),max_offset_m=.3,steps=31)
    assert chosen['sampled_safe']
    assert chosen['selected_additional_offset_m']>.1
    assert chosen['worst_sampled_penetration_mm']==0


def test_motion_reports_and_degenerate_inputs():
    rig=sample_rig()
    clip=sample_shoulder_motion(frames=9)
    assert clip.frames[0].seconds==0
    assert clip.frames[-1].seconds==1
    gear=Gear('shoulderplate',trimesh.creation.box(extents=(.16,.12,.14)),
              anchor_joint='chest',local_offset_m=(.25,0,.04))
    report=evaluate_clip(rig,[gear],clip)
    assert len(report['timeline'])==9
    assert report['summary']['shoulderplate']['frames_evaluated']==9
    with pytest.raises(ValueError):rig.pose({'imaginary_joint':(0,0,0)})
    with pytest.raises(ValueError):sample_shoulder_motion(1)
