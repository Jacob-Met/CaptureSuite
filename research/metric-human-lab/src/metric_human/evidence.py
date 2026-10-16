"""Reproducible file binding for metric-depth evidence in reconstruction runs.

Proof that a file was calibrated is *not* proof that calibration measurements
were physically correct. Exact hashes prevent silent substitution of a
relative-depth .npy for the anchored metric one in a saved session manifest.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path


def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def write_aligned_depth_receipt(*, aligned_path, relative_path, anchors_path,
                                alignment, max_rmse_m):
    aligned_path=Path(aligned_path)
    receipt={
        'schema':'metric-human/metric-depth-receipt/v1',
        'evidence_type':'affine_alignment_with_independent_metric_surface_anchors',
        'metric_depth_file_sha256':sha256_file(aligned_path),
        'relative_depth_file_sha256':sha256_file(relative_path),
        'surface_anchor_file_sha256':sha256_file(anchors_path),
        'depth_calibration':alignment.to_dict(),
        'admission_max_anchor_rmse_m':float(max_rmse_m),
        'actual_metric_accuracy_independently_validated':False,
        'limitations':['File provenance and regression residuals do not prove anchor correctness.',
                       'Reprojection and cross-view consistency need separate tests.',
                       'This receipt does not verify geometry or scale of a human body.'],
    }
    path=aligned_path.with_suffix('.alignment.json')
    path.write_text(json.dumps(receipt,indent=2),encoding='utf8')
    return receipt,path


def verify_metric_depth_receipt(*,depth_file,receipt_file):
    """Fail closed if the referenced depth array differs from calibrated bytes."""
    receipt=json.loads(Path(receipt_file).read_text(encoding='utf8'))
    if receipt.get('schema')!='metric-human/metric-depth-receipt/v1':
        raise ValueError('Unrecognized metric depth receipt schema')
    if receipt.get('evidence_type')!='affine_alignment_with_independent_metric_surface_anchors':
        raise ValueError('Depth receipt does not claim independent metric anchor calibration')
    if receipt.get('metric_depth_file_sha256')!=sha256_file(depth_file):
        raise ValueError('Metric depth array differs from calibrated receipt digest')
    cal=receipt.get('depth_calibration',{})
    try:
        n=int(cal.get('n_anchors',0))
        rmse=float(cal.get('anchor_rmse_m',float('inf')))
        threshold=float(receipt.get('admission_max_anchor_rmse_m',-1))
        slope=float(cal.get('slope',float('nan')))
        intercept=float(cal.get('intercept_m',float('nan')))
    except (ValueError,TypeError,OverflowError) as e:
        raise ValueError('Invalid metric depth alignment receipt') from e
    if (n<3 or not math.isfinite(rmse) or rmse<0 or
        not math.isfinite(threshold) or threshold<=0 or rmse>threshold or
        not math.isfinite(slope) or not math.isfinite(intercept) or abs(slope)<1e-12):
        raise ValueError('Metric depth alignment receipt fails calibration thresholds')
    return {'depth_provenance':'affine_metric_surface_anchor_calibration',
            'receipt_sha256':sha256_file(receipt_file),
            'depth_sha256':sha256_file(depth_file),
            'not_real_world_accuracy_certification':True}
