"""Independent experimental motion/gear clearance geometry.

A transparent skeletal-capsule **proxy**, not a deformable-body simulation.
Useful for qualifying collision math and motion interfaces without claiming the
photo reconstruction has a validated personalized rig or real comfort model.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping

import numpy as np
import trimesh
from scipy.spatial.transform import Rotation


@dataclass(frozen=True)
class Joint:
    name: str
    parent: str | None
    rest_offset_m: tuple[float,float,float]
    body_radius_m: float = .06

    def __post_init__(self):
        if len(self.rest_offset_m)!=3 or self.body_radius_m<0:
            raise ValueError('Invalid rig joint coordinates/radius')


@dataclass(frozen=True)
class Rig:
    joints: tuple[Joint,...]

    def __post_init__(self):
        names=set()
        for j in self.joints:
            if j.name in names or (j.parent is not None and j.parent not in names):
                raise ValueError('Rig joint order must be unique and parent-first')
            names.add(j.name)

    def pose(self, angles_rad: Mapping[str,tuple[float,float,float]]):
        """Return joint world positions/rotations using XYZ parent-relative Euler angles."""
        valid={j.name for j in self.joints}
        if any(n not in valid for n in angles_rad):
            raise ValueError('Clip references unknown joint')
        matrices={}
        for j in self.joints:
            local=np.eye(4)
            local[:3,3]=np.asarray(j.rest_offset_m,float)
            local[:3,:3]=Rotation.from_euler('xyz',angles_rad.get(j.name,(0,0,0))).as_matrix()
            matrices[j.name]=(matrices[j.parent]@local if j.parent is not None else local)
        return matrices

    def capsules(self,angles_rad):
        poses=self.pose(angles_rad)
        output={}
        for j in self.joints:
            if j.parent is not None and j.body_radius_m>0:
                pa=poses[j.parent][:3,3]
                pb=poses[j.name][:3,3]
                output[j.name]=(pa,pb,j.body_radius_m)
        return output


@dataclass(frozen=True)
class MotionFrame:
    seconds: float
    angles_rad: dict[str,tuple[float,float,float]]


@dataclass(frozen=True)
class MotionClip:
    name: str
    frames: tuple[MotionFrame,...]
    origin: str = 'procedural'  # not recorded wearer motion

    def __post_init__(self):
        if not self.frames or any(self.frames[i+1].seconds<=self.frames[i].seconds
                                  for i in range(len(self.frames)-1)):
            raise ValueError('Clip must have strictly increasing time samples')


@dataclass(frozen=True)
class Gear:
    name: str
    mesh: trimesh.Trimesh
    anchor_joint: str
    local_offset_m: tuple[float,float,float]=(0,0,0)
    ignored_body_segments: tuple[str,...]=()

    def __post_init__(self):
        if len(self.local_offset_m)!=3 or len(self.mesh.vertices)<3:
            raise ValueError('Gear must be a nonempty triangulated mesh with 3D offset')


def signed_distance_to_capsule(points,a,b,r):
    """Exact signed distances to a straight capsule; negative means penetration."""
    p=np.asarray(points,float)
    a=np.asarray(a,float);b=np.asarray(b,float)
    delta=b-a
    denom=float(delta@delta)
    if denom<1e-16:
        closest=np.broadcast_to(a,p.shape)
    else:
        t=np.clip(((p-a)@delta)/denom,0,1)
        closest=a+t[:,None]*delta
    return np.linalg.norm(p-closest,axis=1)-r


def surface_probe_points(mesh):
    """Deterministic vertices+centroids proxy; not continuous triangle collision."""
    vertices=np.asarray(mesh.vertices,float)
    faces=np.asarray(mesh.faces,int)
    centroids=vertices[faces].mean(axis=1)
    return np.concatenate((vertices,centroids),axis=0)


def pose_gear(gear:Gear,posed_matrices):
    if gear.anchor_joint not in posed_matrices:
        raise ValueError(f'Unknown gear anchor joint {gear.anchor_joint}')
    samples=surface_probe_points(gear.mesh)+np.asarray(gear.local_offset_m)
    m=posed_matrices[gear.anchor_joint]
    return samples@m[:3,:3].T+m[:3,3]


def evaluate_clip(rig:Rig,gear:list[Gear],clip:MotionClip,*,clearance_m=.005):
    """Evaluate sampled gear surface against articulated body-proxy capsules.

    Detects penetrations at sampled points, NOT full continuous collision,
    compressible material, high-speed dynamics, gear/gear, or skin deformation.
    """
    if clearance_m<0:
        raise ValueError('clearance must be >=0')
    output=[]
    by_part={g.name:[] for g in gear}
    for frame in clip.frames:
        transforms=rig.pose(frame.angles_rad)
        segments=rig.capsules(frame.angles_rad)
        for g in gear:
            points=pose_gear(g,transforms)
            parts=[]
            all_segment_clearances=[]
            for body_name,(a,b,radius) in segments.items():
                if body_name in g.ignored_body_segments:
                    continue
                distances=signed_distance_to_capsule(points,a,b,radius)
                lowest=float(np.min(distances))
                all_segment_clearances.append(lowest)
                if lowest<clearance_m:
                    parts.append((body_name,lowest))
            global_min=min(all_segment_clearances,default=float('inf'))
            row={'frame_s':float(frame.seconds),'gear':g.name,
                 'smallest_clearance_m':global_min if np.isfinite(global_min) else None,
                 'interference_segments':[n for n,v in parts if v<0],
                 'near_clearance_segments':[n for n,v in parts if v>=0],
                 'below_target_clearance':global_min<clearance_m,
                 'maximum_sampled_penetration_mm':max(0.,-global_min*1000.)}
            by_part[g.name].append(row)
            output.append(row)
    summary={name:{'worst_sampled_penetration_mm':max(x['maximum_sampled_penetration_mm'] for x in rows),
                   'minimum_sampled_clearance_m':min((x['smallest_clearance_m'] for x in rows
                                                     if x['smallest_clearance_m'] is not None),default=None),
                   'frames_below_target_clearance':sum(x['below_target_clearance'] for x in rows),
                   'frames_with_sampled_penetration':sum(x['maximum_sampled_penetration_mm']>0 for x in rows),
                   'frames_evaluated':len(rows)} for name,rows in by_part.items()}
    return {'clip':clip.name,'status':'sampled_capsule_proxy_not_fabrication_safe',
            'summary':summary,'timeline':output,
            'limitations':['Body represented by joint-to-joint capsules, not personalized deformable mesh.',
                           'Collision tested at sampled gear vertices/triangle centroids, not continuous time or full triangles.',
                           'No garment forces, straps, friction, contact pressure, padding or comfort.']}


def optimize_offset_along_axis(rig:Rig,part:Gear,clip:MotionClip,*,axis=(1.,0.,0.),
                               min_offset_m=0.,max_offset_m=.16,steps=17,clearance_m=.005):
    """Choose smallest *sampled* offset that removes capsule interpenetration.

    If none is safe, choose least penetrative. Offsetting without gear and design
    constraints can create new problems, so this is a demonstration only.
    """
    axis=np.asarray(axis,float)
    n=float(np.linalg.norm(axis))
    if n<1e-8 or steps<2 or max_offset_m<min_offset_m:
        raise ValueError('Invalid offset sweep')
    axis/=n
    candidates=[]
    for offset in np.linspace(min_offset_m,max_offset_m,steps):
        trial=replace(part,local_offset_m=tuple(np.asarray(part.local_offset_m)+axis*offset))
        report=evaluate_clip(rig,[trial],clip,clearance_m=clearance_m)
        worst=float(report['summary'][part.name]['worst_sampled_penetration_mm'])
        near=int(report['summary'][part.name]['frames_below_target_clearance'])
        candidates.append((float(offset),worst,near))
    safe=[x for x in candidates if x[1]==0 and x[2]==0]
    selected=safe[0] if safe else min(candidates,key=lambda x:(x[1],x[2],x[0]))
    return {'selected_additional_offset_m':selected[0],
            'worst_sampled_penetration_mm':selected[1],
            'sampled_safe':bool(safe),
            'frames_below_target_clearance':selected[2],
            'candidates':[{'offset_m':x,'worst_penetration_mm':y, 'frames_below_target_clearance':near}
                          for x,y,near in candidates],
            'status':'one_axis_offset_sweep_over_approximate_body_capsules'}


def sample_rig():
    """Procedural neutral adult-like proxy, NOT fitted or measured from a human."""
    return Rig((Joint('pelvis',None,(0,0,.95),.0),
        Joint('chest','pelvis',(0,0,.46),.15),
        Joint('left_shoulder','chest',(-.22,0,.04),.1),
        Joint('left_elbow','left_shoulder',(-.15,0,-.24),.07),
        Joint('left_wrist','left_elbow',(-.11,0,-.24),.045),
        Joint('right_shoulder','chest',(.22,0,.04),.1),
        Joint('right_elbow','right_shoulder',(.15,0,-.24),.07),
        Joint('right_wrist','right_elbow',(.11,0,-.24),.045),
        Joint('left_hip','pelvis',(-.12,0,-.04),.13),
        Joint('left_knee','left_hip',(-.01,0,-.42),.09),
        Joint('left_ankle','left_knee',(0,0,-.40),.06),
        Joint('right_hip','pelvis',(.12,0,-.04),.13),
        Joint('right_knee','right_hip',(.01,0,-.42),.09),
        Joint('right_ankle','right_knee',(0,0,-.40),.06)))


def sample_shoulder_motion(frames=25):
    if frames<2:raise ValueError('Need >=2 motion frames')
    seq=[]
    for t in np.linspace(0,1,frames):
        rise=np.sin(np.pi*t/2)
        seq.append(MotionFrame(float(t),{'left_shoulder':(0,float(1.3*rise),0),
                                          'right_shoulder':(0,float(-1.3*rise),0)}))
    return MotionClip('both_arms_raised_sample_proxy',tuple(seq))
