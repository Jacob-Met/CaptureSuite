# SPDX-License-Identifier: GPL-3.0-only
"""Phase 5 D2 kinematics job — Tier A teacher labels from pose landmarks."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from capture_session.package_reader import ReviewSummary

from capture_analysis.kinematics.compute import detection_rate, landmarks_to_kinematics
from capture_analysis.kinematics.registry import validate_parquet_columns


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_job_dir(package_root: Path, job_id: str) -> Path:
    path = package_root / "processing" / "jobs" / job_id
    if not path.is_dir():
        raise FileNotFoundError(f"analysis job not found: {job_id} ({path})")
    return path


def _landmark_paths(pose_job_dir: Path) -> list[Path]:
    paths = sorted(pose_job_dir.glob("pose/*/landmarks.parquet"))
    if not paths:
        raise FileNotFoundError(
            f"no pose/*/landmarks.parquet under {pose_job_dir}"
        )
    return paths


def _read_model_id(pose_job_dir: Path, landmarks_path: Path) -> str:
    source_id = landmarks_path.parent.name
    card = pose_job_dir / "pose" / source_id / "model_card.json"
    if card.is_file():
        try:
            doc = json.loads(card.read_text(encoding="utf-8"))
            mid = doc.get("model_id")
            if isinstance(mid, str) and mid:
                return mid
        except json.JSONDecodeError:
            pass
    return "unknown_pose_model"


def run_kinematics_job(
    package_root: Path,
    work: Path,
    summary: ReviewSummary,
    *,
    pose_job_id: str,
    outputs: list[dict[str, Any]],
    warnings: list[str],
    imu_fusion: bool = False,
) -> dict[str, Any]:
    """Write kinematics/kinematics.parquet + kinematics_qc.json."""
    import pandas as pd

    _ = summary
    pose_dir = resolve_job_dir(package_root, pose_job_id)
    landmark_files = _landmark_paths(pose_dir)

    frames: list[Any] = []
    model_ids: set[str] = set()
    for lm_path in landmark_files:
        lm_df = pd.read_parquet(lm_path)
        model_id = _read_model_id(pose_dir, lm_path)
        model_ids.add(model_id)
        kin_part = landmarks_to_kinematics(
            lm_df,
            pose_model_id=model_id,
            teacher_source="video+imu" if imu_fusion else "video",
        )
        if not kin_part.empty:
            frames.append(kin_part)

    if not frames:
        raise RuntimeError("kinematics job: no frames produced from pose landmarks")

    kin_df = pd.concat(frames, ignore_index=True).sort_values("session_time_ns")
    missing = validate_parquet_columns(list(kin_df.columns))
    if missing:
        raise RuntimeError(f"kinematics.parquet missing registry columns: {missing}")

    kin_dir = work / "kinematics"
    kin_dir.mkdir(parents=True, exist_ok=True)
    kin_path = kin_dir / "kinematics.parquet"
    kin_df.to_parquet(kin_path, index=False)

    rates = detection_rate(kin_df)
    qc = {
        "schemaId": "capture.kinematics_qc/1",
        "poseJobId": pose_job_id,
        "poseModelIds": sorted(model_ids),
        "provisional": any(m.startswith("sim_") for m in model_ids),
        "frameCount": int(len(kin_df)),
        "detectionRates": rates,
        "imuFusion": {"applied": imu_fusion, "weights": None},
        "gapPolicy": "mask",
        "notes": (
            "Sim/fixture teacher when pose_model_id starts with sim_. "
            "Shoulder angles require hip landmarks on real teachers."
        ),
        "createdUtc": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    qc_path = kin_dir / "kinematics_qc.json"
    qc_path.write_text(json.dumps(qc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for rel, kind in (
        ("kinematics/kinematics.parquet", "kinematics_parquet"),
        ("kinematics/kinematics_qc.json", "kinematics_qc"),
    ):
        path = work / rel
        outputs.append(
            {
                "relativePath": rel,
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
                "kind": kind,
            }
        )

    return {
        "kinematicsRows": int(len(kin_df)),
        "poseJobId": pose_job_id,
        "poseModelIds": sorted(model_ids),
        "detectionRates": rates,
        "provisional": qc["provisional"],
    }
