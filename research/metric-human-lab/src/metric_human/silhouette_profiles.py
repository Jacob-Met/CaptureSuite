"""Translation-invariant silhouette profile evidence, not an anatomical scan.

This descriptor preserves projected body height and row spans in pixels but is
invariant to global integer image translations when the full silhouette stays
inside the frame. It cannot measure occluded anatomy, recover camera poses or
uniquely determine an individual's 3D body shape.
"""
from __future__ import annotations
import numpy as np


def silhouette_profile(mask, *, rows:int=24):
    fg=np.asarray(mask,bool)
    if fg.ndim!=2 or not 4<=rows<=128:
        raise ValueError('Need 2D mask and 4..128 profile rows')
    ys,xs=np.nonzero(fg)
    if len(xs)<20:
        raise ValueError('Too few visible foreground pixels for silhouette profile')
    ymin,ymax=int(ys.min()),int(ys.max())
    xmin,xmax=int(xs.min()),int(xs.max())
    height=ymax-ymin+1
    width=xmax-xmin+1
    # Interpolate row span/occupancy at normalized silhouette heights. Using
    # coordinates relative to the bbox removes the nuisance of image centering.
    positions=np.linspace(0,1,rows)
    row_pixels=np.rint(ymin+positions*(height-1)).astype(int)
    extents=[];counts=[]
    for y in row_pixels:
        active=np.flatnonzero(fg[y])
        if len(active):
            extents.append(active[-1]-active[0]+1)
            counts.append(len(active))
        else:
            extents.append(0)
            counts.append(0)
    return np.array([height,width]+extents+counts,dtype=np.float64)


def silhouette_profile_loss(predicted,observed,*,rows:int=24):
    a=silhouette_profile(predicted,rows=rows)
    b=silhouette_profile(observed,rows=rows)
    H,W=np.asarray(predicted).shape
    # Numerator retains image pixel scale (shape is not normalized by its own
    # proportions), denominator is a stable dimension-specific noise scale.
    normalizer=np.array([.2*H,.2*W]+[.2*W]*rows*2)
    normalizer=np.maximum(normalizer,8.)
    return float(np.mean(((a-b)/normalizer)**2))
