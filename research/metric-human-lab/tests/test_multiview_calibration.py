import numpy as np
import pytest

from metric_human.cameras import Camera
from metric_human.multiview_calibration import recover_relative_cameras


def make_pair(seed=31, baseline=0.55, noise=0.18, count=110, outliers=0, planar=False):
    rng = np.random.default_rng(seed)
    cloud = rng.uniform(-0.65, 0.65, (count, 3))
    cloud[:, 2] = 0.8 if planar else rng.uniform(0.35, 1.55, count)
    cam1 = Camera.look_at([0.2, -3.1, 1.0], [0, 0, 0.95], width=960, height=720,
                          focal=920, model='perspective')
    cam2 = Camera.look_at([0.2 + baseline, -3.1, 1.0], [0, 0, 0.95], width=960,
                          height=720, focal=920, model='perspective')
    u1, _ = cam1.project(cloud)
    u2, _ = cam2.project(cloud)
    u1 += rng.normal(0, noise, u1.shape)
    u2 += rng.normal(0, noise, u2.shape)
    if outliers:
        idx = rng.choice(count, outliers, replace=False)
        u2[idx] = rng.uniform((100, 100), (850, 630), (outliers, 2))
    a = {f'point_{i:03d}': u1[i].tolist() for i in range(count)}
    b = {f'point_{i:03d}': u2[i].tolist() for i in range(count)}
    return a, b, cam1, cam2


def solve(a, b, **kwargs):
    return recover_relative_cameras(a, b, image_width=960, image_height=720,
                                    first_fx_px=920, first_fy_px=920, **kwargs)


def test_two_view_relative_orientation_translation_and_nonmetric_provenance():
    a, b, cam1, cam2 = make_pair()
    r = solve(a, b)
    expected_R = cam2.rotation @ cam1.rotation.T
    angle = np.degrees(np.arccos(np.clip((np.trace(r.second_camera.rotation @ expected_R.T)-1)/2, -1, 1)))
    assert angle < 1
    expected_t = cam2.translation - expected_R @ cam1.translation
    expected_t /= np.linalg.norm(expected_t)
    assert np.dot(r.second_camera.translation, expected_t) > 0.99
    assert r.reprojection_rmse_px < 1
    assert r.median_parallax_deg > 1.5
    assert r.to_dict()['metric_scale_verified'] is False
    assert r.to_dict()['metric_scale_source'] == 'unknown_global_similarity_gauge'
    assert np.isclose(np.linalg.norm(r.second_camera.translation), 1)


def test_outlier_robustness_and_stable_seed():
    a,b,_,_ = make_pair(outliers=19)
    r1 = solve(a,b)
    r2 = solve(a,b)
    assert 75 <= len(r1.inlier_labels) <= 91
    assert r1.inlier_labels == r2.inlier_labels
    assert np.allclose(r1.second_camera.rotation,r2.second_camera.rotation)


def test_no_3d_scale_can_be_inferred_from_corresponding_images():
    a,b,_,_ = make_pair()
    r = solve(a,b)
    assert np.isclose(np.linalg.norm(r.second_camera.translation), 1.)
    assert 'points_baseline_units' in r.to_dict()
    assert 'points_meters' not in r.to_dict()


def test_low_baseline_refused():
    a,b,_,_ = make_pair(baseline=1e-6,noise=0)
    with pytest.raises(ValueError,match='parallax|degener|triangul|reprojection'):
        solve(a,b)


def test_near_planar_features_refused():
    a,b,_,_ = make_pair(planar=True,noise=0)
    with pytest.raises(ValueError,match='planar|Planar|parallax|degener'):
        solve(a,b)


def test_too_few_degenerate_nonfinite_and_weak_support_refused():
    a,b,_,_ = make_pair()
    with pytest.raises(ValueError,match='12'):
        solve(dict(list(a.items())[:9]),dict(list(b.items())[:9]))
    deg = {k: [500., 200.] for k in a}
    with pytest.raises(ValueError,match='degenerate'):
        solve(deg,b)
    corrupt = dict(a); corrupt['point_003']=[np.nan,7]
    with pytest.raises(ValueError,match='Nonfinite'):
        solve(corrupt,b)
    rng=np.random.default_rng(8)
    scrambled=dict(b)
    for k in list(scrambled)[:65]:scrambled[k]=rng.uniform(100,800,2).tolist()
    with pytest.raises(ValueError,match='Not enough|Insufficient|failed|high'):
        solve(a,scrambled)


def test_camera_intrinsics_not_silently_guessed():
    a,b,c1,c2 = make_pair(noise=0.0)
    with pytest.raises(ValueError, match='intrinsics'):
        solve(a,b,second_fx_px=0.0)
    with pytest.raises(ValueError, match='Thresholds'):
        solve(a,b,min_median_parallax_deg=0)


def test_pixel_noise_and_outliers_experiment_across_seeds():
    """Changed-subject repeat: avoids accidentally certifying a single lucky seed."""
    rotation_errors=[]
    for seed in (7, 11, 19, 37, 47):
        a,b,c1,c2 = make_pair(seed=seed, baseline=.65,noise=.15, outliers=14)
        result=solve(a,b)
        true_relative=c2.rotation @ c1.rotation.T
        delta=result.second_camera.rotation @ true_relative.T
        rotation_errors.append(float(np.degrees(np.arccos(np.clip((np.trace(delta)-1)/2,-1,1)))))
        assert result.ransac_inlier_count >= 80
        assert result.reprojection_rmse_px < 1.2
    assert float(np.median(rotation_errors)) < 1.5
    assert max(rotation_errors) < 3.0


def test_cli_two_view_output_keeps_scale_unknown(tmp_path,monkeypatch,capsys):
    import json
    from metric_human.cli import main
    a,b,_,_ = make_pair(count=105,noise=.11,outliers=8)
    source=tmp_path/'pairs.json'
    dest=tmp_path/'calibration.json'
    source.write_text(json.dumps({'pixels_first':a,'pixels_second':b}))
    monkeypatch.setattr('sys.argv',['metric-human','calibrate-two-view',
       '--correspondences-json',str(source),'--width','960','--height','720',
       '--fx','920','--fy','920','--out',str(dest)])
    main()
    record=json.loads(dest.read_text())
    assert record['metric_scale_verified'] is False
    assert record['camera_baseline_arbitrary_units']==1.0
    assert len(record['points_baseline_units'])>75
    assert 'metric_scale_verified' in capsys.readouterr().out
