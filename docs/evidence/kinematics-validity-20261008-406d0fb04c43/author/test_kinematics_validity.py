# SPDX-License-Identifier: GPL-3.0-only
"""Kinematic labels must preserve missing pose evidence through the real CLI."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from capture_analysis.kinematics.compute import detection_rate, landmarks_to_kinematics

from tests.analysis.test_pose_job import _write_pose_package

ROOT = Path(__file__).resolve().parents[2]
MODEL = "mediapipe_body_fixture"
JOINTS = {
    11: (0.0, 0.0, 0.0),
    13: (1.0, 0.0, 0.0),
    15: (1.0, 1.0, 0.0),
    23: (0.0, -1.0, 0.0),
    12: (3.0, 0.0, 0.0),
    14: (4.0, 0.0, 0.0),
    16: (4.0, 1.0, 0.0),
    24: (3.0, -1.0, 0.0),
}


def _landmarks(frames: int = 5) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "session_time_ns": 1_000_000_007 + frame * 33_333_333,
                "frame_index": frame,
                "joint_index": joint,
                "x": xyz[0],
                "y": xyz[1],
                "z": xyz[2],
                "confidence": 0.9,
            }
            for frame in range(frames)
            for joint, xyz in JOINTS.items()
        ]
    )


def _compute(landmarks: pd.DataFrame, **kwargs) -> pd.DataFrame:
    return landmarks_to_kinematics(landmarks, pose_model_id=MODEL, **kwargs)


def _assert_right_limb_valid(table: pd.DataFrame) -> None:
    assert table["valid_elbow_R"].all()
    assert table["valid_shoulder_R"].all()
    for column in ("theta_elbow_flex_R", "theta_shoulder_elev_R", "theta_shoulder_flex_R"):
        np.testing.assert_allclose(table[column], 90.0, atol=1e-12)


def test_complete_pose_geometry_is_unchanged() -> None:
    table = _compute(_landmarks())
    assert table.filter(like="valid_").all().all()
    np.testing.assert_allclose(table.filter(like="theta_"), 90.0, atol=1e-12)
    np.testing.assert_allclose(table.filter(like="omega_"), 0.0, atol=1e-12)
    np.testing.assert_allclose(table.filter(like="afr_"), 0.0, atol=1e-12)
    assert table["session_time_ns"].tolist() == [
        1_000_000_007 + frame * 33_333_333 for frame in range(5)
    ]


def test_missing_hips_mask_shoulders_without_replacing_elbow_geometry() -> None:
    landmarks = _landmarks()
    landmarks = landmarks.loc[~landmarks["joint_index"].isin([23, 24])]
    table = _compute(landmarks)
    assert table[["valid_elbow_L", "valid_elbow_R"]].all().all()
    assert not table[["valid_shoulder_L", "valid_shoulder_R"]].any().any()
    np.testing.assert_allclose(table.filter(like="theta_elbow"), 90.0, atol=1e-12)
    assert table.filter(like="theta_shoulder").isna().all().all()
    assert table.filter(like="omega_shoulder").isna().all().all()
    assert detection_rate(table) == {
        "elbow_L": 1.0, "elbow_R": 1.0, "shoulder_L": 0.0, "shoulder_R": 0.0
    }


def test_frame_dropout_masks_only_dependent_joint_and_derived_labels() -> None:
    landmarks = _landmarks()
    landmarks = landmarks.loc[
        ~((landmarks["frame_index"] == 2) & (landmarks["joint_index"] == 15))
    ]
    table = _compute(landmarks)
    _assert_right_limb_valid(table)
    assert table["valid_shoulder_L"].all()
    assert table["valid_elbow_L"].tolist() == [True, True, False, True, True]
    for column in ("theta_elbow_flex_L", "omega_elbow_flex_L", "afr_elbow_L_deg"):
        assert pd.isna(table.loc[2, column]), column
    assert detection_rate(table)["elbow_L"] == 0.8


@pytest.mark.parametrize("field,value", [
    ("x", float("nan")),
    ("y", float("inf")),
    ("confidence", float("nan")),
    ("confidence", float("inf")),
    ("confidence", 0.1),
])
def test_unusable_landmark_never_makes_a_valid_angle(field: str, value: float) -> None:
    landmarks = _landmarks()
    landmarks.loc[landmarks["joint_index"] == 15, field] = value
    table = _compute(landmarks)
    _assert_right_limb_valid(table)
    assert table["valid_shoulder_L"].all()
    assert not table["valid_elbow_L"].any()
    for column in ("theta_elbow_flex_L", "omega_elbow_flex_L", "afr_elbow_L_deg"):
        assert table[column].isna().all(), column


def test_coincident_joint_masks_only_undefined_angles() -> None:
    landmarks = _landmarks()
    landmarks.loc[landmarks["joint_index"] == 15, ["x", "y", "z"]] = JOINTS[13]
    table = _compute(landmarks)
    _assert_right_limb_valid(table)
    assert table["valid_shoulder_L"].all()
    assert not table["valid_elbow_L"].any()
    assert table["theta_elbow_flex_L"].isna().all()


def test_confidence_is_per_required_landmark_not_whole_body_mean() -> None:
    landmarks = _landmarks()
    landmarks["confidence"] = 0.75
    unrelated = pd.DataFrame([
        {"session_time_ns": 1_000_000_007 + frame * 33_333_333,
         "frame_index": frame, "joint_index": joint,
         "x": 0.0, "y": 0.0, "z": 0.0, "confidence": 0.0}
        for frame in range(5) for joint in range(25) if joint not in JOINTS
    ])
    table = _compute(pd.concat([landmarks, unrelated], ignore_index=True))
    assert table.filter(like="valid_").all().all()
    np.testing.assert_allclose(table.filter(like="theta_"), 90.0, atol=1e-12)


def test_custom_confidence_threshold_applies_to_each_required_landmark() -> None:
    landmarks = _landmarks()
    landmarks.loc[landmarks["joint_index"] == 15, "confidence"] = 0.7
    table = _compute(landmarks, min_confidence=0.8)
    _assert_right_limb_valid(table)
    assert table["valid_shoulder_L"].all()
    assert not table["valid_elbow_L"].any()
    assert table["theta_elbow_flex_L"].isna().all()


def test_explicit_sim_teacher_keeps_existing_synthetic_values_and_flags() -> None:
    landmarks = _landmarks()
    landmarks = landmarks.loc[landmarks["joint_index"] == 15]
    table = landmarks_to_kinematics(landmarks, pose_model_id="sim_teacher_v1")
    times = landmarks["session_time_ns"].to_numpy() / 1e9
    np.testing.assert_allclose(table["theta_elbow_flex_L"], 90 + 15 * np.sin(times * 1.3))
    assert table.filter(like="valid_").all().all()
    assert (table["pose_model_id"] == "sim_teacher_v1").all()


def test_sparse_non_sim_pose_cli_retains_missing_data_and_source_bytes(tmp_path: Path) -> None:
    package = _write_pose_package(tmp_path / "session.mmsession")
    pose_dir = package / "processing" / "jobs" / "pose-recorded" / "pose" / "camera-fixture"
    pose_dir.mkdir(parents=True)
    landmarks = _landmarks()
    landmarks = landmarks.loc[landmarks["joint_index"] == 15]
    landmarks.to_parquet(pose_dir / "landmarks.parquet", index=False)
    (pose_dir / "model_card.json").write_text(json.dumps({"model_id": MODEL}), encoding="utf-8")
    (pose_dir.parents[1] / "job_manifest.json").write_text(
        json.dumps({"schemaId": "capture.analysis_job/1", "jobId": "pose-recorded",
                    "status": "completed", "command": "pose"}), encoding="utf-8"
    )
    originals = {
        p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in package.rglob("*") if p.is_file()
    }
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(str(ROOT / part) for part in (
        "libs/python/capture_analysis", "libs/python/capture_session",
        "libs/python/capture_protocol", "libs/python/capture_protocol/capture_protocol/generated",
    ))
    command = [sys.executable, str(ROOT / "tools/run_analysis.py"), "kinematics", str(package),
               "--pose-job", "pose-recorded", "--overwrite-job-id", "kin-receiving"]
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    job = package / "processing" / "jobs" / "kin-receiving"
    table = pd.read_parquet(job / "kinematics" / "kinematics.parquet")
    qc = json.loads((job / "kinematics" / "kinematics_qc.json").read_text(encoding="utf-8"))
    assert qc["provisional"] is False
    assert qc["poseModelIds"] == [MODEL]
    assert table["session_time_ns"].tolist() == landmarks["session_time_ns"].tolist()
    assert not table.filter(like="valid_").any().any()
    assert table.filter(regex="^(theta_|omega_|afr_)").isna().all().all()
    assert all(value == 0.0 for value in qc["detectionRates"].values())
    for relative, digest in originals.items():
        assert hashlib.sha256((package / relative).read_bytes()).hexdigest() == digest, relative
