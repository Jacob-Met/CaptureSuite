"""CPU depth rasterization for deterministic, *known-camera* geometry experiments.

This module renders depth from an existing mesh, it does not estimate depth
from photographs. It permits geometric ablations without neural-model noise.
"""
from __future__ import annotations
import numpy as np


def render_metric_depth(mesh, camera, *, near_m=1e-3):
    """Return camera-forward metric Z of the closest triangle per pixel.

    Pixels without visible surfaces are NaN. Perspective depth is computed by
    interpolating reciprocal camera Z; orthographic depth is interpolated
    linearly. Fully/partly behind-near-plane triangles are skipped rather than
    being incorrectly rasterized without near-plane clipping.
    """
    if not np.isfinite(near_m) or near_m <= 0:
        raise ValueError('near_m must be positive')
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or not np.isfinite(vertices).all():
        raise ValueError('Mesh vertices must be finite Nx3')
    uv, z = camera.project(vertices)
    result = np.full((camera.height, camera.width), np.inf, dtype=np.float64)
    for tri in faces:
        if not np.all(z[tri] > near_m):
            continue
        triangle = uv[tri]
        if not np.isfinite(triangle).all():
            continue
        x0 = max(0, int(np.floor(np.min(triangle[:, 0]))))
        x1 = min(camera.width - 1, int(np.ceil(np.max(triangle[:, 0]))))
        y0 = max(0, int(np.floor(np.min(triangle[:, 1]))))
        y1 = min(camera.height - 1, int(np.ceil(np.max(triangle[:, 1]))))
        if x0 > x1 or y0 > y1:
            continue
        a, b, c = triangle
        area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(area) < 1e-12:
            continue
        xx, yy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1), indexing='xy')
        w1 = ((xx - a[0]) * (c[1] - a[1]) - (yy - a[1]) * (c[0] - a[0])) / area
        w2 = ((b[0] - a[0]) * (yy - a[1]) - (b[1] - a[1]) * (xx - a[0])) / area
        w0 = 1 - w1 - w2
        inside = (w0 >= -1e-7) & (w1 >= -1e-7) & (w2 >= -1e-7)
        if not inside.any():
            continue
        tz = z[tri]
        if camera.model == 'perspective':
            dep = 1 / (w0 / tz[0] + w1 / tz[1] + w2 / tz[2])
        else:
            dep = w0 * tz[0] + w1 * tz[1] + w2 * tz[2]
        sub = result[y0:y1 + 1, x0:x1 + 1]
        np.minimum(sub, np.where(inside, dep, np.inf), out=sub)
    result[~np.isfinite(result)] = np.nan
    return result.astype(np.float32)
