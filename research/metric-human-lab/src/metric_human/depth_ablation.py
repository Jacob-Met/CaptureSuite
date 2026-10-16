"""Known-camera synthetic benchmark isolating value of calibrated depth.

Rendered depths here are *oracle* evidence from the same source mesh. This
benchmarks the geometric solver under ideal metric-depth conditions, not the
quality of a learned monocular depth estimator or natural-photograph pipeline.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np

from .bench import default_grid, build_scene
from .reconstruct import View, fuse_views
from .render import render_metric_depth
from .volume import intersection_over_union
from .quality import surface_chamfer_mm
from .measurements import slice_components


def run_depth_ablation(out_dir, *, resolution=60, view_counts=(1, 2, 4, 8),
                       image_width=192, image_height=288, tolerance_voxels=.8):
    """Compare silhouette-only and *known-metric-depth* carving to true volume."""
    if not view_counts or any(n <= 0 or max(view_counts) % n for n in view_counts):
        raise ValueError('View counts must be positive divisors of maximum count')
    if not 0 <= tolerance_voxels <= 5 or not np.isfinite(tolerance_voxels):
        raise ValueError('Invalid depth tolerance in voxel units')
    grid = default_grid(resolution)
    truth, mesh, views = build_scene(grid, max_views=max(view_counts),
                                    width=image_width, height=image_height)
    tolerance = float(max(grid.spacing) * tolerance_voxels)
    depth_views = []
    for v in views:
        depth = render_metric_depth(mesh, v.camera)
        depth_views.append(View(camera=v.camera, mask=v.mask, label=v.label,
                                depth_m=depth, depth_tolerance_m=tolerance))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for n in view_counts:
        indices = np.arange(0, max(view_counts), max(view_counts) // n)
        row = {'views': int(n), 'depth_tolerance_m': tolerance}
        for mode, evidence in [('silhouette', views), ('oracle_metric_depth', depth_views)]:
            subset = [evidence[int(i)] for i in indices]
            recon = fuse_views(subset, grid, scale_source='synthetic_world_coordinates')
            row[mode] = {
                'voxel_iou': intersection_over_union(recon.occupancy, truth),
                'surface_chamfer_mm': surface_chamfer_mm(recon.occupancy, truth, grid),
                'false_positive_voxels': int(np.sum(recon.occupancy & ~truth)),
                'false_negative_voxels': int(np.sum(truth & ~recon.occupancy)),
            }
            for height in [1.10, 1.32]:
                expected=slice_components(truth,grid,height)
                predicted=slice_components(recon.occupancy,grid,height)
                row[mode][f'section_{height:.2f}m_perimeter_abs_error_mm'] = (
                    abs(expected[0]['perimeter_m'] - predicted[0]['perimeter_m']) * 1000
                    if expected and predicted else None)
        rows.append(row)
    result = {
        'benchmark_type': 'procedural_known_camera_oracle_metric_depth_ablation',
        'rows': rows,
        'is_reconstruction_from_real_rgb': False,
        'human_measurement_accuracy_validated': False,
        'known_camera_and_metric_scale': True,
        'depth_origin': 'CPU triangle rasterization of the known source mesh (oracle)',
        'warning': 'Do not interpret oracle-depth improvements as learned monocular depth accuracy.',
        'grid': grid.to_dict(), 'image_size':[image_width,image_height],
    }
    (out/'depth_ablation.json').write_text(json.dumps(result, indent=2),encoding='utf8')
    return result
