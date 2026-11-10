# SPDX-License-Identifier: GPL-3.0-only
"""Imported sensor dropouts retain elapsed windows through real analysis jobs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from capture_analysis import JobParams, hash_sources_tree, run
from test_numeric_batch_pipeline import _batch, _write_mcap


def recording(dest: Path) -> Path:
    dest.mkdir()
    (dest / "manifest.json").write_text(
        json.dumps({"sessionId": "numeric.dropout", "state": "sealed", "sourceIds": ["lsl"]})
    )
    stream = dest / "sources/lsl/streams/signal"
    path = stream / "segments/000000.mcap"
    _write_mcap(
        path,
        [
            (
                100_000_000,
                _batch(
                    channel_count=1,
                    channel_names=["signal"],
                    samples=[1.0, 2.0, 9.0, 10.0],
                    device_time_ns=[0, 500_000_000, 3_000_000_000, 3_500_000_000],
                ),
            )
        ],
    )
    (stream / "stream.json").write_text(
        json.dumps(
            {
                "sourceId": "lsl",
                "streamId": "signal",
                "modality": "eeg",
                "dataSchemaId": "generic.numeric_batch/1",
                "nominalRateHz": 2.0,
                "units": "V",
                "dimensions": [1],
            }
        )
    )
    health = dest / "sources/lsl/health"
    health.mkdir()
    (health / "gaps.jsonl").write_text(
        json.dumps(
            {
                "sourceId": "lsl",
                "streamId": "signal",
                "cause": "DISCONNECT",
                "startSessionTimeNs": 1_100_000_000,
                "endSessionTimeNs": 3_099_999_999,
                "closed": True,
            }
        )
        + "\n"
    )
    (dest / "integrity.json").write_text(
        json.dumps(
            {
                "schemaVersion": "1",
                "files": [
                    {
                        "path": path.relative_to(dest).as_posix(),
                        "sizeBytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "endSessionTimeNs": 4_100_000_000,
                    }
                ],
            }
        )
    )
    return dest


@pytest.mark.parametrize("policy", ["mask", "split"])
def test_real_numeric_job_keeps_distant_episodes_separate(tmp_path: Path, policy: str) -> None:
    package = recording(tmp_path / "sensor.mmsession")
    before = hash_sources_tree(package)
    result = run(package, JobParams(command="all", gap_policy=policy, overwrite_job_id=policy))
    table = next((result.job_dir / "features/numeric").rglob("*.parquet"))
    rows = pd.read_parquet(table)
    assert (rows["t_end_ns"] - rows["t_start_ns"]).eq(1_000_000_000).all()
    # Old mask combined 2V and 9V across the disconnect into a 3-second 5.5V row.
    assert 5.5 not in rows["signal_mean"].tolist()
    if policy == "mask":
        assert rows["t_start_ns"].tolist() == [
            100_000_000,
            600_000_000,
            2_600_000_000,
            3_100_000_000,
        ]
        assert rows["signal_mean"].tolist() == [1.5, 2.0, 9.0, 9.5]
        assert rows["sample_count"].tolist() == [2, 1, 1, 2]
        assert rows["valid_fraction"].tolist() == [1.0, 0.5, 0.5, 1.0]
    else:
        assert rows["t_start_ns"].tolist() == [100_000_000, 3_100_000_000]
        assert rows["signal_mean"].tolist() == [1.5, 9.5]
        assert rows["sample_count"].tolist() == [2, 2]
        assert rows["valid_fraction"].tolist() == [1.0, 1.0]
    assert rows["expected_sample_count"].eq(2).all()
    assert rows["gap_fraction"].equals(1.0 - rows["valid_fraction"])
    manifest = json.loads((result.job_dir / "job_manifest.json").read_text())
    assert manifest["gapSummary"]["validFractionBySource"]["lsl"] == 0.5
    schema = json.loads((result.job_dir / "features/_schema.json").read_text())
    assert "numeric.basic.v2" in json.dumps(schema)
    assert hash_sources_tree(package) == before


def test_numeric_declared_empty_dropout_stops_fail_job(tmp_path: Path) -> None:
    package = recording(tmp_path / "sensor.mmsession")
    before = hash_sources_tree(package)
    with pytest.raises(RuntimeError, match="gap_policy=fail"):
        run(package, JobParams(command="features", gap_policy="fail", overwrite_job_id="fail"))
    assert not list((package / "processing").rglob("*.parquet"))
    assert hash_sources_tree(package) == before
