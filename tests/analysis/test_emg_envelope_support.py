# SPDX-License-Identifier: GPL-3.0-only
"""Actual recorded-EMG envelope support and independent numerical expectations."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from capture_analysis.emg_envelope import emg_rms_envelope
from capture_analysis.types import GapInterval, GapMask, LoadedEmg, StreamRef, TimeWindow
from capture_protocol.generated.capture.v1.data import emg_batch_pb2
from mcap.writer import Writer

ROOT = Path(__file__).resolve().parents[2]


def mask(times, gaps=(), rate=1000):
    ref = StreamRef("emg", "raw", "emg", "emg.batch/1", rate, "mV")
    return GapMask(ref, TimeWindow(int(times[0]), int(times[-1])), list(gaps), "mask")


@pytest.mark.parametrize("declared", [False, True])
def test_two_constant_contractions_do_not_contaminate_each_other(declared):
    times = np.r_[np.arange(50) * 1_000_000, 2_000_000_000 + np.arange(50) * 1_000_000]
    samples = np.r_[np.ones(50), np.full(50, 9.0)].reshape(1, -1)
    gaps = [GapInterval("emg", "raw", "disconnect", 50_000_000, 1_999_999_999, True)]
    loaded = LoadedEmg(["flexor"], times.copy(), samples.copy(), 1000, "mV")
    t, y = emg_rms_envelope(loaded, mask(times, gaps if declared else []))
    assert np.isnan(y).sum() == 1
    np.testing.assert_array_equal(y[(t < 50_000_000) & np.isfinite(y)], 1.0)
    np.testing.assert_array_equal(y[(t >= 2_000_000_000) & np.isfinite(y)], 9.0)
    np.testing.assert_array_equal(loaded.X, samples)
    np.testing.assert_array_equal(loaded.t_sample_ns, times)


def test_short_runs_survive_and_invalid_samples_never_enter_the_rms():
    times = np.arange(6) * 500_000
    values = np.array([[3.0, 3.0, np.nan, 7.0, 999.0, 7.0]])
    gap = GapInterval("emg", "raw", "disconnect", 2_000_000, 2_000_000, True)
    t, y = emg_rms_envelope(
        LoadedEmg(["flexor"], times, values, 2000, "mV"),
        mask(times, [gap], rate=2000),
    )
    np.testing.assert_array_equal(t[np.isfinite(y)], [0, 500_000, 1_500_000, 2_500_000])
    np.testing.assert_array_equal(y[np.isfinite(y)], [3.0, 3.0, 7.0, 7.0])
    assert np.isnan(y).sum() == 2


def test_nonintegral_rate_matches_scalar_centered_observed_support():
    rate = 137
    times = 123_000_000 + np.arange(73) * round(1e9 / rate)
    values = np.array([(-1) ** i * (2 + i / 11) for i in range(len(times))])
    t, y = emg_rms_envelope(
        LoadedEmg(["flexor"], times, values.reshape(1, -1), rate, "mV"),
        mask(times, rate=rate),
    )
    # The documented six-sample kernel uses three left and two right neighbours.
    expected = []
    for stamp in t:
        i = list(times).index(stamp)
        window = values[max(0, i - 3) : min(len(values), i + 3)]
        expected.append(np.sqrt(sum(float(v) ** 2 for v in window) / len(window)))
    np.testing.assert_allclose(y, expected, rtol=1e-12)


def test_actual_cli_saves_finite_separate_contractions_and_json_null_break(tmp_path):
    root = tmp_path / "contractions.mmsession"
    stream = root / "sources/emg/streams/raw"
    (stream / "segments").mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({"sessionId": "envelope", "state": "finalized"}))
    (root / "integrity.json").write_text(
        json.dumps({"files": [{"endSessionTimeNs": 3_050_000_000}]})
    )
    (stream / "stream.json").write_text(
        json.dumps(
            {
                "sourceId": "emg",
                "streamId": "raw",
                "modality": "emg",
                "dataSchemaId": "emg.batch/1",
                "nominalRateHz": 1000,
                "units": "mV",
                "dimensions": [1],
            }
        )
    )
    with (stream / "segments/000000.mcap").open("wb") as output:
        writer = Writer(output)
        writer.start()
        schema = writer.register_schema("emg.batch/1", "protobuf", b"")
        channel = writer.register_channel("emg/raw", "protobuf", schema)
        for t0, value in [(1_000_000_000, 2.0), (3_000_000_000, 8.0)]:
            msg = emg_batch_pb2.EmgBatch(
                sample_count=50,
                channel_ids=["flexor"],
                samples_f32_le=np.full((1, 50), value, dtype="<f4").tobytes(),
            )
            msg.timing.session_time_ns = t0
            writer.add_message(channel, t0, msg.SerializeToString(), t0)
        writer.finish()
    health = root / "sources/emg/health"
    health.mkdir()
    (health / "gaps.jsonl").write_text(
        json.dumps(
            {
                "streamId": "raw",
                "cause": "DISCONNECT",
                "startSessionTimeNs": "1050000000",
                "endSessionTimeNs": "2999999999",
                "closed": True,
            }
        )
        + "\n"
    )
    raw = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/run_analysis.py"),
            "plots",
            str(root),
            "--overwrite-job-id",
            "envelope-use",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    job = root / "processing/jobs/envelope-use"

    def forbid_nonfinite(value):
        raise AssertionError(f"nonstandard JSON number {value}")

    saved = json.loads(
        (job / "figures/sync_dashboard_series.json").read_text(), parse_constant=forbid_nonfinite
    )
    series = saved["series"][0]
    finite = [(t, y) for t, y in zip(series["t_ns"], series["y"], strict=True) if y is not None]
    assert any(y is None for y in series["y"])
    assert all(y == (2.0 if t < 2_000_000_000 else 8.0) for t, y in finite)
    assert (job / "figures/sync_dashboard.png").stat().st_size > 1000
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in raw.items())

    # A recording with no usable support must not create an empty interactive lane.
    (health / "gaps.jsonl").write_text(
        json.dumps(
            {
                "streamId": "raw",
                "cause": "DISCONNECT",
                "startSessionTimeNs": "0",
                "closed": False,
            }
        )
        + "\n"
    )
    empty = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/run_analysis.py"),
            "plots",
            str(root),
            "--overwrite-job-id",
            "envelope-empty",
        ],
        capture_output=True,
        text=True,
    )
    assert empty.returncode == 0, empty.stdout + empty.stderr
    assert not (root / "processing/jobs/envelope-empty/figures/sync_dashboard_series.json").exists()
