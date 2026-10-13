# SPDX-License-Identifier: GPL-3.0-only
"""Receive standards-compliant saved dashboard observations through the actual pipeline."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from capture_analysis import JobParams, hash_sources_tree, pipeline, run
from capture_analysis.types import StreamRef, TimeWindow
from test_video_qc_intervals import write_video_package


def _strict_load(text):
    def reject(token):
        raise ValueError(f"non-JSON numeric token: {token}")

    return json.loads(text, parse_constant=reject)


@pytest.mark.parametrize(
    "values",
    [
        [0.0, -0.0, 2.5],
        [10.0, float("nan"), 10.0],
        [1.0, float("inf"), 2.0],
        [1.0, -float("inf"), 2.0],
        [float("nan"), float("inf"), -float("inf")],
        [1e100, np.finfo(float).tiny, -3.0],
        np.array([1.25, float("nan"), -2.0], dtype=np.float32),
        np.array([1.0, 9.0, float("inf"), 8.0, 3.0, 7.0])[::2],
    ],
)
def test_pipeline_retains_positions_and_plotted_arrays_in_strict_json(
    tmp_path, monkeypatch, values,
):
    y = np.asarray(values)
    timestamps = np.array([2**60, 2**60 + 100, 2**60 + 200], dtype=np.int64)
    original_y, original_t = y.tobytes(), timestamps.tobytes()
    source = StreamRef("source.分析", "frames", "video", "test", 1.0, "FPS")
    row = {"label": "Observed naïve <series>", "t_ns": timestamps, "y": y, "color": "#888888"}
    plotted = []
    original_plot = pipeline.plot_sync_dashboard

    def plot(*args, **kwargs):
        plotted.append(kwargs["series"][0])
        return original_plot(*args, **kwargs)

    def handler(ref, mask, ctx):
        ctx.sync_series.append(row)

    monkeypatch.setattr(pipeline, "discover_streams", lambda root: [source])
    monkeypatch.setattr(pipeline, "plot_sync_dashboard", plot)
    registry = SimpleNamespace(
        stream_handler_for=lambda ref: handler, manifest_version="receiving/1",
    )
    outputs = []
    pipeline.run_features_and_plots(
        tmp_path, tmp_path / "output", SimpleNamespace(gaps=[], session_id="session.分析"),
        TimeWindow(int(timestamps[0]), int(timestamps[-1])),
        gap_policy="mask", max_ram_bytes=1_000_000, sources_filter=[],
        do_features=False, do_plots=True, outputs=outputs, warnings=[], feature_tables=[],
        registry=registry,
    )
    path = tmp_path / "output/figures/sync_dashboard_series.json"
    doc = _strict_load(path.read_text(encoding="utf-8"))
    assert doc["schemaId"] == "capture.sync_dashboard_series/2"
    saved = doc["series"][0]
    assert saved["t_ns"] == timestamps.tolist()
    assert all(type(value) is int for value in saved["t_ns"])
    assert saved["label"] == row["label"] and saved["color"] == row["color"]
    assert len(saved["y"]) == len(y)
    for actual, expected in zip(saved["y"], y, strict=True):
        if np.isfinite(expected):
            assert type(actual) is float and actual == float(expected)
            if expected == 0:
                assert np.signbit(actual) == np.signbit(expected)
        else:
            assert actual is None
    restored = np.asarray(saved["y"], dtype=np.float64)
    np.testing.assert_array_equal(np.isnan(restored), ~np.isfinite(y))
    np.testing.assert_array_equal(restored[np.isfinite(y)], y[np.isfinite(y)])
    assert plotted[0] is row and plotted[0]["y"] is y and plotted[0]["t_ns"] is timestamps
    assert y.tobytes() == original_y and timestamps.tobytes() == original_t
    item = next(item for item in outputs if item["kind"] == "sync_series")
    assert item["bytes"] == path.stat().st_size
    assert item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("version", [1, 2])
def test_existing_numpy_reader_keeps_legacy_and_null_missing_points(version):
    missing = "NaN" if version == 1 else "null"
    text = (
        '{"schemaId":"capture.sync_dashboard_series/' + str(version)
        + '","series":[{"y":[10,' + missing + ',10]}]}'
    )
    doc = json.loads(text)
    restored = np.asarray(doc["series"][0]["y"], dtype=np.float64)
    np.testing.assert_allclose(restored, [10.0, np.nan, 10.0], equal_nan=True)


@pytest.mark.parametrize("command", ["plots", "all"])
def test_real_mcap_job_keeps_masked_frame_and_raw_bytes_in_json(tmp_path, command):
    package = write_video_package(tmp_path / "video.mmsession")
    before = hash_sources_tree(package)
    result = run(package, JobParams(command=command, overwrite_job_id="strict-series"))
    assert result.status in ("completed", "completed_with_warnings")
    assert hash_sources_tree(package) == before
    path = result.job_dir / "figures/sync_dashboard_series.json"
    doc = _strict_load(path.read_text(encoding="utf-8"))
    assert doc["schemaId"] == "capture.sync_dashboard_series/2"
    row = doc["series"][0]
    assert row["t_ns"] == [100_000_000, 2_100_000_000, 2_200_000_000]
    assert row["y"] == [10.0, None, 10.0]
    table = pd.read_parquet(result.job_dir / "features/video/sim.video/timing_qc.parquet")
    np.testing.assert_allclose(table.fps_inst, [10.0, np.nan, 10.0], equal_nan=True)
    assert table.valid.tolist() == [1, 0, 1]
    item = next(item for item in result.manifest["outputs"] if item["kind"] == "sync_series")
    assert item["bytes"] == path.stat().st_size
    assert item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
