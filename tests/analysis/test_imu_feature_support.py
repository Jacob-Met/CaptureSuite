# SPDX-License-Identifier: GPL-3.0-only
"""IMU support must survive actual MCAP analysis and selected table handoff."""

from __future__ import annotations

import json
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from capture_analysis.features.imu import extract_imu_features
from capture_analysis.types import GapInterval, GapMask, LoadedImu, StreamRef, TimeWindow
from test_phase_b_features import _write_emg_imu_package

ROOT = Path(__file__).resolve().parents[2]


def test_measurement_support_uses_complete_vectors_and_declared_gaps() -> None:
    times = np.arange(8, dtype=np.int64) * 10_000_000
    accel = np.tile([3.0, 4.0, 0.0], (8, 2, 1)).astype(np.float32)
    gyro = np.tile([0.0, 0.0, 2.0], (8, 2, 1)).astype(np.float32)
    # One missing sensor frame, independent invalid accel and gyro vectors,
    # and a declared gap. The intact sensor remains fully present outside it.
    accel[0, 1] = gyro[0, 1] = np.nan
    accel[1, 1] = [100.0, np.nan, 100.0]
    gyro[2, 1] = [0.0, np.inf, 2.0]
    loaded = LoadedImu(["pelvis", "ankle"], times, accel, gyro,
                       np.zeros((8, 2, 4), np.float32), "a.u.")
    ref = StreamRef("s", "frames", "imu", "imu.frame/1", 100, "a.u.")
    gap = GapInterval("s", "frames", "disconnect", 30_000_000, 30_000_000, True)
    mask = GapMask(ref, TimeWindow(0, 70_000_000), [gap])
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        df, meta, vf = extract_imu_features(
            loaded, mask, nominal_rate_hz=100, window_s=.08, hop_s=.08
        )
    row = df.iloc[0]
    assert vf == pytest.approx(7 / 8)
    assert row["window_frame_count"] == 8
    assert row["valid_fraction"] == pytest.approx(7 / 8)
    assert row["pelvis_acc_sample_count"] == row["pelvis_gyro_sample_count"] == 7
    assert row["ankle_acc_sample_count"] == row["ankle_gyro_sample_count"] == 5
    assert row["ankle_acc_valid_fraction"] == row["ankle_gyro_valid_fraction"] == 5 / 8
    assert row["ankle_acc_x_mean"] == 3.0  # incomplete vector's x=100 is excluded
    assert row["ankle_acc_z_mean"] == 0.0
    assert row["ankle_acc_mag_mean"] == 5.0
    assert row["ankle_gyro_mag_mean"] == 2.0
    assert set(df.columns) == {m["name"] for m in meta}


@pytest.mark.parametrize("absent", ["acc", "gyro", "both"])
def test_zero_support_retains_unknown_without_empty_slice_warning(absent: str) -> None:
    times = np.arange(4, dtype=np.int64) * 10_000_000
    accel = np.ones((4, 1, 3), dtype=np.float32)
    gyro = np.zeros((4, 1, 3), dtype=np.float32)
    if absent in ("acc", "both"):
        accel[:] = np.nan
    if absent in ("gyro", "both"):
        gyro[:] = np.nan
    loaded = LoadedImu(["sensor"], times, accel, gyro,
                       np.zeros((4, 1, 4), np.float32), "a.u.")
    ref = StreamRef("s", "frames", "imu", "imu.frame/1", 100, "a.u.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        df, _, _ = extract_imu_features(
            loaded, GapMask(ref, TimeWindow(0, 30_000_000)), nominal_rate_hz=100
        )
    row = df.iloc[0]
    for measurement in ("acc", "gyro"):
        missing = absent in (measurement, "both")
        assert row[f"sensor_{measurement}_sample_count"] == (0 if missing else 4)
        assert row[f"sensor_{measurement}_valid_fraction"] == (0 if missing else 1)
        assert pd.isna(row[f"sensor_{measurement}_mag_mean"]) == missing
    if absent == "acc":
        assert row["sensor_gyro_mag_mean"] == 0  # observed zero is valid, not unknown


def test_mcap_support_is_saved_and_exported_with_source_warning(tmp_path: Path) -> None:
    from capture_analysis import hash_sources_tree
    from capture_analysis.feature_table_export import export_feature_table, list_feature_tables

    package = _write_emg_imu_package(tmp_path / "partial.mmsession", second_sensor_frames=15)
    before = hash_sources_tree(package)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_analysis.py"), "features", str(package),
         "--overwrite-job-id", "support", "--strict-warnings"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "RuntimeWarning" not in proc.stderr
    job = package / "processing/jobs/support"
    manifest = json.loads((job / "job_manifest.json").read_text())
    assert manifest["status"] == "completed_with_warnings"
    assert any("IMU feature support incomplete" in w and "sternum acc" in w
               for w in manifest["warnings"])
    tables = list_feature_tables(job)["tables"]
    table = next(t for t in tables if "imu/" in t["relativePath"])
    frame = pd.read_parquet(job / table["relativePath"])
    assert frame["window_frame_count"].tolist() == [12, 12, 12, 12]
    assert frame["sternum_acc_sample_count"].tolist() == [12, 9, 3, 0]
    assert frame["sternum_gyro_valid_fraction"].tolist() == [1, .75, .25, 0]
    assert frame["pelvis_acc_valid_fraction"].tolist() == [1, 1, 1, 1]
    assert pd.isna(frame["sternum_acc_mag_mean"].iloc[-1])
    schema = json.loads((job / "features/_schema.json").read_text())
    assert schema["tables"][table["relativePath"]]["featureSchemaVersion"] == 2
    selected = ["t_mid_ns", "sternum_acc_mag_mean", "sternum_acc_sample_count",
                "sternum_acc_valid_fraction", "window_frame_count"]
    dest = tmp_path / "selected"
    result = export_feature_table(job, table["relativePath"], dest, columns=selected)
    assert result["source"]["jobStatus"] == "completed_with_warnings"
    for file in ("table.csv", "table.parquet"):
        data = pd.read_csv(dest / file) if file.endswith(".csv") else pd.read_parquet(dest / file)
        assert data.columns.tolist() == selected
        assert data["sternum_acc_valid_fraction"].tolist() == [1, .75, .25, 0]
        assert pd.isna(data["sternum_acc_mag_mean"].iloc[-1])
    exported_schema = json.loads((dest / "_schema.json").read_text())
    support_meta = next(c for c in exported_schema["tableMetadata"]["columns"]
                        if c["name"] == "sternum_acc_valid_fraction")
    assert support_meta["units"] == "1"
    assert "window_frame_count" in support_meta["description"]
    retained = json.loads((dest / "source/job_manifest.json").read_text())
    assert retained["warnings"] == manifest["warnings"]
    assert hash_sources_tree(package) == before
