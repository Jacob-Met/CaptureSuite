# SPDX-License-Identifier: GPL-3.0-only
"""Exercise exported signal figures with genuine recorded MCAP and gap ledgers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from capture_analysis.pipeline import run_features_and_plots
from capture_analysis.plots.modality import plot_emg_channels, plot_series
from capture_analysis.plots.style import save_fig
from capture_analysis.types import GapInterval, LoadedEmg, TimeWindow
from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
from capture_session.package_reader import load_review_summary
from mcap.writer import Writer

SECOND = 1_000_000_000


def recorded_package(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "sessionId": "signal-plot-recording",
                "state": "finalized",
            }
        )
    )
    for source in ("interrupted", "healthy"):
        stream = root / "sources" / source / "streams" / "signal"
        (stream / "segments").mkdir(parents=True)
        (stream / "stream.json").write_text(
            json.dumps(
                {
                    "sourceId": source,
                    "streamId": "signal",
                    "modality": "numeric",
                    "dataSchemaId": "generic.numeric_batch/1",
                    "nominalRateHz": 1,
                    "units": "V",
                    "dimensions": [1],
                }
            )
        )
        with (stream / "segments" / "000000.mcap").open("wb") as fh:
            writer = Writer(fh)
            writer.start()
            schema = writer.register_schema("generic.numeric_batch/1", "protobuf", b"")
            channel = writer.register_channel(
                f"{source}/signal/generic.numeric_batch/1",
                "protobuf",
                schema,
            )
            for t, value in [(10, 1), (11, 2), (14, 8), (15, 9)]:
                message = numeric_batch_pb2.NumericBatch(
                    channel_count=1,
                    channel_names=["force"],
                    dtype="float64",
                    units="V",
                    samples=[value],
                    device_time_ns=[t * SECOND],
                )
                writer.add_message(channel, t * SECOND, message.SerializeToString(), t * SECOND)
            writer.finish()
    health = root / "sources" / "interrupted" / "health"
    health.mkdir()
    (health / "gaps.jsonl").write_text(
        json.dumps(
            {
                "sourceId": "interrupted",
                "streamId": "signal",
                "cause": "DISCONNECT",
                "startSessionTimeNs": str(12 * SECOND),
                "endSessionTimeNs": str(13 * SECOND),
                "closed": True,
            }
        )
        + "\n"
    )
    return root


def captures(snapshot):
    def save(fig, path):
        snapshot[Path(path).name] = [
            {
                "lines": [
                    (line.get_xdata().copy(), line.get_ydata().copy()) for line in ax.get_lines()
                ],
                "bands": len(ax.patches),
                "label": ax.get_ylabel(),
                "xlabel": ax.get_xlabel(),
            }
            for ax in fig.axes
        ]
        save_fig(fig, path)

    return save


def edges(axis):
    result = []
    for x, y in axis["lines"]:
        for index in range(1, len(x)):
            if np.isfinite(y[index - 1 : index + 1]).all():
                result.append((float(x[index - 1]), float(x[index])))
    return result


def test_recorded_gap_breaks_only_affected_static_dashboard_lane(tmp_path):
    package = recorded_package(tmp_path / "recording.mmsession")
    before = {
        p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (package / "sources").rglob("*")
        if p.is_file()
    }
    snapshots = {}
    work = package / "processing" / "jobs" / "plots"
    warnings, outputs = [], []
    with (
        patch("capture_analysis.plots.modality.save_fig", captures(snapshots)),
        patch("capture_analysis.plots.sync_dashboard.save_fig", captures(snapshots)),
    ):
        run_features_and_plots(
            package,
            work,
            load_review_summary(package),
            TimeWindow(10 * SECOND, 15 * SECOND),
            gap_policy="mask",
            max_ram_bytes=16 * 1024**2,
            sources_filter=[],
            do_features=False,
            do_plots=True,
            outputs=outputs,
            warnings=warnings,
            feature_tables=[],
        )
    assert warnings == []
    dashboard = snapshots["sync_dashboard.png"]
    interrupted = next(ax for ax in dashboard if "interrupted" in ax["label"])
    healthy = next(ax for ax in dashboard if "healthy" in ax["label"])
    assert interrupted["bands"] == 1
    assert healthy["bands"] == 0
    assert (11.0, 14.0) not in edges(interrupted)
    assert (11.0, 14.0) in edges(healthy)
    assert edges(interrupted) == [(10.0, 11.0), (14.0, 15.0)]
    assert before == {
        p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (package / "sources").rglob("*")
        if p.is_file()
    }
    assert all((work / output["relativePath"]).is_file() for output in outputs)


def test_emg_export_uses_recorded_session_seconds_and_gap_break(tmp_path):
    snapshots = {}
    loaded = LoadedEmg(
        ["channel"],
        np.array([10, 11, 14, 15]) * SECOND,
        np.array([[1.0, 2.0, 8.0, 9.0]]),
        1.0,
        "mV",
    )
    gap = GapInterval("emg", "raw", "DISCONNECT", 12 * SECOND, 13 * SECOND, True)
    with patch("capture_analysis.plots.modality.save_fig", captures(snapshots)):
        plot_emg_channels(
            tmp_path / "emg.png", loaded, window=TimeWindow(10 * SECOND, 15 * SECOND), gaps=[gap]
        )
    assert edges(snapshots["emg.png"][0]) == [(10.0, 11.0), (14.0, 15.0)]


@pytest.mark.parametrize("end", [12 * SECOND, None])
def test_samples_inside_closed_and_open_gap_are_not_drawn(tmp_path, end):
    snapshots = {}
    with patch("capture_analysis.plots.modality.save_fig", captures(snapshots)):
        plot_series(
            tmp_path / "series.png",
            np.arange(10, 16) * SECOND,
            np.arange(6.0),
            window=TimeWindow(10 * SECOND, 15 * SECOND),
            gaps=[GapInterval("source", "stream", "DISCONNECT", 12 * SECOND, end, end is not None)],
            ylabel="V",
            title="Recorded samples",
        )
    axis = snapshots["series.png"][0]
    drawn = {
        float(xi) for x, y in axis["lines"] for xi, yi in zip(x, y, strict=True) if np.isfinite(yi)
    }
    assert 12.0 not in drawn
    assert 10.0 in drawn and 11.0 in drawn
    assert (13.0 in drawn) == (end is not None)


def test_display_thinning_keeps_narrow_gap_and_missing_value_breaks(tmp_path):
    snapshots = {}
    times = np.arange(40005, dtype=np.int64) * 1_000_000
    values = np.ones(times.size)
    values[10001] = np.nan
    gap = GapInterval("source", "stream", "DISCONNECT", 20001_000_000, 20001_000_000, True)
    with patch("capture_analysis.plots.modality.save_fig", captures(snapshots)):
        plot_series(
            tmp_path / "dense.png",
            times,
            values,
            window=TimeWindow(0, int(times[-1])),
            gaps=[gap],
            ylabel="V",
            title="Dense",
        )
    segments = edges(snapshots["dense.png"][0])
    assert not any(start < 10.001 < end for start, end in segments)
    assert not any(start < 20.001 < end for start, end in segments)
    assert segments[0][0] == 0.0
    assert segments[-1][-1] == 40.004


def test_negative_session_time_is_preserved(tmp_path):
    snapshots = {}
    with patch("capture_analysis.plots.modality.save_fig", captures(snapshots)):
        plot_series(
            tmp_path / "negative.png",
            np.array([-2, -1, 0, 1]) * SECOND,
            np.arange(4.0),
            window=TimeWindow(-2 * SECOND, SECOND),
            gaps=[],
            ylabel="V",
            title="Pre T0",
        )
    assert edges(snapshots["negative.png"][0]) == [(-2.0, -1.0), (-1.0, 0.0), (0.0, 1.0)]
