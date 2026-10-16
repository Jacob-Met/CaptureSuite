import json
import numpy as np
import cv2
import pytest

from metric_human.evidence import write_aligned_depth_receipt,verify_metric_depth_receipt
from metric_human.depth import align_relative_depth
from metric_human.cli import from_config
from metric_human.cameras import Camera
from metric_human.volume import Grid


def test_metric_depth_receipt_detects_tampering(tmp_path):
    relative=np.array([[1.,2.,3.,4.],[2.,3.,4.,5.]],dtype=float)
    anchors=[{'u':u,'v':0,'camera_z_m':float(2+.4*relative[0,u])} for u in range(4)]
    raw=tmp_path/'relative.npy';np.save(raw,relative)
    source=tmp_path/'anchors.json';source.write_text(json.dumps({'anchors':anchors}))
    fitted,alignment=align_relative_depth(relative,anchors)
    metric=tmp_path/'metric.npy';np.save(metric,fitted)
    receipt,path=write_aligned_depth_receipt(aligned_path=metric,relative_path=raw,
                               anchors_path=source,alignment=alignment,max_rmse_m=.05)
    assert verify_metric_depth_receipt(depth_file=metric,receipt_file=path)['depth_provenance']
    with open(metric,'wb') as f:np.save(f,fitted+10)
    with pytest.raises(ValueError,match='differs'):
        verify_metric_depth_receipt(depth_file=metric,receipt_file=path)


def test_reconstruct_rejects_unverified_depth_and_accepts_bound_receipt(tmp_path):
    grid=Grid((-.2,-.2,0),(.2,.2,1.8),(10,10,25))
    cam=Camera.look_at([0,-2,.9],[0,0,.9],width=64,height=64,focal=25)
    cv2.imwrite(str(tmp_path/'mask.png'),np.ones((64,64),np.uint8)*255)
    rel=np.tile(np.linspace(1,2,64),(64,1))
    raw=tmp_path/'rel.npy';np.save(raw,rel)
    anchors=[{'u':i,'v':20,'camera_z_m':2+.1*rel[20,i]} for i in (0,15,30,45,63)]
    ap=tmp_path/'anchors.json';ap.write_text(json.dumps({'anchors':anchors}))
    fit,align=align_relative_depth(rel,anchors)
    depth=tmp_path/'depth.npy';np.save(depth,fit)
    receipt,receipt_path=write_aligned_depth_receipt(aligned_path=depth,relative_path=raw,
                          anchors_path=ap,alignment=align,max_rmse_m=.05)
    conf={'grid':grid.to_dict(),'scale_source':'inferred_unvalidated',
          'views':[{'camera':cam.to_dict(),'mask':'mask.png','depth_m':'depth.npy'}]}
    config=tmp_path/'input.json';config.write_text(json.dumps(conf))
    with pytest.raises(ValueError,match='receipt'):
        from_config(config,tmp_path/'recon')
    conf['views'][0]['depth_alignment_receipt']=receipt_path.name
    config.write_text(json.dumps(conf))
    result=from_config(config,tmp_path/'recon')
    assert result['metric_scale_verified'] is False
    out=json.loads((tmp_path/'recon'/'report.json').read_text())
    assert out['depth_evidence_receipts'][0]['receipt_sha256']


def test_receipt_rejects_nonfinite_fake_calibration(tmp_path):
    rel=np.linspace(1,3,10).reshape(2,5)
    anchors=[{'u':i,'v':0,'camera_z_m':2+.4*rel[0,i]} for i in range(5)]
    a=tmp_path/'a.json';a.write_text(json.dumps({'anchors':anchors}))
    raw=tmp_path/'r.npy';np.save(raw,rel)
    metric,align=align_relative_depth(rel,anchors)
    dest=tmp_path/'metric.npy';np.save(dest,metric)
    _,receipt=write_aligned_depth_receipt(aligned_path=dest,relative_path=raw,
                                        anchors_path=a,alignment=align,max_rmse_m=.05)
    data=json.loads(receipt.read_text())
    data['depth_calibration']['anchor_rmse_m']=float('nan')
    receipt.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='thresholds'):
        verify_metric_depth_receipt(depth_file=dest,receipt_file=receipt)
