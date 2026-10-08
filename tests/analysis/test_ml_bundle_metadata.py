# SPDX-License-Identifier: GPL-3.0-only
"""ML bundle metadata describes the real Parquet values and integer window grid."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from capture_analysis.ml_bundle.job import DEFAULT_TARGET_COLUMNS, run_ml_bundle_job

ROOT = Path(__file__).resolve().parents[2]


def _seed_inputs(package: Path, *, short: bool = False) -> dict[Path, bytes]:
    times = [0, 25_000_000, 50_000_000] if short else [
        index * 100_000_000 for index in range(15)
    ]
    labels = [0.0, 100.0, 30.0] if short else [
        0.0, 100.0, 30.0, 20.0, 120.0, 50.0, 40.0, 140.0,
        70.0, 60.0, 160.0, 90.0, 80.0, 180.0, 110.0,
    ]
    teacher = {
        "session_time_ns": times,
        "valid_elbow_L": [True] * len(times),
        "valid_elbow_R": [True] * len(times),
    }
    for multiple, column in enumerate(DEFAULT_TARGET_COLUMNS, 1):
        teacher[column] = [multiple * value for value in labels]
    kin = package / "processing/jobs/kin/kinematics/kinematics.parquet"
    features = package / "processing/jobs/feat/features/radar/radar.fixture/energy.parquet"
    kin.parent.mkdir(parents=True)
    features.parent.mkdir(parents=True)
    pd.DataFrame(teacher).to_parquet(kin, index=False)
    pd.DataFrame({
        "t_ns": [0, 250_000_000, 600_000_000, 850_000_000, 1_200_000_000, 1_500_000_000],
        "energy": [100.0, 200.0, 300.0, 400.0, 500.0, 600.0],
    }).to_parquet(features, index=False)
    return {path: path.read_bytes() for path in (kin, features)}


def _bundle(tmp_path: Path, *, short=False, window=0.2, hop=0.3, rate=20.0):
    package = tmp_path / "package"
    inputs = _seed_inputs(package, short=short)
    work = tmp_path / "result"
    outputs, warnings = [], []
    run_ml_bundle_job(
        package, work, SimpleNamespace(session_id="metadata-fixture"),
        kinematics_job_id="kin", features_job_id="feat",
        window_sec=window, hop_sec=hop, grid_rate_hz=rate,
        outputs=outputs, warnings=warnings,
    )
    assert warnings == []
    assert {path: path.read_bytes() for path in inputs} == inputs
    for row in outputs:
        content = (work / row["relativePath"]).read_bytes()
        assert row["bytes"] == len(content)
        assert row["sha256"] == hashlib.sha256(content).hexdigest()
    doc = json.loads((work / "ml_bundle/manifest.json").read_bytes())
    import jsonschema
    schema = json.loads((ROOT / "schemas/ml_bundle/ml_bundle.manifest.schema.json").read_bytes())
    jsonschema.validate(doc, schema)
    return doc, pd.read_parquet(work / "ml_bundle/windows.parquet")


def test_raw_features_and_targets_are_not_declared_normalized(tmp_path: Path) -> None:
    doc, windows = _bundle(tmp_path)
    assert windows["motion_energy"].tolist() == [100.0, 200.0, 300.0, 400.0, 500.0]
    assert windows["motion_energy"].mean() == 300.0
    assert windows["omega_elbow_flex_L"].tolist() == [90.0, 150.0, 210.0, 270.0, 330.0]
    assert doc["normalization"] == {"input": "none", "target": "none"}


def test_declared_method_matches_nearest_features_and_window_medians(tmp_path: Path) -> None:
    doc, windows = _bundle(tmp_path)
    assert windows["theta_elbow_flex_L"].tolist() == [30.0, 50.0, 70.0, 90.0, 110.0]
    # The center samples are 100,120,140,160,180: linear interpolation differs.
    assert windows["theta_elbow_flex_L"].tolist() != [100.0, 120.0, 140.0, 160.0, 180.0]
    assert windows["motion_energy"].tolist() == [100.0, 200.0, 300.0, 400.0, 500.0]
    grid = doc["analysisGrids"][0]
    assert grid["method"] == "nearest_feature_window_median_targets"
    assert grid["params"]["windowBounds"] == "inclusive"


@pytest.mark.parametrize(("hop", "requested_rate"), [
    (0.05, 20.0), (0.3, 20.0), (0.3000000009, 99.0),
])
def test_rate_and_hop_describe_integer_output_spacing(
    tmp_path: Path, hop: float, requested_rate: float,
) -> None:
    doc, windows = _bundle(tmp_path, hop=hop, rate=requested_rate)
    centers = windows["session_time_ns"].tolist()
    deltas = {right - left for left, right in zip(centers, centers[1:], strict=False)}
    assert deltas == {int(hop * 1e9)}
    actual_hop = deltas.pop()
    grid = doc["analysisGrids"][0]
    assert grid["rateHz"] == 1e9 / actual_hop
    assert grid["params"]["hopNs"] == actual_hop
    assert grid["params"]["rateBasis"] == "configured_integer_hop"
    assert grid["params"]["windowHopSec"] == doc["window"]["hopSec"] == actual_hop / 1e9
    assert grid["params"]["requestedHopSec"] == hop
    assert grid["params"]["requestedRateHz"] == requested_rate
    assert grid["params"]["centerPolicy"] == "regular_hop"


def test_quantized_window_records_actual_bounds_and_requested_duration(tmp_path: Path) -> None:
    requested = 0.2000000019
    doc, windows = _bundle(tmp_path, window=requested)
    assert windows["session_time_ns"].tolist() == [
        100_000_000, 400_000_000, 700_000_000, 1_000_000_000, 1_300_000_000,
    ]
    assert windows["theta_elbow_flex_L"].tolist() == [30.0, 50.0, 70.0, 90.0, 110.0]
    params = doc["analysisGrids"][0]["params"]
    assert params["halfWindowNs"] == 100_000_000
    assert params["requestedWindowSec"] == requested
    assert params["windowSec"] == doc["window"]["windowSec"] == 0.2


def test_short_source_explicitly_identifies_the_median_center_fallback(tmp_path: Path) -> None:
    doc, windows = _bundle(tmp_path, short=True)
    assert windows["session_time_ns"].tolist() == [25_000_000]
    assert windows["theta_elbow_flex_L"].tolist() == [30.0]
    params = doc["analysisGrids"][0]["params"]
    assert params["centerPolicy"] == "median_fallback"
    assert params["rateBasis"] == "configured_integer_hop"
    assert doc["analysisGrids"][0]["rateHz"] == 1e9 / params["hopNs"]


def test_job_api_keeps_requested_parameters_and_final_artifact_receipts(tmp_path: Path) -> None:
    from capture_analysis import JobParams, hash_sources_tree, run

    package = tmp_path / "recording.mmsession"
    shutil.copytree(ROOT / "tests/fixtures/mini_session", package)
    inputs = _seed_inputs(package)
    raw_before = hash_sources_tree(package)
    extra = {
        "kinematics_job_id": "kin", "features_job_id": "feat",
        "window_sec": 0.2000000019, "hop_sec": 0.3000000009, "grid_rate_hz": 99.0,
    }
    result = run(package, JobParams(command="ml_bundle", overwrite_job_id="metadata", extra=extra))
    params = json.loads((result.job_dir / "params.json").read_bytes())
    assert params["extra"] == extra
    assert hash_sources_tree(package) == raw_before
    assert {path: path.read_bytes() for path in inputs} == inputs
    saved = json.loads((result.job_dir / "job_manifest.json").read_bytes())
    assert saved == result.manifest
    for row in saved["outputs"]:
        content = (result.job_dir / row["relativePath"]).read_bytes()
        assert row["bytes"] == len(content)
        assert row["sha256"] == hashlib.sha256(content).hexdigest()
    bundle = json.loads((result.job_dir / "ml_bundle/manifest.json").read_bytes())
    assert bundle["analysisGrids"][0]["rateHz"] == 1e9 / 300_000_000
    assert bundle["window"] == {"windowSec": 0.2, "hopSec": 0.3, "targetTime": "center"}
