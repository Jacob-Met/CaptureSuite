"""User-supplied mesh benchmark. No scans/datasets are bundled or downloaded.

Converts an already-licensed and dimensioned source mesh to a voxel reference,
then renders calibrated synthetic RGB-like silhouettes to test reconstruction.
This tests geometry with *known* cameras, not pose inference from real photos.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import trimesh

from .cameras import Camera
from .volume import Grid, intersection_over_union, bbox_error_mm
from .measurements import slice_components
from .quality import surface_chamfer_mm
from .synthetic import render_silhouette
from .reconstruct import View, fuse_views


def scan_truth_voxels(mesh,grid,pitch):
    vox=mesh.voxelized(pitch).fill()
    locations=vox.points
    coords=np.rint((locations-np.asarray(grid.lower)-pitch*.5)/pitch).astype(int)
    keep=np.all((coords>=0)&(coords<np.array(grid.shape)),axis=1)
    coords=coords[keep]
    occupancy=np.zeros(grid.shape,bool)
    occupancy[coords[:,0],coords[:,1],coords[:,2]]=True
    return occupancy


def run_external_mesh_benchmark(mesh_path,out_dir,*,units='m',resolution=70,
                                views=(1,2,4,8),width=320,height=440):
    mesh_path=Path(mesh_path)
    if units not in ('m','mm'):
        raise ValueError('Specify physical mesh coordinates in meters or millimeters')
    if resolution<20 or resolution>250:
        raise ValueError('Unsupported benchmark resolution')
    scene=trimesh.load(mesh_path,force='mesh')
    if isinstance(scene,trimesh.Scene):
        scene=trimesh.util.concatenate(tuple(scene.geometry.values()))
    if not isinstance(scene,trimesh.Trimesh) or not len(scene.vertices) or not len(scene.faces):
        raise ValueError('Need a nonempty triangle mesh')
    mesh=scene.copy()
    mesh.apply_scale(.001 if units=='mm' else 1.)
    if not mesh.is_watertight:
        raise ValueError('Reference mesh must be watertight to establish volumetric ground truth')
    bounds=mesh.bounds
    height_m=float(bounds[1,2]-bounds[0,2])
    if height_m<.1 or height_m>3.:
        raise ValueError('Mesh height must be plausibly human-sized in declared units')
    # +Z vertical: explicitly require user to orient mesh before invocation.
    mid=(bounds[0]+bounds[1])*.5
    mesh.apply_translation((-mid[0],-mid[1],-bounds[0,2]))
    pitch=height_m/resolution
    margin=np.array([.09,.09,.09])
    low=mesh.bounds[0]-margin
    upper=mesh.bounds[1]+margin
    shape=np.ceil((upper-low)/pitch).astype(int)
    grid=Grid(tuple(float(v) for v in low),
              tuple(float(v) for v in low+shape*pitch),tuple(int(v) for v in shape))
    truth=scan_truth_voxels(mesh,grid,pitch)
    if not truth.any():
        raise ValueError('Reference voxelization failed')
    # Make the same explicit camera configuration available for exact replay.
    max_views=max(views)
    if max_views<1 or any(v<=0 or max_views%v for v in views):
        raise ValueError('Every view count must be a positive divisor of maximum')
    lateral=float(max(mesh.bounds[1,0]-mesh.bounds[0,0], mesh.bounds[1,1]-mesh.bounds[0,1]))
    focal=min(.82*height/height_m, .85*width/max(lateral,.2))
    eye_radius=max(3.,height_m*1.8)
    cam_list=[]
    for a in np.linspace(0,2*np.pi,max_views,endpoint=False):
        eye=(eye_radius*np.sin(a),-eye_radius*np.cos(a),height_m/2)
        cam_list.append(Camera.look_at(eye,[0,0,height_m/2],width=width,height=height,
                                       focal=focal,model='orthographic'))
    cameras=[View(camera,render_silhouette(mesh,camera),label=f'orbit_{i:02d}')
             for i,camera in enumerate(cam_list)]
    out=Path(out_dir)
    out.mkdir(parents=True,exist_ok=True)
    mesh.export(out/'reference_geometry.glb')
    rows=[]
    for n in views:
        subset=cameras[::max_views//n]
        recon=fuse_views(subset,grid,scale_source='source_mesh_explicit_units')
        occupied=recon.occupancy
        outmesh=recon.mesh()
        outmesh.export(out/f'reconstructed_{n}views.glb')
        sections={}
        for fraction in (.55,.75):
            z=height_m*fraction
            truth_s=slice_components(truth,grid,z)
            recon_s=slice_components(occupied,grid,z)
            sections[f'largest_section_{round(fraction*100)}pct_perimeter_error_mm']=(
                abs(truth_s[0]['perimeter_m']-recon_s[0]['perimeter_m'])*1000
                if truth_s and recon_s else None)
        rows.append({'views':n,'voxel_iou_against_voxelized_source':intersection_over_union(occupied,truth),
                     'surface_chamfer_mm_against_voxelized_source':surface_chamfer_mm(occupied,truth,grid),
                     **bbox_error_mm(occupied,truth,grid.spacing),**sections})
    for i,view in enumerate(cameras):
        cv2.imwrite(str(out/f'mask_{i:02d}.png'),(np.asarray(view.mask,dtype=np.uint8)*255))
    manifest={'grid':grid.to_dict(),'scale_source':'source_mesh_explicit_units',
              'views':[{'mask':f'mask_{i:02d}.png','label':v.label,
                        'camera':v.camera.to_dict()} for i,v in enumerate(cameras)]}
    (out/'reproducible_input.json').write_text(json.dumps(manifest,indent=2))
    result={'benchmark_type':'externally_provided_watertight_mesh_rendered_into_synthetic_views',
            'source_mesh_sha256':hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
            'source_path':str(mesh_path),'source_declared_units':units,
            'source_height_m_after_unit_conversion':height_m,
            'camera_geometry':'known_rendered_orthographic',
            'reference_triangulation':'source_mesh_converted_to_voxels_at_grid_resolution',
            'source_is_verified_scan':False,
            'source_license': 'Unspecified by program: operator is responsible for source rights',
            'real_camera_pose_estimation_demonstrated':False,
            'image_only_absolute_scale_estimation_demonstrated':False,
            'rows':rows}
    (out/'benchmark.json').write_text(json.dumps(result,indent=2))
    return result
