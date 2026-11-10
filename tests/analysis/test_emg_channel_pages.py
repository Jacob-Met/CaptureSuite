# SPDX-License-Identifier: GPL-3.0-only
"""Later recorded EMG channels must survive into ordinary saved figure artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
from capture_analysis.pipeline import run_features_and_plots
from capture_analysis.plots.style import save_fig
from capture_analysis.types import TimeWindow
from capture_protocol.generated.capture.v1.data import emg_batch_pb2
from capture_session.package_reader import load_review_summary
from mcap.writer import Writer

SECOND = 1_000_000_000


def test_all_recorded_channels_have_identifiable_saved_pages(tmp_path):
    package = tmp_path / "nine-electrodes.mmsession"
    stream = package / "sources" / "forearm" / "streams" / "raw"
    (stream / "segments").mkdir(parents=True)
    (package / "manifest.json").write_text(
        json.dumps({"sessionId": "nine-electrodes", "state": "finalized"})
    )
    (stream / "stream.json").write_text(
        json.dumps(
            {
                "sourceId": "forearm",
                "streamId": "raw",
                "modality": "emg",
                "dataSchemaId": "emg.batch/1",
                "nominalRateHz": 1,
                "units": "mV",
                "dimensions": [9],
            }
        )
    )
    channels = [f"electrode-{index}" for index in range(1, 10)]
    with (stream / "segments" / "000000.mcap").open("wb") as fh:
        writer = Writer(fh)
        writer.start()
        schema = writer.register_schema("emg.batch/1", "protobuf", b"")
        topic = writer.register_channel("forearm/raw", "protobuf", schema)
        for index, second in enumerate((10, 11, 14, 15)):
            values = np.array([channel * 10 + index for channel in range(1, 10)], dtype="<f4")
            message = emg_batch_pb2.EmgBatch(
                first_sample_index=second,
                sample_count=1,
                channel_ids=channels,
                samples_f32_le=values.tobytes(),
            )
            message.timing.session_time_ns = second * SECOND
            writer.add_message(topic, second * SECOND, message.SerializeToString(), second * SECOND)
        writer.finish()
    health = package / "sources" / "forearm" / "health"
    health.mkdir()
    (health / "gaps.jsonl").write_text(
        json.dumps(
            {
                "streamId": "raw",
                "cause": "DISCONNECT",
                "startSessionTimeNs": str(12 * SECOND),
                "endSessionTimeNs": str(13 * SECOND),
                "closed": True,
            }
        )
        + "\n"
    )
    raw_hashes = {
        p.relative_to(package): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in package.rglob("*")
        if p.is_file()
    }
    snapshots = {}

    def capture(fig, path):
        snapshots[Path(path).name] = {
            "title": fig._suptitle.get_text(),
            "axes": [
                {
                    "channel": axis.get_title(loc="left"),
                    "xlabel": axis.get_xlabel(),
                    "ylabel": axis.get_ylabel(),
                    "bands": len(axis.patches),
                    "lines": [
                        (line.get_xdata().copy(), line.get_ydata().copy())
                        for line in axis.get_lines()
                    ],
                }
                for axis in fig.axes
            ],
        }
        save_fig(fig, path)

    outputs, warnings = [], []
    work = package / "processing" / "jobs" / "all-channels"
    with patch("capture_analysis.plots.modality.save_fig", capture):
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

    assert set(snapshots) == {
        "emg_forearm_channels.png",
        "emg_forearm_channels_005-008.png",
        "emg_forearm_channels_009-009.png",
    }
    assert [len(page["axes"]) for page in snapshots.values()] == [4, 4, 1]
    assert [page["title"] for page in snapshots.values()] == [
        "EMG · forearm · channels 1–4 of 9",
        "EMG · forearm · channels 5–8 of 9",
        "EMG · forearm · channels 9–9 of 9",
    ]
    axes = [axis for page in snapshots.values() for axis in page["axes"]]
    assert [axis["channel"] for axis in axes] == channels
    for channel, axis in enumerate(axes, start=1):
        actual = {
            float(t): float(value)
            for times, values in axis["lines"]
            for t, value in zip(times, values, strict=True)
            if np.isfinite(value)
        }
        assert actual == dict(
            zip((10.0, 11.0, 14.0, 15.0), range(channel * 10, channel * 10 + 4), strict=True)
        )
        assert axis["bands"] == 1
        assert axis["ylabel"] == "mV"
        assert not any(
            a == 11 and b == 14 and np.isfinite(values[index : index + 2]).all()
            for times, values in axis["lines"]
            for index, (a, b) in enumerate(zip(times[:-1], times[1:], strict=True))
        )
    assert all(page["axes"][-1]["xlabel"] == "session time (s)" for page in snapshots.values())
    recorded_outputs = {Path(entry["relativePath"]).name: entry for entry in outputs}
    for name in snapshots:
        entry = recorded_outputs[name]
        path = work / entry["relativePath"]
        assert entry["kind"] == "figure"
        assert entry["bytes"] == path.stat().st_size
        assert entry["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert all(
        hashlib.sha256((package / name).read_bytes()).hexdigest() == digest
        for name, digest in raw_hashes.items()
    )
