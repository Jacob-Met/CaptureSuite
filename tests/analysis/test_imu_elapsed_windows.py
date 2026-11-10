# SPDX-License-Identifier: GPL-3.0-only
"""IMU analysis must not compress a disconnect into one short feature window."""

import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]


def make_package(path):
    helper = runpy.run_path(str(ROOT / "tests/analysis/test_phase_b_features.py"))
    return helper["_write_emg_imu_package"](path)


def run_features(package, policy="mask"):
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_analysis.py"), "features", str(package),
         "--sources", "sim.imu.upper", "--start-ns", "0", "--end-ns", "4000000000",
         "--gap-policy", policy, "--overwrite-job-id", "imu-elapsed"],
        env=os.environ.copy(), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return pd.read_parquet(
        package / "processing/jobs/imu-elapsed/features/imu/sim.imu.upper/windows.parquet"
    )


@pytest.mark.parametrize("policy", ["mask", "split"])
def test_encoded_imu_disconnected_episodes_remain_separate(tmp_path, policy):
    from capture_analysis import hash_sources_tree
    from capture_protocol.generated.capture.v1.data import imu_frame_pb2
    from mcap.writer import Writer

    package = make_package(tmp_path / "imu.mmsession")
    segment = package / "sources/sim.imu.upper/streams/sim.imu.upper.frames/segments/000000.mcap"
    with segment.open("wb") as fh:
        writer = Writer(fh)
        writer.start(profile="", library="imu-elapsed-regression")
        schema = writer.register_schema(name="imu.frame/1", encoding="protobuf", data=b"")
        channel = writer.register_channel(
            topic="imu", message_encoding="protobuf", schema_id=schema
        )
        for i in range(12):
            timestamp = round((i / 60 if i < 6 else 3 + (i - 6) / 60) * 1e9)
            frame = imu_frame_pb2.ImuFrame()
            frame.timing.session_time_ns = timestamp
            frame.timing.sequence_number = i
            frame.frame_index = i
            sensor = frame.sensors.add()
            sensor.sensor_id = "pelvis"
            sensor.accel_z = 1 if i < 6 else 9
            sensor.qw = 1
            writer.add_message(channel_id=channel, log_time=timestamp,
                               publish_time=timestamp, data=frame.SerializeToString())
        writer.finish()
    health = package / "sources/sim.imu.upper/health"
    health.mkdir(exist_ok=True)
    (health / "gaps.jsonl").write_text(json.dumps({
        "sourceId": "sim.imu.upper", "streamId": "sim.imu.upper.frames",
        "cause": "disconnect", "startSessionTimeNs": 100_000_000,
        "endSessionTimeNs": 2_999_999_999, "closed": True,
    }) + "\n")
    before = hash_sources_tree(package)
    table = run_features(package, policy)
    assert hash_sources_tree(package) == before
    assert list(table.pelvis_acc_mag_mean) == [1, 9]
    assert list(table.pelvis_acc_mag_std) == [0, 0]
    assert list(table.window_frame_count) == [6, 6]
    assert (table.t_end_ns - table.t_start_ns <= 200_000_000).all()
    assert not table.t_mid_ns.between(100_000_000, 2_999_999_999).any()
    assert (table.expected_frame_count >= table.window_frame_count).all()


def test_continuous_imu_retains_standard_windows(tmp_path):
    table = run_features(make_package(tmp_path / "continuous.mmsession"))
    assert len(table) == 4
    assert list(table.t_start_ns) == [0, 100_000_000, 200_000_000, 300_000_000]
    assert (table.t_end_ns - table.t_start_ns == 200_000_000).all()
    assert list(table.window_frame_count) == [12] * 4
    np.testing.assert_allclose(table.pelvis_acc_mag_mean, 9.81, rtol=1e-6)
