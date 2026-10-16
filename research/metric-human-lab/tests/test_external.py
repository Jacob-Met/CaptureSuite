import json
from pathlib import Path
import pytest
import trimesh
from metric_human.external import run_external_mesh_benchmark


def test_external_benchmark_accepts_known_unit_mesh(tmp_path):
    src=trimesh.creation.capsule(height=1.2,radius=.2,count=[7,16])
    src.apply_translation([0,0,.4])
    path=tmp_path/'reference.obj';src.export(path)
    result=run_external_mesh_benchmark(path,tmp_path/'results',units='m',resolution=23,
                                       views=(1,2,4),width=120,height=150)
    assert result['rows'][-1]['voxel_iou_against_voxelized_source'] > result['rows'][0]['voxel_iou_against_voxelized_source']
    assert result['real_camera_pose_estimation_demonstrated'] is False
    assert len(result['source_mesh_sha256'])==64
    assert (tmp_path/'results'/'reproducible_input.json').exists()


def test_external_benchmark_rejects_unit_assumptions(tmp_path):
    src=trimesh.creation.box(extents=(.5,.4,1.5))
    path=tmp_path/'reference.obj';src.export(path)
    with pytest.raises(ValueError,match='meters or millimeters'):
        run_external_mesh_benchmark(path,tmp_path/'results',units='unknown')
    with pytest.raises(ValueError,match='plausibly human-sized'):
        run_external_mesh_benchmark(path,tmp_path/'results',units='mm')
