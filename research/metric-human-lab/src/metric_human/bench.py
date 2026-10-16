"""Synthetic geometry qualification; no claims about real-photograph accuracy."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import cv2
from .synthetic import Figure,orbit_cameras,ground_truth,render_silhouette
from .reconstruct import View,fuse_views,leave_one_out_sensitivity
from .measurements import geometric_report, slice_components
from .quality import surface_chamfer_mm
from .volume import Grid,intersection_over_union,bbox_error_mm


def default_grid(resolution=70):
    if resolution < 20: raise ValueError("resolution must be >=20")
    lower=(-.70,-.46,-.10)
    upper=(.70,.46,1.92)
    # isotropic-ish voxel pitch across axes
    pitch=2.02/resolution
    shape=tuple(int(np.ceil((b-a)/pitch)) for a,b in zip(lower,upper))
    return Grid(lower,upper,shape)


def build_scene(grid,figure=Figure(),max_views=8,width=256,height=384):
    truth=ground_truth(grid,figure)
    true_mesh=grid.occupancy_to_mesh(truth)
    cameras=orbit_cameras(max_views,width=width,height=height)
    views=[View(c,render_silhouette(true_mesh,c),label=f"view_{i:02d}")
           for i,c in enumerate(cameras)]
    return truth,true_mesh,views


def run_benchmark(out_dir,*,resolution=70,view_counts=(1,2,4,8),figure=Figure(),
                  image_width=256,image_height=384,do_loo=False):
    out=Path(out_dir)
    out.mkdir(parents=True,exist_ok=True)
    grid=default_grid(resolution)
    max_views=max(view_counts)
    truth,truth_mesh,views=build_scene(grid,figure,max_views,image_width,image_height)
    truth_mesh.export(out/'reference.glb')
    rows=[]
    for n in view_counts:
        if n<=0 or max_views % n:
            raise ValueError("View counts must evenly divide maximum for independent orbit sampling")
        chosen=views[::max_views//n]
        recon=fuse_views(chosen,grid,scale_source="synthetic_world_coordinates")
        mesh=recon.mesh()
        mesh.export(out/f'reconstruction_{n}views.glb')
        report=geometric_report(recon.occupancy,grid,cross_section_heights=(.75,1.10,1.32),
                                scale_source="synthetic_world_coordinates")
        errors=bbox_error_mm(recon.occupancy,truth,grid.spacing)
        section_errors={}
        for z_m in (1.10,1.32):
            expected_sections=slice_components(truth,grid,z_m)
            predicted_sections=slice_components(recon.occupancy,grid,z_m)
            key=f"largest_section_perimeter_error_{int(round(z_m*100))}cm_mm"
            section_errors[key] = (abs(expected_sections[0]['perimeter_m']-predicted_sections[0]['perimeter_m'])*1000
                                   if expected_sections and predicted_sections else None)
        row={"views":n,"synthetic_voxel_iou":intersection_over_union(recon.occupancy,truth),
             "synthetic_surface_chamfer_mm":surface_chamfer_mm(recon.occupancy,truth,grid),
             **section_errors,
             "false_positive_voxels":int(np.sum(recon.occupancy & ~truth)),
             "false_negative_voxels":int(np.sum(truth & ~recon.occupancy)),
             "mesh_vertices":int(len(mesh.vertices)),**errors}
        rows.append(row)
        with open(out/f'report_{n}views.json','w') as f:
            json.dump({"benchmark":row,"measurement":report,
                       "reconstruction":recon.metadata},f,indent=2)
    for i,v in enumerate(views):
        cv2.imwrite(str(out/f'mask_{i:02d}.png'),np.uint8(v.mask)*255)
    config={"grid":grid.to_dict(),"scale_source":"synthetic_world_coordinates",
            "views":[{"mask":f'mask_{i:02d}.png',"label":v.label,
                      "camera":v.camera.to_dict()} for i,v in enumerate(views)]}
    with open(out/'reproducible_input.json','w') as f:json.dump(config,f,indent=2)
    result={"benchmark_type":"procedural_human_figure_synthetic_only",
            "truth_description":"Mesh/voxel shape created from analytic ellipsoids and capsules, not a real person",
            "figure_parameters":figure.__dict__,"grid":grid.to_dict(),
            "image_size":[image_width,image_height],"rows":rows,
            "scale_note":"Synthetic coordinate units were defined as meters; this does not demonstrate image-only metric scale recovery.",
            "camera_note":"Camera geometry was provided from renderer; does not demonstrate automatic real-photo camera calibration.",
            "real_human_accuracy_claim":False,
            "follow_up":"Test external real scans/images under compatible licenses, then evaluate geometry, circumference and scale independently."}
    if do_loo:
        result['loo_view_sensitivity']=leave_one_out_sensitivity(views,grid)
    with open(out/'benchmark.json','w') as f:json.dump(result,f,indent=2)
    return result
