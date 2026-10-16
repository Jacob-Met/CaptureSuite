import json
from pathlib import Path
import numpy as np
import cv2
import pytest
from metric_human.photos import prepare_photographs
from metric_human.cli import from_config


def make_masks(tmp_path,n):
    photos=[]
    masks=[]
    for i in range(n):
        img=np.full((180,160,3),200,np.uint8)
        mask=np.zeros((180,160),np.uint8)
        half=int(14+8*np.cos(i*np.pi/n)**2)
        cv2.ellipse(mask,(80,25),(11,13),0,0,360,255,-1)
        cv2.rectangle(mask,(80-half,40),(80+half,110),255,-1)
        cv2.rectangle(mask,(65,100),(76,169),255,-1)
        cv2.rectangle(mask,(84,100),(95,169),255,-1)
        p=tmp_path/f'photo{i}.png';mp=tmp_path/f'mask{i}.png'
        cv2.imwrite(str(p),img);cv2.imwrite(str(mp),mask)
        photos.append(p);masks.append(mp)
    return photos,masks


def test_zero_measurement_photo_prep_flags_unverified(tmp_path):
    photos,masks=make_masks(tmp_path,4)
    prep=prepare_photographs(photos,tmp_path/'prep',masks=masks,resolution=29)
    manifest=json.loads(Path(prep['manifest']).read_text())
    assert prep['scale_source']=='inferred_unvalidated'
    assert prep['views']==4
    assert manifest['calibration_status']=='approximate_uncalibrated_photographs'
    assert all((tmp_path/'prep'/v['mask']).exists() for v in manifest['views'])
    result=from_config(prep['manifest'],tmp_path/'reconstructed')
    assert result['metric_scale_verified'] is False
    assert (tmp_path/'reconstructed'/'reconstruction.glb').stat().st_size>500
    assert (tmp_path/'reconstructed'/'reconstruction.obj').stat().st_size>500
    report=json.loads((tmp_path/'reconstructed'/'report.json').read_text())
    assert report['input_assumptions']['height_prior_m']==pytest.approx(1.70)
    assert len(report['reprojection_diagnostics'])==4


def test_height_anchor_does_not_claim_real_shape_validation(tmp_path):
    photos,masks=make_masks(tmp_path,2)
    prep=prepare_photographs(photos,tmp_path/'prep',masks=masks,
                             known_height_m=1.9,angles_deg=[0,90],resolution=28)
    conf=json.loads(Path(prep['manifest']).read_text())
    assert conf['height_prior_m']==1.9
    assert conf['scale_source']=='user_height_anchor'
    assert 'approximate' in conf['calibration_status']


def test_reject_mismatched_mask_count_and_empty_mask(tmp_path):
    photos,masks=make_masks(tmp_path,3)
    with pytest.raises(ValueError):
        prepare_photographs(photos,tmp_path/'a',masks=masks[:2])
    with pytest.raises(ValueError):
        prepare_photographs(photos,tmp_path/'b',masks=masks,angles_deg=[0,90])
    cv2.imwrite(str(masks[0]),np.zeros((180,160),np.uint8))
    with pytest.raises(ValueError):
        prepare_photographs(photos,tmp_path/'c',masks=masks)


def test_manifest_fuses_joint_observation_with_volume_report(tmp_path):
    from metric_human.bench import default_grid,build_scene
    grid=default_grid(25)
    _,_,views=build_scene(grid,max_views=4,width=130,height=180)
    for i,v in enumerate(views):
        cv2.imwrite(str(tmp_path/f'm{i}.png'),v.mask.astype(np.uint8)*255)
    point=np.array([.25,.01,1.35])
    landmark_rows=[]
    for i,v in enumerate(views):
        uv,z=v.camera.project(point.reshape(1,3))
        landmark_rows.append({'label':'test_shoulder','view':v.label,'uv':uv[0].tolist(),'confidence':.9})
    conf={'grid':grid.to_dict(),'scale_source':'synthetic_world_coordinates',
          'landmark_observations':landmark_rows,
          'views':[{'mask':f'm{i}.png','label':v.label,'camera':v.camera.to_dict()} for i,v in enumerate(views)]}
    path=tmp_path/'input.json';path.write_text(json.dumps(conf))
    from_config(path,tmp_path/'out')
    joints=json.loads((tmp_path/'out'/'joints.json').read_text())
    found=joints['triangulated_landmarks']['test_shoulder']
    assert found['status']=='triangulated'
    assert np.allclose(found['xyz_world_units'],point,atol=1e-5)
    assert found['reprojection_rmse_pixels']<1e-5
