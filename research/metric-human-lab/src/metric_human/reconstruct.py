"""Geometric evidence fusion: mask-space hard/robust visual-hull carving.

Silhouettes, calibrated camera projections, and (optional) metric depth evidence
contribute directly to volumetric constraints. Relative depth predictions are
explicitly not accepted as meters. Learned predictors are adapters, not geometry.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import cv2
from scipy.ndimage import binary_dilation, binary_closing
from .volume import Grid
from .cameras import Camera


@dataclass(frozen=True)
class View:
    camera: Camera
    mask: np.ndarray  # foreground silhouette boolean, HxW
    label: str = ""
    weight: float = 1.0
    depth_m: np.ndarray | None = None  # known metric camera-z front surface
    depth_tolerance_m: float = .02
    segmentation_margin_px: int = 0

    def __post_init__(self):
        if np.asarray(self.mask).shape != (self.camera.height,self.camera.width):
            raise ValueError(f"Bad mask shape for {self.label}")
        if self.depth_m is not None and np.asarray(self.depth_m).shape != np.asarray(self.mask).shape:
            raise ValueError("Depth and mask image dimensions must match")
        if not np.isfinite(self.weight) or self.weight <= 0 or self.segmentation_margin_px < 0 or self.depth_tolerance_m < 0 or not np.isfinite(self.depth_tolerance_m):
            raise ValueError("Invalid evidence weight/margin/tolerance")


@dataclass
class Reconstruction:
    grid: Grid
    occupancy: np.ndarray
    support_fraction: np.ndarray
    metadata: dict

    def mesh(self):
        return self.grid.occupancy_to_mesh(self.occupancy)


def fuse_views(views:list[View],grid:Grid,*,min_fraction:float=1.,closing_iterations:int=0,
               chunk_size=240_000,scale_source="calibrated_camera_geometry") -> Reconstruction:
    """Carve voxel occupancy using cameras in the grid's coordinate units.

    min_fraction=1 uses intersection of view-consistent cones.
    Relaxing min_fraction is tolerant of uncertain segmentations but can
    hallucinate occupancy. It is never an estimated confidence interval.
    Depth may only be a metric camera-z surface. Anything else is rejected.
    """
    if not views: raise ValueError("No evidence views")
    if not 0 < min_fraction <= 1: raise ValueError("min_fraction must be in (0,1]")
    total_weight = sum(v.weight for v in views)
    points=grid.centers
    fractions=np.zeros(len(points), dtype=np.float32)
    for view in views:
        mask=np.asarray(view.mask,dtype=bool)
        if view.segmentation_margin_px:
            mask=binary_dilation(mask,iterations=view.segmentation_margin_px)
        h,w=mask.shape
        depth = np.asarray(view.depth_m) if view.depth_m is not None else None
        for start in range(0,len(points),chunk_size):
            end=min(start+chunk_size,len(points))
            uv, camera_z = view.camera.project(points[start:end])
            finite=np.isfinite(uv).all(axis=1)
            good=finite&(camera_z>0)
            # Empty projection maps to out-of-silhouette.
            ix=np.zeros(end-start,dtype=int)
            iy=np.zeros(end-start,dtype=int)
            ix[good]=np.rint(uv[good,0]).astype(int)
            iy[good]=np.rint(uv[good,1]).astype(int)
            inside=good&(ix>=0)&(ix<w)&(iy>=0)&(iy<h)
            agreed=np.zeros(end-start,dtype=bool)
            agreed[inside]=mask[iy[inside],ix[inside]]
            if depth is not None:
                pixel_depth=np.full(end-start,np.nan)
                pixel_depth[inside]=depth[iy[inside],ix[inside]]
                valid_depth=np.isfinite(pixel_depth)&(pixel_depth>0)
                # Surface cannot physically be behind candidate occupancy.
                agreed &= (~valid_depth)|(camera_z>=pixel_depth-view.depth_tolerance_m)
            fractions[start:end]+=view.weight*agreed
    fractions=(fractions/total_weight).reshape(grid.shape)
    occupancy=fractions>=min_fraction-1e-6
    if closing_iterations:
        occupancy=binary_closing(occupancy,iterations=closing_iterations)
    metadata={"method":"weighted_multiview_silhouette_carving", "views":len(views),
              "min_view_support_fraction":min_fraction,"scale_source":scale_source,
              "grid_spacing_m":grid.spacing.tolist(),"occupied_voxels":int(occupancy.sum()),
              "notes":["This is a visual hull, not an anatomically complete body estimate.",
                       "View agreement is not a calibrated probability of geometric correctness.",
                       "Depth constraints require metric camera-Z depth; relative AI depth is not silently interpreted as meters."]}
    return Reconstruction(grid,occupancy,fractions,metadata)


def leave_one_out_sensitivity(views,grid,**kwargs):
    """Voxel fraction whose classification changes when each view is removed.

    A sensitivity diagnostic, not an uncertainty bound or posterior probability.
    """
    if len(views)<2: return {"available":False,"reason":"Requires >=2 views"}
    full=fuse_views(views,grid,**kwargs).occupancy
    scores={}
    for i,v in enumerate(views):
        reduced=fuse_views(views[:i]+views[i+1:],grid,**kwargs).occupancy
        scores[v.label or str(i)] = float(np.mean(full!=reduced))
    return {"available":True,"voxel_classification_change_fraction":scores}


def mask_from_image(image_path, *, rectangle=None, iterations=6):
    """Optional simple GrabCut foreground proposal. Not a body segmenter.

    Expect a photo with the whole person inside the rectangle. May fail on
    complex backgrounds or loose clothing. Save/correct masks before use.
    """
    bgr=cv2.imread(str(image_path))
    if bgr is None: raise ValueError(f"Cannot read {image_path}")
    h,w=bgr.shape[:2]
    if rectangle is None:
        rectangle=(int(w*.08),int(h*.025),int(w*.84),int(h*.95))
    x,y,rw,rh=rectangle
    if x<0 or y<0 or rw<1 or rh<1 or x+rw>w or y+rh>h:
        raise ValueError("Invalid foreground rectangle")
    mask=np.zeros((h,w),np.uint8)
    cv2.grabCut(bgr,mask,tuple(int(v) for v in rectangle),np.zeros((1,65),np.float64),
                np.zeros((1,65),np.float64),iterations,cv2.GC_INIT_WITH_RECT)
    return np.isin(mask,[cv2.GC_FGD,cv2.GC_PR_FGD])
