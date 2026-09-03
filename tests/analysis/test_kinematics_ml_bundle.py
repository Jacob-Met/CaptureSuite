# SPDX-License-Identifier: GPL-3.0-only
"""Phase 5 kinematics + Phase 6 ML bundle end-to-end on sim fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.analysis.test_pose_job import _write_pose_package

ROOT = Path(__file__).resolve().parents[2]

pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("mcap")


def _write_combined_package(dest: Path) -> Path:
    """Pose timing + real EMG MCAP for feature alignment."""
    pkg = _write_pose_package(dest)
    from tests.analysis.test_phase_b_features import _write_emg_imu_package

    emg_pkg = _write_emg_imu_package(dest.parent / "_emg_tmp")
    import shutil

    for src in ("sim.emg.main", "sim.imu.upper"):
        shutil.copytree(emg_pkg / "sources" / src, pkg / "sources" / src, dirs_exist_ok=True)
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    ids = set(manifest.get("sourceIds") or [])
    ids.update(["sim.emg.main", "sim.imu.upper"])
    manifest["sourceIds"] = sorted(ids)
    (pkg / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(emg_pkg, ignore_errors=True)
    return pkg


def _write_radar_energy_features_job(pkg: Path, job_id: str = "feat-radar") -> str:
    """Seed a features job with radar motion-energy parquet (sim RD stack proxy)."""
    import pandas as pd

    job = pkg / "processing" / "jobs" / job_id
    feat = job / "features" / "radar" / "sim.radar.1"
    feat.mkdir(parents=True, exist_ok=True)
    t = [int(i * 1e9 / 20.0) for i in range(20)]
    df = pd.DataFrame(
        {
            "t_ns": t,
            "energy": [float(100 + 10 * (i % 5)) for i in range(20)],
            "peak_range_bin": [i % 8 for i in range(20)],
            "valid": [1] * 20,
        }
    )
    df.to_parquet(feat / "frame_features.parquet", index=False)
    (job / "job_manifest.json").write_text(
        json.dumps(
            {
                "schemaId": "capture.analysis_job/1",
                "jobId": job_id,
                "status": "completed",
                "command": "features",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return job_id


def test_radar_to_teacher_ml_bundle(tmp_path: Path) -> None:
    """Phase 6 gate: radar motion energy → kinematics teacher windows."""
    from capture_analysis.jobs import JobParams, run

    pkg = _write_pose_package(tmp_path / "radar_ml")
    feat_id = _write_radar_energy_features_job(pkg)
    pose = run(pkg, JobParams(command="pose", overwrite_job_id="pose-r"))
    kin = run(
        pkg,
        JobParams(
            command="kinematics",
            overwrite_job_id="kin-r",
            extra={"pose_job_id": pose.job_id},
        ),
    )
    bundle = run(
        pkg,
        JobParams(
            command="ml_bundle",
            overwrite_job_id="bundle-r",
            extra={
                "kinematics_job_id": kin.job_id,
                "features_job_id": feat_id,
                "window_sec": 0.1,
                "hop_sec": 0.05,
            },
        ),
    )
    assert bundle.status in ("completed", "completed_with_warnings")
    doc = json.loads(
        (bundle.job_dir / "ml_bundle" / "manifest.json").read_text(encoding="utf-8")
    )
    assert doc["schemaId"] == "capture.ml_bundle/1"
    streams = doc["analysisGrids"][0]["sourceStreams"]
    assert any("radar" in s or s == "sim.radar.1" for s in streams) or "sim.radar.1" in streams
    assert "kinematics.teacher" in streams

    import jsonschema

    schema_path = (
        ROOT / "schemas" / "ml_bundle" / "ml_bundle.manifest.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)


def test_kinematics_from_pose_job(tmp_path: Path) -> None:
    from capture_analysis.jobs import JobParams, run
    from capture_analysis.kinematics.registry import validate_parquet_columns

    pkg = _write_pose_package(tmp_path / "kin_pkg")
    pose = run(pkg, JobParams(command="pose", overwrite_job_id="pose-fixture"))
    kin = run(
        pkg,
        JobParams(
            command="kinematics",
            overwrite_job_id="kin-fixture",
            extra={"pose_job_id": pose.job_id},
        ),
    )
    assert kin.status in ("completed", "completed_with_warnings")
    kin_path = kin.job_dir / "kinematics" / "kinematics.parquet"
    qc_path = kin.job_dir / "kinematics" / "kinematics_qc.json"
    assert kin_path.is_file()
    assert qc_path.is_file()

    import pandas as pd

    df = pd.read_parquet(kin_path)
    missing = validate_parquet_columns(list(df.columns))
    assert missing == []
    assert len(df) == 10
    assert df["theta_elbow_flex_L"].notna().all()
    qc = json.loads(qc_path.read_text(encoding="utf-8"))
    assert qc["provisional"] is True


def test_ml_bundle_end_to_end(tmp_path: Path) -> None:
    from capture_analysis.jobs import JobParams, run

    pkg = _write_combined_package(tmp_path / "ml_pkg")
    feat = run(pkg, JobParams(command="features", overwrite_job_id="feat-fixture"))
    pose = run(pkg, JobParams(command="pose", overwrite_job_id="pose-fixture"))
    kin = run(
        pkg,
        JobParams(
            command="kinematics",
            overwrite_job_id="kin-fixture",
            extra={"pose_job_id": pose.job_id},
        ),
    )
    bundle = run(
        pkg,
        JobParams(
            command="ml_bundle",
            overwrite_job_id="bundle-fixture",
            extra={
                "kinematics_job_id": kin.job_id,
                "features_job_id": feat.job_id,
                "window_sec": 0.05,
                "hop_sec": 0.02,
            },
        ),
    )
    assert bundle.status in ("completed", "completed_with_warnings")
    man = bundle.job_dir / "ml_bundle" / "manifest.json"
    win = bundle.job_dir / "ml_bundle" / "windows.parquet"
    assert man.is_file()
    assert win.is_file()

    doc = json.loads(man.read_text(encoding="utf-8"))
    assert doc["schemaId"] == "capture.ml_bundle/1"
    assert doc["sourceJobIds"]["kinematics"] == kin.job_id
    assert doc["sourceJobIds"]["features"] == feat.job_id

    import pandas as pd

    windows = pd.read_parquet(win)
    assert len(windows) >= 1
    assert "motion_energy" in windows.columns
    assert "theta_elbow_flex_L" in windows.columns


def test_eval_from_ml_bundle(tmp_path: Path) -> None:
    from capture_analysis.jobs import JobParams, run

    pkg = _write_combined_package(tmp_path / "eval_pkg")
    feat = run(pkg, JobParams(command="features", overwrite_job_id="feat-e"))
    pose = run(pkg, JobParams(command="pose", overwrite_job_id="pose-e"))
    kin = run(
        pkg,
        JobParams(
            command="kinematics",
            overwrite_job_id="kin-e",
            extra={"pose_job_id": pose.job_id},
        ),
    )
    bundle = run(
        pkg,
        JobParams(
            command="ml_bundle",
            overwrite_job_id="bundle-e",
            extra={
                "kinematics_job_id": kin.job_id,
                "features_job_id": feat.job_id,
                "window_sec": 0.05,
                "hop_sec": 0.02,
            },
        ),
    )
    ev = run(
        pkg,
        JobParams(
            command="eval",
            overwrite_job_id="eval-e",
            extra={"ml_bundle_job_id": bundle.job_id},
        ),
    )
    assert ev.status in ("completed", "completed_with_warnings")
    report = ev.job_dir / "eval" / "eval_report.json"
    preds = ev.job_dir / "eval" / "predictions.parquet"
    assert report.is_file()
    assert preds.is_file()
    doc = json.loads(report.read_text(encoding="utf-8"))
    assert doc["schemaId"] == "capture.eval_report/1"
    assert doc["windowCount"] >= 1


def test_run_analysis_cli_kinematics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    pkg = _write_pose_package(tmp_path / "cli_kin")
    monkeypatch.chdir(ROOT)
    sys.path[:0] = [
        str(ROOT / "libs" / "python" / "capture_analysis"),
        str(ROOT / "libs" / "python" / "capture_session"),
        str(ROOT / "libs" / "python" / "capture_protocol"),
    ]
    from tools.run_analysis import main

    assert main(["pose", str(pkg), "--overwrite-job-id", "p1"]) == 0
    assert main(["kinematics", str(pkg), "--pose-job", "p1", "--overwrite-job-id", "k1"]) == 0
