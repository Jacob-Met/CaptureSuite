from pathlib import Path

import numpy as np
import pytest

from metric_human.makehuman import (import_makehuman_prior, makehuman_to_world,
                                    read_index_preserving_obj, read_sparse_makehuman_target,
                                    save_imported_prior)
from metric_human.prior import Prior


def _make_files(tmp_path):
    # Rectangular volume with 1.8 m height in invented 0.1 m/native units.
    obj = tmp_path / 'base.obj'
    obj.write_text('''# Indexed triangles and quads
v -1 -9 -1
v 1 -9 -1
v 1 -9 1
v -1 -9 1
v -1 9 -1
v 1 9 -1
v 1 9 1
v -1 9 1
f 1 4 3 2
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
''')
    inc = tmp_path / 'width-incr.target'
    dec = tmp_path / 'width-decr.target'
    inc.write_text('# sparse MakeHuman target\n1 0.25 0 0\n2 0.25 0 0\n5 0.25 0 0\n6 0.25 0 0\n')
    dec.write_text('# negative is independent from positive target\n1 -0.15 0 0\n2 -0.15 0 0\n5 -0.15 0 0\n6 -0.15 0 0\n')
    return obj,inc,dec


def test_coordinate_conversion_handedness_and_native_units():
    arr = np.eye(3)
    out = makehuman_to_world(arr, .1)
    assert np.allclose(out,[[.1,0,0],[0,0,.1],[0,-.1,0]])
    basis=np.array([[1,0,0],[0,0,-1],[0,1,0]])
    assert np.linalg.det(basis)==pytest.approx(1)
    with pytest.raises(ValueError):makehuman_to_world(arr,0)


def test_convert_makehuman_paired_targets_preserves_vertex_indices(tmp_path):
    obj,inc,dec=_make_files(tmp_path)
    verts,faces=read_index_preserving_obj(obj)
    assert verts.shape==(8,3)
    assert faces.shape==(12,3)
    disp=read_sparse_makehuman_target(inc,8)
    assert disp[1,0]==pytest.approx(.25)
    assert disp[0,0]==0
    data=import_makehuman_prior(obj,positive_targets={'width':inc},negative_targets={'width':dec})
    p=data.prior
    assert np.ptp(p.vertices_m[:,2])==pytest.approx(1.8)
    assert p.vertices_m[:,2].min()==pytest.approx(0)
    assert len(p.faces)==12
    base=p.generate([0]).vertices
    assert p.generate([1]).vertices[1,0]-base[1,0]==pytest.approx(.025)
    assert p.generate([-1]).vertices[1,0]-base[1,0]==pytest.approx(-.015)
    assert p.generate([.5]).vertices[1,0]-base[1,0]==pytest.approx(.0125)
    assert p.generate([-.5]).vertices[1,0]-base[1,0]==pytest.approx(-.0075)
    assert np.allclose(p.generate([-1]).vertices[0],base[0])
    file,meta=save_imported_prior(data,tmp_path/'prior.npz')
    loaded=Prior.load(file)
    assert np.allclose(loaded.generate([-.7]).vertices,p.generate([-.7]).vertices)
    assert 'base_obj' in meta.read_text()


def test_makehuman_target_validation_and_legacy_prior(tmp_path):
    obj,inc,dec=_make_files(tmp_path)
    broken=tmp_path/'broken.target'
    broken.write_text('1 0.5 0 0\n1 0.2 0 0\n')
    with pytest.raises(ValueError,match='duplicate'):
        read_sparse_makehuman_target(broken,8)
    broken.write_text('8 0.3 0 0\n')
    with pytest.raises(ValueError,match='out-of-range'):
        read_sparse_makehuman_target(broken,8)
    broken.write_text('0 NaN 0 0\n')
    with pytest.raises(ValueError,match='nonfinite'):
        read_sparse_makehuman_target(broken,8)
    with pytest.raises(ValueError):
        import_makehuman_prior(obj,positive_targets={'width':inc},meters_per_native_unit=100)
    imported=import_makehuman_prior(obj,positive_targets={'width':inc})
    # Without a decreasing target, zero deformation is an honest fallback.
    assert np.allclose(imported.prior.generate([-1]).vertices, imported.prior.vertices_m)
    old=Prior(imported.prior.vertices_m,imported.prior.faces,
              imported.prior.shape_deltas_m,('width',),{},'legacy_linear')
    old.save(tmp_path/'legacy.npz')
    legacy=Prior.load(tmp_path/'legacy.npz')
    assert np.allclose(legacy.generate([-1]).vertices,
                      legacy.vertices_m-legacy.shape_deltas_m[0])
