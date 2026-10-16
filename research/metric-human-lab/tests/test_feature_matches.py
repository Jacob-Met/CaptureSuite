import cv2
import numpy as np
import pytest
from metric_human.feature_matches import match_masked_rgb_features


def write_pair(tmp_path):
    rng=np.random.default_rng(22)
    img=rng.integers(30,220,(410,520),dtype=np.uint8)
    mask=np.zeros_like(img)
    cv2.rectangle(mask,(45,55),(470,350),255,-1)
    # Add irregular high-contrast patterns only on foreground; background is
    # flat, so the detector cannot succeed by fitting background landmarks.
    img[mask==0]=10
    for x,y in rng.integers([70,75],[450,330],size=(80,2)):
        cv2.circle(img,(int(x),int(y)),int(rng.integers(3,11)),int(rng.integers(30,240)),-1)
    warped = cv2.warpAffine(img,np.float32([[1,0,8],[0,1,-5]]),(520,410))
    new_mask=cv2.warpAffine(mask,np.float32([[1,0,8],[0,1,-5]]),(520,410))
    names=[]
    for name,arr in zip(('first.png','second.png','mask1.png','mask2.png'),(img,warped,mask,new_mask)):
        p=tmp_path/name;cv2.imwrite(str(p),arr);names.append(p)
    return names


def test_mutual_features_are_reproducible_with_input_hashes(tmp_path):
    paths=write_pair(tmp_path)
    result=match_masked_rgb_features(*paths)
    again=match_masked_rgb_features(*paths)
    assert result.to_dict()==again.to_dict()
    assert len(result.pixels_first)>35
    uv1=np.asarray(list(result.pixels_first.values()))
    uv2=np.asarray(list(result.pixels_second.values()))
    err=np.linalg.norm((uv2-uv1)-np.array([8,-5]),axis=1)
    assert np.median(err)<.5
    assert result.to_dict()['metric_scale_verified'] is False


def test_blank_foreground_and_mismatched_dimensions_refused(tmp_path):
    paths=write_pair(tmp_path)
    cv2.imwrite(str(paths[0]),np.zeros((410,520),np.uint8))
    with pytest.raises(ValueError,match='texture'):
        match_masked_rgb_features(*paths)
    paths=write_pair(tmp_path)
    cv2.imwrite(str(paths[2]),np.ones((40,50),np.uint8)*255)
    with pytest.raises(ValueError,match='dimensions'):
        match_masked_rgb_features(*paths)


def test_requires_actual_masks_no_silent_background_fallback(tmp_path):
    paths=write_pair(tmp_path)
    with pytest.raises(ValueError,match='Could not read'):
        match_masked_rgb_features(paths[0],paths[1],tmp_path/'missing-mask.png',paths[3])


def test_cli_match_features(tmp_path, monkeypatch):
    import json
    from metric_human.cli import main
    paths=write_pair(tmp_path)
    target=tmp_path/'matches.json'
    monkeypatch.setattr('sys.argv',['metric-human','match-features',
        '--image-first',str(paths[0]),'--image-second',str(paths[1]),
        '--mask-first',str(paths[2]),'--mask-second',str(paths[3]),
        '--out',str(target)])
    main()
    data=json.loads(target.read_text())
    assert data['matched_features']>=35
    assert data['metric_scale_verified'] is False
