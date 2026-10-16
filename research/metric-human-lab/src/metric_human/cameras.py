"""Explicit pinhole and orthographic camera geometry.

World axes: x=lateral, y=anterior-posterior, z=vertical.
Camera axes: +x=image right, +y=image down, +z=forward.
R maps world vectors to camera vectors; t=-R @ camera_center.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Camera:
    rotation: np.ndarray  # world -> camera, 3x3
    translation: np.ndarray  # world -> camera, length 3
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    model: str = "perspective"

    def __post_init__(self):
        if self.model not in ("perspective", "orthographic"):
            raise ValueError("Camera model must be perspective or orthographic")
        if self.width < 2 or self.height < 2 or self.fx <= 0 or self.fy <= 0:
            raise ValueError("Invalid image dimensions or focal scale")
        r = np.asarray(self.rotation, dtype=float)
        t = np.asarray(self.translation, dtype=float)
        if r.shape != (3, 3) or t.shape != (3,):
            raise ValueError("Camera rotation must be 3x3 and translation length 3")
        if not np.allclose(r @ r.T, np.eye(3), atol=1e-5) or np.linalg.det(r) < 0.999:
            raise ValueError("Camera rotation must be a proper orthonormal rotation")

    @classmethod
    def look_at(cls, eye, target, *, width=256, height=384, focal=340., model="orthographic", up=(0., 0., 1.)):
        eye = np.asarray(eye, float)
        target = np.asarray(target, float)
        forward = target - eye
        forward /= np.linalg.norm(forward)
        # Camera down axis is the opposite of the world-up component.
        right = np.cross(forward, np.asarray(up, float))
        norm = np.linalg.norm(right)
        if norm < 1e-8:
            raise ValueError("Camera axis parallel to up axis")
        right /= norm
        down = np.cross(forward, right)
        R = np.stack((right, down, forward))
        return cls(R, -R @ eye, width, height, focal, focal, (width-1)/2., (height-1)/2., model)

    def project(self, points):
        p = np.asarray(points, float)
        if p.ndim != 2 or p.shape[1] != 3:
            raise ValueError("points must be Nx3")
        c = p @ np.asarray(self.rotation).T + np.asarray(self.translation)
        z = c[:, 2]
        if self.model == "perspective":
            divisor = np.where(z > 1e-8, z, np.nan)
            u = self.fx * (c[:, 0] / divisor) + self.cx
            v = self.fy * (c[:, 1] / divisor) + self.cy
        else:
            u = self.fx * c[:, 0] + self.cx
            v = self.fy * c[:, 1] + self.cy
        uv = np.column_stack([u, v])
        return uv, z

    def to_dict(self):
        return dict(rotation=np.asarray(self.rotation).tolist(), translation=np.asarray(self.translation).tolist(),
                    width=self.width, height=self.height, fx=self.fx, fy=self.fy,
                    cx=self.cx, cy=self.cy, model=self.model)

    @classmethod
    def from_dict(cls, d):
        return cls(rotation=np.asarray(d["rotation"], dtype=float),
                   translation=np.asarray(d["translation"], dtype=float),
                   width=int(d["width"]), height=int(d["height"]),
                   fx=float(d["fx"]), fy=float(d["fy"]), cx=float(d["cx"]),
                   cy=float(d["cy"]), model=d.get("model", "perspective"))
