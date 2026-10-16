"""Small explicit, non-neural anatomical-shape prior fitter.

This is an observable ablation target: compare silhouette-only volume against
shape-prior constrained reconstructions. Its template is procedural, not learned
from human scans. Consequently output is a *proxy*, not an accurate real body.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.optimize import minimize
from .synthetic import render_silhouette
from .quality import mask_iou


@dataclass
class TemplateFit:
    width_factor:float
    depth_factor:float
    height_factor:float
    training_objective:float
    observed_silhouette_ious:list[float]
    status:str="synthetic_template_proxy"


def fit_scaled_template(template_mesh,views,*,start=(1.,1.,1.),prior_strength=.03,maxiter=90):
    """Optimize width/depth/height with a geometrically constrained template.

    Fixed mesh topology; fitted to projected silhouettes using Powell search.
    Cannot recover depth from a single frontal orthographic image without the
    prior, by design. Bounded scale range is intentionally transparent.
    """
    vertices=np.asarray(template_mesh.vertices)
    face_copy=np.asarray(template_mesh.faces)
    class FastMesh:
        def __init__(self,v):self.vertices=v;self.faces=face_copy
    def scores(x):
        v=vertices*np.asarray(x)
        mesh=FastMesh(v)
        return [mask_iou(render_silhouette(mesh,ob.camera),ob.mask) for ob in views]
    def objective(x):
        ious=scores(x)
        return float(np.mean([(1.-v)**2 for v in ious])+prior_strength*np.sum((np.asarray(x)-1.)**2))
    bounds=((.6,1.6),(.6,1.6),(.75,1.35))
    opt=minimize(objective,np.asarray(start,float),method='Powell',bounds=bounds,
                 options={'maxiter':maxiter,'xtol':1e-3,'ftol':1e-5})
    return TemplateFit(*[float(z) for z in opt.x],float(opt.fun),scores(opt.x))
