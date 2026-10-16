"""Direct surface-based geometric measurements of an already scaled 3D mesh.

Compared to voxel-slice perimeters, triangle-plane intersections avoid voxel
stair-stepping. This does *not* establish correctness of the source geometry,
which body part a section intersects, or tape-measure equivalence.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
import trimesh


def _cross_section_loops(mesh:trimesh.Trimesh, z_m:float):
    if not np.isfinite(z_m):
        raise ValueError('Non-finite slice height')
    section=mesh.section(plane_origin=(0.,0.,float(z_m)),plane_normal=(0.,0.,1.))
    if section is None:
        return []
    result=[]
    for i,line in enumerate(section.discrete):
        xyz=np.asarray(line,float)
        if len(xyz)<3:
            continue
        # trimesh gives a repeated terminal vertex for closed contours.
        closed=bool(np.linalg.norm(xyz[0]-xyz[-1]) < 1e-6)
        if not closed:
            continue  # not a meaningful girth estimate
        xy=xyz[:-1,:2]
        if len(xy)<3:
            continue
        length=float(np.sum(np.linalg.norm(np.diff(xyz,axis=0),axis=1)))
        cross=xy[:,0]*np.roll(xy[:,1],-1)-np.roll(xy[:,0],-1)*xy[:,1]
        signed_area=.5*float(cross.sum())
        if abs(signed_area)<1e-12:
            continue
        xc=float(np.sum((xy[:,0]+np.roll(xy[:,0],-1))*cross)/(6*signed_area))
        yc=float(np.sum((xy[:,1]+np.roll(xy[:,1],-1))*cross)/(6*signed_area))
        result.append({'contour_index':i,'perimeter_m':round(length,8),
                       'area_m2':round(abs(signed_area),8),
                       'centroid_xy_m':[round(xc,7),round(yc,7)],
                       'segment_count':int(len(xyz)-1)})
    return sorted(result,key=lambda a:-a['area_m2'])


def inspect_mesh_sections(mesh:trimesh.Trimesh, heights_m:list[float],*,units_source:str='known_metric',
                          source: str='operator_supplied') -> dict:
    """Return independent horizontal contours, not named anatomical girths."""
    if not isinstance(mesh,trimesh.Trimesh) or len(mesh.vertices)<4 or len(mesh.faces)<4:
        raise ValueError('Require nonempty triangle mesh')
    if not np.isfinite(mesh.vertices).all() or not np.isfinite(mesh.faces).all():
        raise ValueError('Mesh has non-finite elements')
    if not heights_m or not all(np.isfinite(h) for h in heights_m):
        raise ValueError('At least one finite plane height required')
    if len(heights_m)>256:
        raise ValueError('Too many requested sections')
    b=np.asarray(mesh.bounds,float)
    sections=[]
    for h in heights_m:
        if h<=b[0,2] or h>=b[1,2]:
            raise ValueError(f'Section at {h}m is outside strictly interior mesh height')
        contours=_cross_section_loops(mesh,float(h))
        sections.append({'height_m':float(h),'contours':contours,
                         'separate_contour_count':len(contours)})
    return {'method':'direct_triangle_plane_mesh_intersection',
            'input_source':source, 'units_source':units_source,
            'watertight_mesh':bool(mesh.is_watertight),
            'triangle_count':int(len(mesh.faces)),
            'bounds_m':b.round(7).tolist(),
            'sections':sections,
            'is_observed_anatomical_circumference':False,
            'source_dimensions_independently_validated':False,
            'limitations':[
                'Measurements describe mesh geometry only; inaccurate reconstruction yields inaccurate dimensions.',
                'Sections are global horizontal Z planes and are not automatically anatomical cross-sections.',
                'Different limbs may appear as separate contours at the same height.',
                'Occluded body regions and clothing distort actual anatomical circumferences.',
                'Open or degenerate intersection contours are not reported as perimeters.',
            ]}


def measure_external_mesh(mesh_path, *, units:str,heights_m:list[float]|None=None,
                          fractions:list[float]|None=None):
    """Open a source mesh with explicit m/mm units and measure chosen planes."""
    if units not in ('m','mm'):
        raise ValueError('Explicit physical source units must be m or mm')
    if (heights_m is None)==(fractions is None):
        raise ValueError('Supply either absolute heights or normalized height fractions')
    path=Path(mesh_path)
    mesh=trimesh.load(path,force='mesh')
    if not isinstance(mesh,trimesh.Trimesh):
        raise ValueError('Source is not a triangle mesh')
    mesh=mesh.copy()
    if units=='mm': mesh.apply_scale(.001)
    low,high=float(mesh.bounds[0,2]),float(mesh.bounds[1,2]);size=high-low
    if size < .001 or not np.isfinite(size):
        raise ValueError('Unusable mesh Z extent')
    if fractions is not None:
        if not all(np.isfinite(f) and 0<f<1 for f in fractions):
            raise ValueError('Fractions must be strictly inside 0..1')
        heights_m=[low+float(f)*size for f in fractions]
    report=inspect_mesh_sections(mesh,heights_m,units_source=f'operator_declared_{units}',source=str(path))
    report['source_file_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    report['source_declared_units']=units
    return report


def save_section_report(path,report):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2),encoding='utf8')
    return path
