# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "libs" / "python" / "capture_analysis"))

from capture_analysis.radar_motion.seed import (  # noqa: E402
    LinearKinematicsModel,
    RadarMotionFeaturizer,
    fit_ridge_model,
    generate_synthetic_sequence,
    iter_stacked_features,
)


def test_descriptor_tracks_range_and_doppler_sign() -> None:
    a = generate_synthetic_sequence(40, phase=0.1, seed=3)
    f = RadarMotionFeaturizer(history=4)
    descriptors = [f.push(frame)[0] for frame in a.frames]
    observed_r = np.asarray([d.peak_range_norm for d in descriptors])
    observed_d = np.asarray([d.peak_doppler_norm for d in descriptors])
    expected_r = a.targets[:, 2]
    expected_d = a.targets[:, 3]
    assert np.corrcoef(observed_r, expected_r)[0, 1] > 0.90
    assert np.corrcoef(observed_d, expected_d)[0, 1] > 0.90


def test_ridge_roundtrip_and_provenance_guard(tmp_path: Path) -> None:
    history = 5
    s = generate_synthetic_sequence(120, phase=0.4, seed=5)
    x = iter_stacked_features(s.frames, history)
    model = fit_ridge_model(
        x,
        s.targets,
        target_names=s.target_names,
        history=history,
        training_evidence="synthetic_only",
        calibrated=False,
    )
    assert not model.hardware_validated
    path = tmp_path / "model.npz"
    model.save(path)
    loaded = LinearKinematicsModel.load(path)
    assert loaded.training_evidence == "synthetic_only"
    assert loaded.target_names == s.target_names
    assert loaded.predict(x[-1]).keys() == model.predict(x[-1]).keys()


def test_shuffle_negative_control_is_worse() -> None:
    history = 6
    train = generate_synthetic_sequence(260, phase=0.2, seed=1)
    test = generate_synthetic_sequence(200, phase=1.5, range_bias=0.04, seed=2)
    x = iter_stacked_features(train.frames, history)
    xt = iter_stacked_features(test.frames, history)
    good = fit_ridge_model(x, train.targets, target_names=train.target_names, history=history, alpha=0.2)
    good_hat = np.vstack([list(good.predict(v).values()) for v in xt])
    good_rmse = float(np.sqrt(np.mean((good_hat[:, 0] - test.targets[:, 0]) ** 2)))

    shuffled = train.targets.copy()
    np.random.default_rng(7).shuffle(shuffled, axis=0)
    bad = fit_ridge_model(x, shuffled, target_names=train.target_names, history=history, alpha=0.2)
    bad_hat = np.vstack([list(bad.predict(v).values()) for v in xt])
    bad_rmse = float(np.sqrt(np.mean((bad_hat[:, 0] - test.targets[:, 0]) ** 2)))
    assert bad_rmse > good_rmse * 1.10



def test_descriptor_normalizes_preview_geometry() -> None:
    a = generate_synthetic_sequence(80, rows=32, cols=32, phase=0.7, seed=11)
    b = generate_synthetic_sequence(80, rows=48, cols=64, phase=0.7, seed=11)
    fa = RadarMotionFeaturizer(history=4)
    fb = RadarMotionFeaturizer(history=4)
    # Use fresh featurizers per sequence; compare the normalized physical peak tracks.
    fa.reset()
    fb.reset()
    pa = np.asarray([[d.peak_range_norm, d.peak_doppler_norm] for d in [fa.push(frame)[0] for frame in a.frames]])
    pb = np.asarray([[d.peak_range_norm, d.peak_doppler_norm] for d in [fb.push(frame)[0] for frame in b.frames]])
    assert float(np.mean(np.abs(pa[:, 0] - pb[:, 0]))) < 0.035
    assert float(np.mean(np.abs(pa[:, 1] - pb[:, 1]))) < 0.06


def test_invalid_matrix_rejected() -> None:
    f = RadarMotionFeaturizer()
    with pytest.raises(ValueError):
        f.push(np.asarray([1.0, 2.0]))
    x = np.ones((8, 8), dtype=float)
    x[0, 0] = np.nan
    with pytest.raises(ValueError):
        f.push(x)
