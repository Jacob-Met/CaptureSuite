# SPDX-License-Identifier: GPL-3.0-only
"""Recorded dropouts must not turn distinct contractions into one feature row."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from capture_analysis import JobParams, hash_sources_tree, run

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "sim.emg.main"
STREAM = "sim.emg.main.batch"


def write_dropout_recording(dest: Path, *, second_start_ns: int = 1_000_000_000) -> Path:
    """Two measured-value spans in genuine protobuf MCAP; no hardware claim."""
    from capture_protocol.generated.capture.v1.data.emg_batch_pb2 import EmgBatch
    from mcap.writer import Writer

    fixture = ROOT / "tests/fixtures/mini_session"
    dest.mkdir()
    shutil.copy(fixture / "manifest.json", dest / "manifest.json")
    manifest = json.loads((dest / "manifest.json").read_text())
    manifest["sourceIds"] = [SOURCE]
    (dest / "manifest.json").write_text(json.dumps(manifest))
    shutil.copytree(fixture / "sources" / SOURCE, dest / "sources" / SOURCE)
    stream_dir = dest / "sources" / SOURCE / "streams" / STREAM
    descriptor = json.loads((stream_dir / "stream.json").read_text())
    descriptor.update(nominalRateHz=1000, dimensions=[1])
    (stream_dir / "stream.json").write_text(json.dumps(descriptor))
    path = stream_dir / "segments/000000.mcap"
    with path.open("wb") as fh:
        writer = Writer(fh)
        writer.start()
        schema = writer.register_schema(name="emg.batch/1", encoding="protobuf", data=b"")
        channel = writer.register_channel(
            topic="emg", message_encoding="protobuf", schema_id=schema
        )
        for sequence, (start, level) in enumerate([(0, 1.0), (second_start_ns, 9.0)]):
            message = EmgBatch()
            message.timing.session_time_ns = start
            message.timing.sequence_number = sequence
            message.first_sample_index = start // 1_000_000
            message.sample_count = 50
            message.channel_ids.append("forearm")
            message.samples_f32_le = np.full(50, level, dtype="<f4").tobytes()
            writer.add_message(
                channel_id=channel,
                log_time=start,
                publish_time=start,
                data=message.SerializeToString(),
            )
        writer.finish()
    gap = {
        "sourceId": SOURCE,
        "streamId": STREAM,
        "cause": "DISCONNECT",
        "startSessionTimeNs": 50_000_000,
        "endSessionTimeNs": second_start_ns - 1,
        "closed": True,
    }
    (dest / "sources" / SOURCE / "health/gaps.jsonl").write_text(json.dumps(gap) + "\n")
    (dest / "integrity.json").write_text(
        json.dumps(
            {
                "schemaVersion": "1",
                "files": [
                    {
                        "path": path.relative_to(dest).as_posix(),
                        "sizeBytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "endSessionTimeNs": second_start_ns + 50_000_000,
                    }
                ],
            }
        )
    )
    return dest


def test_mask_uses_elapsed_time_and_reports_missing_samples(tmp_path: Path) -> None:
    package = write_dropout_recording(tmp_path / "recording.mmsession")
    before = hash_sources_tree(package)
    result = run(package, JobParams(command="features", overwrite_job_id="elapsed-mask"))
    table = result.job_dir / "features/emg" / SOURCE / "windows.parquet"
    rows = pd.read_parquet(table)
    # The old result was one RMS=sqrt(41) row at 0.5245 s, with validity 1.
    assert rows["t_start_ns"].tolist() == [0, 950_000_000]
    assert rows["t_end_ns"].tolist() == [100_000_000, 1_050_000_000]
    assert rows["forearm_rms"].tolist() == [1.0, 9.0]
    assert rows["forearm_mav"].tolist() == [1.0, 9.0]
    assert rows["sample_count"].tolist() == [50, 50]
    assert rows["valid_sample_count"].tolist() == [50, 50]
    assert rows["expected_sample_count"].tolist() == [100, 100]
    assert rows["valid_fraction"].tolist() == [0.5, 0.5]
    schema = json.loads((result.job_dir / "features/_schema.json").read_text())
    assert "emg.windowed.v2" in json.dumps(schema)
    manifest = json.loads((result.job_dir / "job_manifest.json").read_text())
    assert manifest["gapSummary"]["maskedNs"] is None
    assert manifest["gapSummary"]["validFractionBySource"][SOURCE] == pytest.approx(100 / 1050)
    assert hash_sources_tree(package) == before


def test_split_restarts_after_dropout_and_names_short_span(tmp_path: Path) -> None:
    package = write_dropout_recording(tmp_path / "split.mmsession")
    result = run(
        package,
        JobParams(command="features", gap_policy="split", overwrite_job_id="elapsed-split"),
    )
    rows = pd.read_parquet(result.job_dir / "features/emg" / SOURCE / "windows.parquet")
    assert rows["t_start_ns"].tolist() == [0, 1_000_000_000]
    assert rows["t_end_ns"].tolist() == [50_000_000, 1_050_000_000]
    assert rows["forearm_rms"].tolist() == [1.0, 9.0]
    assert rows["expected_sample_count"].tolist() == [50, 50]
    assert rows["valid_fraction"].tolist() == [1.0, 1.0]


def test_fail_cli_rejects_declared_dropout_without_a_stored_sample(tmp_path: Path) -> None:
    package = write_dropout_recording(tmp_path / "fail.mmsession")
    before = hash_sources_tree(package)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/run_analysis.py"),
            "features",
            str(package),
            "--gap-policy",
            "fail",
            "--overwrite-job-id",
            "must-fail",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "gap_policy=fail" in result.stderr
    assert not list((package / "processing").rglob("*.parquet"))
    assert hash_sources_tree(package) == before


def test_day_long_missing_interval_does_not_materialize_empty_windows(tmp_path: Path) -> None:
    package = write_dropout_recording(
        tmp_path / "long-gap.mmsession", second_start_ns=86_400_000_000_000
    )
    result = run(package, JobParams(command="features", overwrite_job_id="long-gap"))
    rows = pd.read_parquet(result.job_dir / "features/emg" / SOURCE / "windows.parquet")
    assert len(rows) == 2
    assert rows["forearm_rms"].tolist() == [1.0, 9.0]
    assert (rows["t_end_ns"] - rows["t_start_ns"]).eq(100_000_000).all()


@pytest.mark.parametrize("policy", ["mask", "split", "fail"])
def test_continuous_signal_keeps_original_window_values(policy: str) -> None:
    from capture_analysis.features.emg import extract_emg_features
    from capture_analysis.types import GapMask, LoadedEmg, StreamRef, TimeWindow

    times = np.arange(300, dtype=np.int64) * 1_000_000
    values = np.sin(2 * np.pi * np.arange(300) / 25).reshape(1, -1)
    stream = StreamRef("sensor", "emg", "emg", "emg.batch/1", 1000, "mV")
    rows, _, coverage = extract_emg_features(
        LoadedEmg(["c"], times, values, 1000, "mV"),
        GapMask(stream, TimeWindow(0, 300_000_000), [], policy),
    )
    assert rows["t_start_ns"].tolist() == [0, 50_000_000, 100_000_000, 150_000_000, 200_000_000]
    assert np.allclose(rows["c_rms"], np.sqrt(0.5))
    assert rows["valid_fraction"].eq(1.0).all()
    assert coverage == 1.0


def test_clean_137hz_signal_is_fully_covered_with_variable_row_counts() -> None:
    from capture_analysis.features.emg import extract_emg_features
    from capture_analysis.types import GapMask, LoadedEmg, StreamRef, TimeWindow

    rate = 137.0
    period = round(1e9 / rate)
    times = 123_456_789 + np.arange(1370, dtype=np.int64) * period
    stream = StreamRef("sensor", "emg", "emg", "emg.batch/1", rate, "mV")
    rows, _, coverage = extract_emg_features(
        LoadedEmg(["c"], times, np.ones((1, len(times))), rate, "mV"),
        GapMask(stream, TimeWindow(int(times[0]), int(times[-1]) + period)),
    )
    assert set(rows["sample_count"]) == {13, 14}
    assert (rows["sample_count"] == rows["expected_sample_count"]).all()
    assert rows["valid_fraction"].eq(1.0).all()
    assert coverage == 1.0
