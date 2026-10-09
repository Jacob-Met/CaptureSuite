# SPDX-License-Identifier: GPL-3.0-only
"""Target selection cannot replace required ML-window fields."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from capture_analysis import JobParams, run
from capture_analysis.ml_bundle.job import DEFAULT_TARGET_COLUMNS, run_ml_bundle_job

ROOT = Path(__file__).resolve().parents[2]
BASE = 2**53 + 1
REQUIRED = ["window_id", "session_time_ns", "valid_mask", "motion_energy", "feature_stream_id"]
CUSTOM = ["torque (N·m)", "Signal", "signal", " trailing ", " "]


def _snapshot(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def _seed(package: Path) -> dict[str, str]:
    teacher = {
        "session_time_ns": [BASE + i * 100_000_000 for i in range(11)],
        "valid_elbow_L": [True] * 11,
        "valid_elbow_R": [True] * 11,
    }
    for offset, name in enumerate([*DEFAULT_TARGET_COLUMNS, *CUSTOM, ""], 1):
        teacher[name] = [float(offset * 100 + i) for i in range(11)]
    # Supply colliding columns as real retained labels. Admission must not rely
    # on their being absent from a particular teacher implementation.
    for name in REQUIRED:
        if name not in teacher:
            teacher[name] = [float(i) for i in range(11)]
    kin = package / "processing/jobs/kin/kinematics/kinematics.parquet"
    kin.parent.mkdir(parents=True)
    pd.DataFrame(teacher).to_parquet(kin, index=False)
    feat = package / "processing/jobs/feat/features/radar/fixture/energy.parquet"
    feat.parent.mkdir(parents=True)
    pd.DataFrame({
        "t_ns": [BASE, BASE + 500_000_000, BASE + 1_000_000_000],
        "energy": [10.0, 20.0, 30.0],
    }).to_parquet(feat, index=False)
    return _snapshot(package)


def _produce(package: Path, work: Path, targets):
    outputs, warnings = [], []
    result = run_ml_bundle_job(
        package, work, SimpleNamespace(session_id="target-admission-fixture"),
        kinematics_job_id="kin", features_job_id="feat",
        window_sec=0.2, hop_sec=0.2, target_columns=targets,
        outputs=outputs, warnings=warnings,
    )
    assert warnings == []
    for row in outputs:
        content = (work / row["relativePath"]).read_bytes()
        assert row["bytes"] == len(content)
        assert row["sha256"] == hashlib.sha256(content).hexdigest()
    return result


def _check_required(work: Path) -> pd.DataFrame:
    path = work / "ml_bundle/windows.parquet"
    schema = pq.read_schema(path)
    assert [schema.field(name).type for name in REQUIRED[1:4]] == [
        pa.int64(), pa.bool_(), pa.float64(),
    ]
    for name in ("window_id", "feature_stream_id"):
        dtype = schema.field(name).type
        assert pa.types.is_string(dtype) or pa.types.is_large_string(dtype)
    frame = pd.read_parquet(path)
    assert frame["session_time_ns"].tolist() == [BASE + i * 100_000_000 for i in (1, 3, 5, 7, 9)]
    assert frame["window_id"].tolist() == [f"w{i:05d}" for i in range(5)]
    assert frame["valid_mask"].tolist() == [True] * 5
    assert frame["motion_energy"].tolist() == [10.0, 20.0, 20.0, 20.0, 30.0]
    assert frame["feature_stream_id"].tolist() == ["fixture"] * 5
    return frame


@pytest.mark.parametrize("targets", [None, []], ids=["none", "empty-list"])
def test_omitted_or_empty_targets_preserve_defaults(tmp_path: Path, targets) -> None:
    package, work = tmp_path / "package", tmp_path / "result"
    original = _seed(package)
    result = _produce(package, work, targets)
    frame = _check_required(work)
    assert result["targetColumns"] == DEFAULT_TARGET_COLUMNS
    assert list(frame) == REQUIRED + DEFAULT_TARGET_COLUMNS
    for offset, name in enumerate(DEFAULT_TARGET_COLUMNS, 1):
        assert frame[name].tolist() == [float(offset * 100 + i) for i in (1, 3, 5, 7, 9)]
    assert _snapshot(package) == original


def test_custom_labels_keep_exact_identity_order_and_values(tmp_path: Path) -> None:
    package, work = tmp_path / "package", tmp_path / "result"
    original = _seed(package)
    selected = list(reversed(CUSTOM))
    result = _produce(package, work, selected)
    frame = _check_required(work)
    manifest = json.loads((work / "ml_bundle/manifest.json").read_bytes())
    assert result["targetColumns"] == manifest["targetColumns"] == selected
    assert list(frame) == REQUIRED + selected
    for name in selected:
        offset = 5 + CUSTOM.index(name)
        assert frame[name].tolist() == [float(offset * 100 + i) for i in (1, 3, 5, 7, 9)]
    assert _snapshot(package) == original


@pytest.mark.parametrize("name", REQUIRED)
def test_required_output_names_are_refused_before_publication(tmp_path: Path, name: str) -> None:
    package, work = tmp_path / "package", tmp_path / "result"
    original = _seed(package)
    try:
        with pytest.raises(ValueError, match="required bundle columns"):
            _produce(package, work, [name])
    finally:
        assert _snapshot(package) == original
    assert not work.exists()


@pytest.mark.parametrize("name", [DEFAULT_TARGET_COLUMNS[0], CUSTOM[0]])
def test_duplicate_target_labels_are_refused(tmp_path: Path, name: str) -> None:
    package, work = tmp_path / "package", tmp_path / "result"
    original = _seed(package)
    try:
        with pytest.raises(ValueError, match="distinct"):
            _produce(package, work, [name, name])
    finally:
        assert _snapshot(package) == original
    assert not work.exists()


@pytest.mark.parametrize("name", ["", None, 7])
def test_target_labels_must_be_nonempty_strings(tmp_path: Path, name) -> None:
    package, work = tmp_path / "package", tmp_path / "result"
    original = _seed(package)
    try:
        with pytest.raises(ValueError, match="nonempty string"):
            _produce(package, work, [name])
    finally:
        assert _snapshot(package) == original
    assert not work.exists()


def test_missing_custom_target_retains_existing_failure(tmp_path: Path) -> None:
    package, work = tmp_path / "package", tmp_path / "result"
    original = _seed(package)
    with pytest.raises(RuntimeError, match="missing target column 'not recorded'"):
        _produce(package, work, ["not recorded"])
    assert _snapshot(package) == original
    assert not work.exists()


@pytest.mark.parametrize("targets", [
    ["session_time_ns"], [DEFAULT_TARGET_COLUMNS[0], DEFAULT_TARGET_COLUMNS[0]],
], ids=["timestamp-collision", "duplicate"])
def test_public_job_retains_failed_attempt_without_bundle(tmp_path: Path, targets) -> None:
    package = tmp_path / "recording.mmsession"
    shutil.copytree(ROOT / "tests/fixtures/mini_session", package)
    original = _seed(package)
    with pytest.raises(ValueError):
        run(package, JobParams(
            command="ml_bundle", overwrite_job_id="invalid-targets",
            extra={
                "kinematics_job_id": "kin", "features_job_id": "feat",
                "window_sec": 0.2, "hop_sec": 0.2, "target_columns": targets,
            },
        ))
    work = package / "processing/jobs/invalid-targets"
    saved = json.loads((work / "job_manifest.json").read_bytes())
    assert saved["status"] == "failed"
    assert saved["errors"]
    assert not (work / "ml_bundle").exists()
    assert all(not row["relativePath"].startswith("ml_bundle/") for row in saved["outputs"])
    for row in saved["outputs"]:
        content = (work / row["relativePath"]).read_bytes()
        assert row["bytes"] == len(content)
        assert row["sha256"] == hashlib.sha256(content).hexdigest()
    after = _snapshot(package)
    assert {name: after[name] for name in original} == original
