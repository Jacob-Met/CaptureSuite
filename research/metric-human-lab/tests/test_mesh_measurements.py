import json
import subprocess
import sys
import numpy as np
import pytest
import trimesh

from metric_human.mesh_measurements import inspect_mesh_sections,measure_external_mesh


def test_direct_cylinder_perimeter_better_than_voxel_steps():
    r=.18
    mesh=trimesh.creation.cylinder(radius=r,height=1,sections=256)
    mesh.apply_translation((0,0,.5))
    report=inspect_mesh_sections(mesh,[.25,.5,.75])
    for section in report['sections']:
        c=section['contours']
        assert len(c)==1
        assert abs(c[0]['perimeter_m']-2*np.pi*r)*1000 < 0.2
        assert abs(c[0]['area_m2']-np.pi*r*r)<2e-5
    assert report['source_dimensions_independently_validated'] is False


def test_two_legs_return_two_independent_components():
    a=trimesh.creation.cylinder(radius=.06,height=.7,sections=64)
    b=a.copy()
    a.apply_translation((-.15,0,.45))
    b.apply_translation((.15,0,.45))
    mesh=trimesh.util.concatenate([a,b])
    report=inspect_mesh_sections(mesh,[.45])
    assert report['sections'][0]['separate_contour_count']==2
    assert report['sections'][0]['contours'][0]['centroid_xy_m'][0]==pytest.approx(-.15,abs=.002)
    assert report['sections'][0]['contours'][1]['centroid_xy_m'][0]==pytest.approx(.15,abs=.002)


def test_explicit_unit_conversion_and_cli(tmp_path):
    box=trimesh.creation.box(extents=(200,100,1000))
    box.apply_translation((0,0,500))
    path=tmp_path/'box.obj';box.export(path)
    report=measure_external_mesh(path,units='mm',fractions=[.5])
    assert report['sections'][0]['contours'][0]['perimeter_m']==pytest.approx(.6,abs=1e-6)
    assert report['source_declared_units']=='mm'
    target=tmp_path/'report.json'
    p=subprocess.run([sys.executable,'-m','metric_human','measure-mesh',
                  '--mesh',str(path),'--units','mm','--height-fractions','.5','--out',str(target)],
                 capture_output=True,text=True,check=True)
    assert json.loads(target.read_text())['source_file_sha256']==report['source_file_sha256']
    assert 'accuracy_validated' in p.stdout


def test_reject_unscaled_or_invalid_planes(tmp_path):
    m=trimesh.creation.box();m.apply_translation((0,0,.5))
    path=tmp_path/'box.stl';m.export(path)
    with pytest.raises(ValueError,match='physical'):
        measure_external_mesh(path,units='unknown',fractions=[.5])
    with pytest.raises(ValueError,match='either'):
        measure_external_mesh(path,units='m',fractions=[.5],heights_m=[.5])
    with pytest.raises(ValueError,match='strictly'):
        measure_external_mesh(path,units='m',fractions=[0])
    with pytest.raises(ValueError,match='strictly interior'):
        inspect_mesh_sections(m,[0])
