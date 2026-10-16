import json
import subprocess
import sys
import pytest
import trimesh
from PIL import Image
from metric_human.datasets import audit_dataset_manifest


def make_fixture(tmp_path,subjects=5):
    rows=[]
    for i in range(subjects):
        f=tmp_path/f'figure_{i}.obj';body=trimesh.creation.box(extents=(.3+.01*i,.2,1))
        body.export(f)
        img=tmp_path/f'person_{i}.png';Image.new('RGB',(36,48),(30+i,50,100)).save(img)
        rows.append({'subject_id':f'subj{i:02}', 'session_id':'sess0',
                    'reference_mesh':f.name,'mesh_units':'m','images':[img.name],
                    'license':'CC0','data_kind':'procedural_synthetic','camera_status':'known'})
    f=tmp_path/'records.json';f.write_text(json.dumps({'records':rows}))
    return f,rows


def test_subject_holdouts_disjoint_and_deterministic(tmp_path):
    p,rows=make_fixture(tmp_path,subjects=9)
    a=audit_dataset_manifest(p,seed=17);b=audit_dataset_manifest(p,seed=17)
    assert a==b
    assert a['unique_subjects']==9 and a['sessions']==9
    assert min(a['split_subject_counts'].values())>0
    assert {r['split'] for r in a['records']}=={'train','validation','test'}
    assert all(r['mesh_sha256'] and r['image_sha256'] for r in a['records'])
    assert a['subject_consent_and_data_rights_independently_verified'] is False


def test_same_identity_sessions_never_split(tmp_path):
    p,rows=make_fixture(tmp_path,subjects=3)
    second=rows[0].copy();second['session_id']='sess1';rows.append(second)
    p.write_text(json.dumps({'records':rows}))
    report=audit_dataset_manifest(p)
    assert report['sessions']==4 and report['unique_subjects']==3
    assignments={r['split'] for r in report['records'] if r['subject_id']=='subj00'}
    assert len(assignments)==1


def test_duplicate_asset_bytes_across_subjects_are_rejected(tmp_path):
    p,rows=make_fixture(tmp_path,subjects=2)
    rows[1]['reference_mesh']=rows[0]['reference_mesh'];p.write_text(json.dumps({'records':rows}))
    with pytest.raises(ValueError,match='leakage'):
        audit_dataset_manifest(p)


def test_external_paths_and_undeclared_rights_rejected(tmp_path):
    p,rows=make_fixture(tmp_path,subjects=1)
    rows[0]['reference_mesh']='../outside.obj';p.write_text(json.dumps({'records':rows}))
    with pytest.raises(ValueError,match='escapes'):
        audit_dataset_manifest(p)
    rows[0]['reference_mesh']='figure_0.obj';rows[0]['license']='unknown'
    p.write_text(json.dumps({'records':rows}))
    with pytest.raises(ValueError,match='license'):
        audit_dataset_manifest(p)


def test_audit_command_creates_no_asset_copies(tmp_path):
    p,_=make_fixture(tmp_path,subjects=3)
    dest=tmp_path/'audit.json';files_before={x.name for x in tmp_path.iterdir()}
    subprocess.run([sys.executable,'-m','metric_human','audit-dataset','--manifest',str(p),
                    '--out',str(dest)],check=True,capture_output=True)
    assert {x.name for x in tmp_path.iterdir()}==files_before|{dest.name}
    report=json.loads(dest.read_text())
    assert report['unique_subjects']==3
    assert report['camera_calibration_independently_verified'] is False


def test_nondict_record_fails_closed(tmp_path):
    p=tmp_path/'manifest.json'
    p.write_text(json.dumps({'records':[None]}))
    with pytest.raises(ValueError,match='Every record must be an object'):
        audit_dataset_manifest(p)
