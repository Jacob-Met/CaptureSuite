"""Low-fidelity bridge from a reconstructed volume to a motion rig.

This is intentionally a *size-adapted generic skeleton*, not an anatomical
joint predictor and not deformable body motion. It permits plumbing tests from
photo geometry to gear testing while reporting why results are not fit-safe.
"""
from __future__ import annotations
from dataclasses import replace
import numpy as np
from .volume import Grid
from .motion import sample_rig,Rig


def approximate_rig_from_volume(occupancy: np.ndarray, grid: Grid) -> tuple[Rig, dict]:
    """Scale a generic adult-like skeleton by observed 3D extents.

    The voxel hull width includes outstretched arms, and the extent is NOT a
    measured bone length. Joint locations are only proportional assumptions.
    """
    occ = np.asarray(occupancy,dtype=bool)
    if occ.shape != grid.shape:
        raise ValueError('Body occupancy and grid shapes disagree')
    where=np.argwhere(occ)
    if len(where)<200:
        raise ValueError('Too few occupied voxels to size even a provisional rig')
    lower=np.asarray(grid.lower)+(where.min(axis=0)+.5)*grid.spacing
    upper=np.asarray(grid.lower)+(where.max(axis=0)+.5)*grid.spacing
    extent=upper-lower+grid.spacing
    if not np.all(np.isfinite(extent)) or np.min(extent)<.08 or extent[2]<.5:
        raise ValueError('Reconstruction extents are not human-shaped enough for proportional rig')
    # Nominal spans from the standalone procedural A-pose test skeleton. These
    # are NOT validated anthropometric regression estimates.
    scales=extent/np.array([1.05,.43,1.76])
    base=sample_rig()
    mid=(lower+upper)/2
    scaled=[]
    for joint in base.joints:
        if joint.parent is None:
            # Pelvis is defined at 0.95m in nominal frame.
            offset=(float(mid[0]),float(mid[1]),float(lower[2]+(.95/1.76)*extent[2]))
        else:
            offset=tuple(float(a*b) for a,b in zip(joint.rest_offset_m,scales))
        radius=float(joint.body_radius_m*np.sqrt(scales[0]*scales[1]))
        scaled.append(replace(joint,rest_offset_m=offset,body_radius_m=radius))
    report={
        'method':'generic_proportional_rig_scaled_to_reconstructed_occupied_bbox',
        'body_bbox_lower_m_if_scaled':lower.tolist(),
        'body_bbox_upper_m_if_scaled':upper.tolist(),
        'extent_xyz_m_if_scaled':extent.tolist(),
        'nominal_to_reconstruction_scales':scales.tolist(),
        'anatomical_joint_positions_validated':False,
        'body_shape_or_surface_fit_validated':False,
        'limitations':[
            'All joints inferred from fixed generic adult proportions; not independently observed anatomical points.',
            'A-pose arm span and silhouette visual-hull overfill can distort width/depth scaling.',
            'Root uses estimated feet-to-pelvis proportion; rig geometry does not skin/deform the reconstructed mesh.',
            'Gear collision relies on sampled proxy capsules, not the wearer-specific moving surface.',
            'Uncalibrated photo volumes have unverified physical units; size estimates are provisional.',
        ],
    }
    return Rig(tuple(scaled)), report
