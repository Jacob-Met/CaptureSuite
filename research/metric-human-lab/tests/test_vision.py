"""Adapters can be validated without network, torch or pretrained weights."""
import json
from pathlib import Path
import cv2
import numpy as np
import pytest

from metric_human.vision import (generate_sam2_masks,generate_relative_depth,
                                 _binary_mask_from_prediction,_prepare_box)


def image(tmp_path, suffix, shape=(96,80)):
    path=tmp_path/f'view{suffix}.png'
    cv2.imwrite(str(path), np.full((*shape,3),180,dtype=np.uint8))
    return path


def test_sam2_mock_masks_and_sha_provenance(tmp_path):
    paths=[image(tmp_path,i) for i in range(2)]
    boxes=[[8,4,64,85],[9,5,62,82]]
    def predictor(pil,box):
        assert tuple(pil.size)==(80,96)
        assert box[2]>box[0]
        a=np.full((96,80),-.8,np.float32)
        a[20:80,22:60]=3.0
        return a
    result=generate_sam2_masks(paths,tmp_path/'maskout',boxes=boxes,predictor=predictor)
    assert result['kind']=='segmentation_evidence_not_ground_truth'
    assert len(result['records'])==2
    for record in result['records']:
        assert len(record['sha256'])==64
        mask=cv2.imread(str(tmp_path/'maskout'/record['mask']),cv2.IMREAD_GRAYSCALE)
        assert int((mask>0).sum())==60*38
        assert record['foreground_fraction']==pytest.approx(60*38/(96*80))
    assert (tmp_path/'maskout'/'vision_manifest.json').is_file()


def test_probability_threshold_vs_logit_threshold():
    assert _binary_mask_from_prediction(np.array([[0.01,.49,.51,.99]],np.float32)).tolist()==[[False,False,True,True]]
    assert _binary_mask_from_prediction(np.array([[-2,-.1,0,2]],np.float32)).tolist()==[[False,False,False,True]]
    assert _binary_mask_from_prediction(np.array([[False,True]],bool)).tolist()==[[False,True]]


def test_sam2_rejects_invalid_mask_or_box(tmp_path):
    a=image(tmp_path,1)
    with pytest.raises(ValueError,match='Bounding box'):
        generate_sam2_masks([a],tmp_path/'bad',boxes=[[1,1,1,5]],predictor=lambda p,b: np.ones((96,80)))
    with pytest.raises(ValueError,match='source'):
        generate_sam2_masks([a],tmp_path/'bad',boxes=[[0,0,79,95]],predictor=lambda p,b: np.ones((20,30)))
    with pytest.raises(ValueError,match='no foreground'):
        generate_sam2_masks([a],tmp_path/'bad',boxes=[[0,0,79,95]],predictor=lambda p,b: np.zeros((96,80)))


def test_relative_depth_is_resized_and_not_metric(tmp_path):
    paths=[image(tmp_path,i) for i in range(2)]
    depth=lambda image: np.array([[1.,2.],[3.,4.]],dtype=np.float32)
    result=generate_relative_depth(paths,tmp_path/'depthout',predictor=depth)
    assert result['kind']=='relative_depth_evidence_not_metric_depth'
    assert result['calibrated_to_metric'] is False
    assert result['may_be_used_for_hard_carving'] is False
    for record in result['records']:
        assert record['metric_depth'] is False
        saved=np.load(tmp_path/'depthout'/record['relative_depth'],allow_pickle=False)
        assert saved.shape == (96,80)
        assert saved.dtype==np.float32
        assert saved.max()<=4 and saved.min()>=1
    assert json.loads((tmp_path/'depthout'/'vision_manifest.json').read_text())['units'].endswith('NOT_meters')


def test_relative_depth_rejects_nonfinite_predictions(tmp_path):
    a=image(tmp_path,1)
    with pytest.raises(ValueError,match='invalid map'):
        generate_relative_depth([a],tmp_path/'bad',predictor=lambda img:np.full((20,20),np.inf))


def test_explicit_box_pixel_validation():
    assert _prepare_box((0,0,80,96),80,96)==(0.,0.,80.,96.)
    with pytest.raises(ValueError):_prepare_box((0,-1,50,50),80,96)
    with pytest.raises(ValueError):_prepare_box((0,0,81,50),80,96)
