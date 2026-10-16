"""Voxel geometry, metric surface export, and occupancy metrics."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from skimage import measure
import trimesh


@dataclass(frozen=True)
class Grid:
    lower: tuple[float, float, float]
    upper: tuple[float, float, float]
    shape: tuple[int, int, int]

    def __post_init__(self):
        if len(self.lower) != 3 or len(self.upper) != 3 or len(self.shape) != 3:
            raise ValueError("Grid is 3D")
        if min(self.shape) < 4 or not all(b > a for a, b in zip(self.lower, self.upper)):
            raise ValueError("Invalid grid bounds/shape")

    @property
    def spacing(self):
        return (np.asarray(self.upper, dtype=float) - np.asarray(self.lower, dtype=float)) / np.asarray(self.shape, dtype=float)

    @property
    def centers(self):
        return np.indices(self.shape, dtype=float).reshape(3, -1).T * self.spacing + np.asarray(self.lower) + 0.5 * self.spacing

    def to_dict(self):
        return dict(lower=list(self.lower), upper=list(self.upper), shape=list(self.shape))

    @classmethod
    def from_dict(cls, d):
        return cls(tuple(d["lower"]), tuple(d["upper"]), tuple(d["shape"]))

    def occupancy_to_mesh(self, occupancy):
        v = np.asarray(occupancy, bool)
        if v.shape != self.shape:
            raise ValueError("Occupancy shape mismatch")
        if not v.any():
            raise ValueError("Cannot mesh empty volume")
        # Pad so surfaces remain closed even when occupied at voxel grid boundary.
        padded = np.pad(v.astype(np.uint8), 1)
        verts, faces, _, _ = measure.marching_cubes(padded, level=0.5, spacing=tuple(self.spacing))
        verts += np.asarray(self.lower) - 0.5 * self.spacing
        mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
        mesh.fix_normals()
        return mesh


def intersection_over_union(actual, expected):
    a, b = np.asarray(actual, bool), np.asarray(expected, bool)
    if a.shape != b.shape:
        raise ValueError("Grid mismatch")
    union = np.count_nonzero(a | b)
    return float(np.count_nonzero(a & b) / union) if union else 1.0


def bbox_error_mm(actual, expected, spacing):
    a, b = np.argwhere(actual), np.argwhere(expected)
    if not len(a) or not len(b):
        return None
    step = np.asarray(spacing)
    a_extent = (a.max(axis=0)-a.min(axis=0)+1) * step
    b_extent = (b.max(axis=0)-b.min(axis=0)+1) * step
    return dict(zip(("x_width_mm", "y_depth_mm", "z_height_mm"),
                    (np.abs(a_extent-b_extent) * 1000).tolist()))
