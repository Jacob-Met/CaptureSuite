"""Geometric 3D joint/landmark triangulation from independent 2D pose evidence.

Keypoint predictors are pluggable; this module consumes their coordinates,
confidence, and camera geometry. Near-parallel rays are rejected explicitly.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
import numpy as np
from .cameras import Camera


@dataclass(frozen=True)
class Observation:
    label: str
    camera: Camera
    pixel_uv: tuple[float,float]
    confidence: float = 1.0
    provenance: str = "external_keypoint_detector"

    def __post_init__(self):
        if len(self.pixel_uv)!=2 or not np.isfinite(self.pixel_uv).all():
            raise ValueError("pixel_uv must be finite 2D coordinate")
        if not 0 < self.confidence <= 1:
            raise ValueError("confidence must be in (0,1]")


def camera_ray(camera:Camera,uv):
    R=np.asarray(camera.rotation,dtype=float)
    center=-R.T@np.asarray(camera.translation,dtype=float)
    normalized=np.array([(uv[0]-camera.cx)/camera.fx,
                         (uv[1]-camera.cy)/camera.fy,1.0])
    if camera.model=='orthographic':
        origin=center+R.T@np.array([normalized[0],normalized[1],0.])
        ray=R.T@np.array([0.,0.,1.])
    else:
        origin=center
        ray=R.T@normalized
    ray/=np.linalg.norm(ray)
    return origin,ray


def triangulate(observations:list[Observation],*,max_condition=1e7):
    if not observations:
        return {}
    grouped=defaultdict(list)
    for ob in observations:
        grouped[ob.label].append(ob)
    result={}
    for label,obs in grouped.items():
        if len(obs)<2:
            result[label]={"status":"unobservable","reason":"fewer_than_two_rays","n_views":len(obs)}
            continue
        lhs=np.zeros((3,3));rhs=np.zeros(3)
        for ob in obs:
            o,d=camera_ray(ob.camera,ob.pixel_uv)
            A=np.eye(3)-np.outer(d,d)
            lhs+=ob.confidence*A
            rhs+=ob.confidence*A@o
        condition=float(np.linalg.cond(lhs))
        if not np.isfinite(condition) or condition>max_condition:
            result[label]={"status":"unobservable","reason":"near_parallel_or_degenerate_rays",
                           "n_views":len(obs),"condition_number":condition}
            continue
        xyz=np.linalg.solve(lhs,rhs)
        residuals=[]
        for ob in obs:
            proj,dep=ob.camera.project(xyz.reshape(1,3))
            residuals.append(float(np.linalg.norm(proj[0]-ob.pixel_uv)) if dep[0]>0 else float('inf'))
        rmse=float(np.sqrt(np.average(np.square(residuals),weights=[o.confidence for o in obs])))
        result[label]={"status":"triangulated","xyz_world_units":xyz.round(8).tolist(),
                       "reprojection_rmse_pixels":rmse,"n_views":len(obs),
                       "condition_number":condition,
                       "scale_note":"World scale follows camera geometry; not intrinsically inferred from pixels."}
    return result
