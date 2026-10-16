"""Independently generated procedural human geometry and RGB-like masks.

No real-person assets and no dataset permissions are necessary for these tests.
The figure is an SDF proxy for engineering verification, NOT a biological ground truth.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import cv2
from scipy.ndimage import binary_fill_holes
from .cameras import Camera
from .volume import Grid


@dataclass(frozen=True)
class Figure:
    height: float = 1.75
    width_scale: float = 1.0
    depth_scale: float = 1.0
    arm_scale: float = 1.0
    leg_scale: float = 1.0


def _ellipsoid(p, center, radii):
    center, radii = np.asarray(center), np.asarray(radii)
    # Distance-like estimate; exact distance unnecessary for our zero level set.
    return (np.linalg.norm((p-center)/radii, axis=1)-1.0) * float(min(radii))


def _capsule(p, a, b, r0, r1=None):
    a,b = np.asarray(a),np.asarray(b)
    d = b-a
    t = np.clip(np.sum((p-a)*d,axis=1) / np.dot(d,d), 0.0, 1.0)
    q = a+t[:,None]*d
    r = r0+(r1-r0)*t if r1 is not None else r0
    return np.linalg.norm(p-q,axis=1)-r


def figure_sdf(points, figure=Figure()):
    p = np.asarray(points, float).copy()
    p[:, 0] /= figure.width_scale
    p[:, 1] /= figure.depth_scale
    p[:, 2] /= figure.height / 1.75
    d = np.full(len(p), np.inf)
    parts = [
        _ellipsoid(p, [0., 0., 1.27], [.229,.127,.315]),  # chest and abdomen
        _ellipsoid(p, [0., 0., .995], [.195,.127,.164]), # pelvis
        _capsule(p, [0,0,1.48], [0,0,1.56], .069, .060),
        _ellipsoid(p,[0.,-.010,1.649],[.109,.103,.125]),
    ]
    for side in (-1,1):
        # Shoulders + down/out A-pose arms, elbow, wrists
        x=side
        parts.extend([
            _capsule(p,[x*.210,0.,1.43],[x*.346,-.005,1.257],.090*figure.arm_scale,.075*figure.arm_scale),
            _capsule(p,[x*.346,-.005,1.257],[x*.463,-.020,1.056],.075*figure.arm_scale,.053*figure.arm_scale),
            _capsule(p,[x*.463,-.020,1.056],[x*.489,-.030,.951],.054*figure.arm_scale,.049*figure.arm_scale),
            _ellipsoid(p,[x*.490,-.030,.907],[.055*figure.arm_scale,.027,.070]),
            _capsule(p,[x*.110,0.,.922],[x*.128,-.005,.557],.101*figure.leg_scale,.078*figure.leg_scale),
            _capsule(p,[x*.128,-.005,.557],[x*.145,-.012,.128],.077*figure.leg_scale,.047*figure.leg_scale),
            _ellipsoid(p,[x*.145,-.073,.081],[.074,.151,.057]),
        ])
    for part in parts:
        d = np.minimum(d,part)
    # Convert distance-like field approximately back into metric units.
    return d * min(figure.width_scale,figure.depth_scale,figure.height/1.75)


def ground_truth(grid, figure=Figure(), chunk_size=500_000):
    p = grid.centers
    out = np.zeros(len(p), bool)
    for i in range(0,len(p),chunk_size):
        out[i:i+chunk_size] = figure_sdf(p[i:i+chunk_size],figure)<=0
    return out.reshape(grid.shape)


def render_silhouette(mesh,camera):
    """CPU triangle silhouette renderer. No shading/learned labels involved."""
    uv,z = camera.project(mesh.vertices)
    face_ids = np.asarray(mesh.faces, dtype=int)
    mask = np.zeros((camera.height,camera.width), dtype=np.uint8)
    valid = np.all(z[face_ids]>1e-6,axis=1)
    # Clip giant off-image triangles in integer coordinates to protect OpenCV.
    coords = np.rint(np.clip(uv,-1_000_000,1_000_000)).astype(np.int32)
    for face in face_ids[valid]:
        cv2.fillConvexPoly(mask, coords[face], 255, lineType=cv2.LINE_8)
    return binary_fill_holes(mask>0)


def orbit_cameras(n, *, width=256,height=384, focal=166., z_target=.96, model="orthographic"):
    if n < 1: raise ValueError("At least one view required")
    result=[]
    for a in np.linspace(0,2*np.pi,n,endpoint=False):
        eye=(3*np.sin(a),-3*np.cos(a),z_target)
        result.append(Camera.look_at(eye,[0.,0.,z_target],width=width,height=height,
                                     focal=focal,model=model))
    return result
