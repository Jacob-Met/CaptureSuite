"""Direct measurements from a known-scale occupied voxel geometry.

A closed-contour perimeter around silhouette slices is a geometric estimate,
not automatically a tape-measured human circumference. Naming requires anatomy.
"""
from __future__ import annotations
import numpy as np
import cv2
from .volume import Grid


def slice_components(occupancy,grid:Grid,z_m):
    """Connected XY contours at specified Z, sorted by cross-sectional area."""
    iz = int(np.floor((z_m - grid.lower[2])/grid.spacing[2]))
    if iz < 0 or iz >= grid.shape[2]:
        raise ValueError("Requested section outside grid")
    xy=np.asarray(occupancy,dtype=bool)[:,:,iz].astype(np.uint8)
    outlines,_=cv2.findContours(xy,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    result=[]
    dx,dy=grid.spacing[:2]
    for poly in outlines:
        if len(poly)<3:continue
        path=poly.reshape(-1,2).astype(float)
        path[:,0] *= dy # OpenCV horizontal coordinate is grid second axis
        path[:,1] *= dx
        dif=np.roll(path,-1,axis=0)-path
        circumference=float(np.linalg.norm(dif,axis=1).sum())
        area_px=float(cv2.contourArea(poly))
        area_m2=area_px*dx*dy
        moments=cv2.moments(poly)
        if moments['m00']:
            centroid=(grid.lower[0]+(moments['m01']/moments['m00']+.5)*dx,
                      grid.lower[1]+(moments['m10']/moments['m00']+.5)*dy)
        else: centroid=(float('nan'),float('nan'))
        result.append({"perimeter_m":round(circumference,6),"area_m2":round(area_m2,7),
                       "centroid_xy_m":[round(v,5) for v in centroid]})
    return sorted(result,key=lambda x:x['area_m2'],reverse=True)


def geometric_report(occupancy,grid:Grid,*,cross_section_heights=None,scale_source="unknown"):
    p=np.argwhere(occupancy)
    if not len(p): return {"status":"no_reconstruction","scale_source":scale_source}
    spacing=grid.spacing
    low=np.asarray(grid.lower)+p.min(axis=0)*spacing
    high=np.asarray(grid.lower)+(p.max(axis=0)+1)*spacing
    # A typo or unchecked free-text provenance must never silently certify metric scale.
    validated_sources={"synthetic_world_coordinates","source_mesh_explicit_units",
                       "calibrated_camera_geometry"}
    anchored_sources=validated_sources | {"user_height_anchor"}
    result={"status":"geometric_volume_only", "metric_scale_verified":scale_source in validated_sources,
            "metric_scale_anchored":scale_source in anchored_sources,
            "human_measurement_accuracy_validated":False,
            "scale_source":scale_source,"bounds_units": "meters_in_given_coordinate_frame",
            "occupied_volume_m3_if_scaled":float(len(p)*np.prod(spacing)),
            "axis_extents_m_if_scaled":dict(zip(("x_width","y_depth","z_height"),(high-low).round(6).tolist())),
            "voxel_resolution_m":spacing.round(7).tolist(),
            "limitations":["Voxel surface discretization affects measurements.",
                           "Silhouette-only hull can overestimate unobserved concavities.",
                           "Body-part identity and material/fitting ease are not inferred.",
                           "Dimensions are not verified human dimensions without real ground truth."]}
    if cross_section_heights is not None:
        result["horizontal_sections"]=[{"z_m":float(h),"components":slice_components(occupancy,grid,h)}
                                        for h in cross_section_heights]
    return result
