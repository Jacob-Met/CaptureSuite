# SPDX-License-Identifier: GPL-3.0-only
"""Video QC observes intervals without treating recorded gaps as valid cadence."""

from __future__ import annotations

import ast
import json
import shutil
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from capture_analysis.features.video_qc import extract_video_qc
from capture_analysis.loaders.video import LoadedVideoTiming
from capture_analysis.types import GapInterval, GapMask, StreamRef, TimeWindow


def extract(times, *, gaps=(), policy="mask", window=None):
    t = np.asarray(times, dtype=np.int64)
    source = StreamRef("sim.video", "frames", "video", "video.timing/1", 10.0, "ns")
    span = window or TimeWindow(int(t.min()) if t.size else 0, int(t.max()) if t.size else 0)
    gap_mask = GapMask(
        source,
        span,
        [GapInterval("sim.video", "frames", "DISCONNECT", a, b, b is not None) for a, b in gaps],
        policy,
    )
    original = t.copy()
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        result = extract_video_qc(LoadedVideoTiming(t), gap_mask, nominal_rate_hz=10.0)
    np.testing.assert_array_equal(t, original)
    return result


def summary(result):
    return ast.literal_eval(
        next(w.split("=", 1)[1] for w in result[3] if w.startswith("video_qc_summary="))
    )


def test_regular_frames_keep_observed_intervals_and_feature_schema():
    result = extract([0, 100_000_000, 200_000_000, 300_000_000])
    table, meta, fraction, _ = result
    assert list(table.columns) == ["t_ns", "dt_s", "fps_inst", "valid"]
    assert [m["name"] for m in meta] == list(table.columns)
    assert table.t_ns.tolist() == [100_000_000, 200_000_000, 300_000_000]
    assert table.dt_s.tolist() == [0.1, 0.1, 0.1]
    assert table.fps_inst.tolist() == [10.0, 10.0, 10.0]
    assert table.valid.tolist() == [1, 1, 1]
    assert fraction == 1.0
    assert summary(result)["fps_median"] == 10.0


def test_recorded_gap_between_retained_frames_is_not_valid_cadence():
    result = extract(
        [0, 100_000_000, 2_100_000_000, 2_200_000_000], gaps=[(200_000_000, 2_000_000_000)]
    )
    table = result[0]
    assert table.valid.tolist() == [1, 0, 1]
    assert table.dt_s.tolist() == [0.1, 2.0, 0.1]
    assert np.isnan(table.fps_inst.iloc[1])
    assert result[2] == 1.0  # Frame coverage and interval coverage are distinct.
    details = summary(result)
    assert details["fps_median"] == 10.0
    assert details["dt_p95_s"] == 0.1
    assert details["interval_count"] == 3
    assert details["valid_interval_count"] == 2
    assert details["invalid_interval_count"] == 1


def test_both_endpoints_must_be_valid():
    result = extract([0, 100, 200, 300, 400], gaps=[(200, 300)])
    assert result[0].valid.tolist() == [1, 0, 0, 0]
    assert result[0].fps_inst.isna().tolist() == [False, True, True, True]
    assert result[2] == 3 / 5


@pytest.mark.parametrize("gap", [(100, 100), (100, 199), (101, 200), (101, 199)])
def test_closed_gap_edges_break_the_affected_pairs(gap):
    result = extract([0, 100, 200, 300], gaps=[gap])
    expected = [1, 0, 1]
    if gap[0] == 100:
        expected[0] = 0
    if gap[1] == 200:
        expected[2] = 0
    assert result[0].valid.tolist() == expected


def test_open_gap_invalidates_the_remaining_intervals():
    result = extract([0, 100, 200, 300], gaps=[(150, None)])
    assert result[0].valid.tolist() == [1, 0, 0]
    assert summary(result)["valid_interval_count"] == 1
    assert result[2] == 0.5


def test_overlapping_gap_records_do_not_change_the_union():
    a = extract([0, 100, 200, 300, 400], gaps=[(125, 275)])
    b = extract([0, 100, 200, 300, 400], gaps=[(125, 175), (150, 275), (125, 175)])
    pd.testing.assert_frame_equal(a[0], b[0])
    assert a[1:] == b[1:]


def test_outside_and_reversed_intervals_keep_existing_mask_semantics():
    expected = extract([0, 100, 200, 300])
    actual = extract([0, 100, 200, 300], gaps=[(-200, -100), (400, None), (190, 110)])
    pd.testing.assert_frame_equal(expected[0], actual[0])
    assert expected[1:] == actual[1:]


def test_window_requires_both_endpoints_inside():
    result = extract([0, 100, 200, 300], window=TimeWindow(100, 300))
    assert result[0].valid.tolist() == [0, 1, 1]
    assert result[2] == 0.75


def test_duplicate_and_reversed_timestamps_are_retained_but_not_usable():
    result = extract([0, 0, 100_000_000, 50_000_000, 200_000_000])
    assert result[0].valid.tolist() == [0, 1, 0, 1]
    assert result[0].dt_s.tolist() == [0.0, 0.1, -0.05, 0.15]
    assert result[0].fps_inst.isna().tolist() == [True, False, True, False]
    assert summary(result)["dt_p50_s"] == 0.125
    assert result[2] == 1.0


@pytest.mark.parametrize("origin", [2**60, -(2**60)])
def test_differences_preserve_small_intervals_at_large_signed_origins(origin):
    result = extract([origin, origin + 100, origin + 200])
    assert result[0].t_ns.tolist() == [origin + 100, origin + 200]
    assert result[0].dt_s.tolist() == [1e-7, 1e-7]
    assert result[0].fps_inst.tolist() == [1e7, 1e7]
    assert result[0].valid.tolist() == [1, 1]


def test_full_signed_int64_span_does_not_overflow():
    result = extract([-(2**63), 2**63 - 1])
    assert result[0].dt_s.tolist() == [(2**64 - 1) / 1e9]
    assert result[0].valid.tolist() == [1]
    assert result[0].fps_inst.iloc[0] > 0


@pytest.mark.parametrize(
    "times",
    [
        [-(2**63), -1, 100, 2**63 - 1],
        [-(2**63), 0, 2**63 - 1],
        [100, -100, 100, -100],
    ],
)
def test_mixed_sign_pairs_match_integer_differences(times):
    result = extract(times)
    expected = [(right - left) / 1e9 for left, right in zip(times[:-1], times[1:], strict=True)]
    assert result[0].dt_s.tolist() == expected
    assert result[0].valid.tolist() == [int(dt > 0) for dt in expected]


def test_reversed_full_span_is_not_a_positive_interval():
    result = extract([2**63 - 1, -(2**63)])
    assert result[0].dt_s.tolist() == [-(2**64 - 1) / 1e9]
    assert result[0].valid.tolist() == [0]
    assert np.isnan(result[0].fps_inst.iloc[0])
    assert summary(result)["fps_median"] is None


def test_all_invalid_intervals_have_explicit_missing_statistics():
    result = extract([0, 100, 200], gaps=[(0, None)])
    assert result[0].valid.tolist() == [0, 0]
    assert result[0].fps_inst.isna().all()
    assert result[2] == 0.0
    details = summary(result)
    assert details["valid_interval_count"] == 0
    assert details["fps_median"] is None
    assert details["dt_p50_s"] is None
    assert details["dt_p95_s"] is None


@pytest.mark.parametrize("times", [[], [100]])
def test_short_inputs_preserve_empty_result(times):
    result = extract(times)
    assert result[0].empty
    assert result[1:] == ([], 0.0, [])


@pytest.mark.parametrize("gap", [(100, 100), (101, 199)])
def test_fail_policy_detects_gap_on_frames_or_between_frames(gap):
    with pytest.raises(RuntimeError, match="gap_policy=fail"):
        extract([0, 100, 200, 300], gaps=[gap], policy="fail")


def test_split_and_mask_share_the_same_interval_rows():
    a = extract([0, 100, 200, 300], gaps=[(125, 175)])
    b = extract([0, 100, 200, 300], gaps=[(125, 175)], policy="split")
    pd.testing.assert_frame_equal(a[0], b[0])
    assert a[1:] == b[1:]


def test_nonpositive_interval_does_not_invent_a_gap_policy_failure():
    result = extract([0, 0, 100], gaps=[(200, 250)], policy="fail", window=TimeWindow(0, 300))
    assert result[0].valid.tolist() == [0, 1]


def write_video_package(destination: Path) -> Path:
    from capture_protocol.generated.capture.v1.data import video_timing_pb2
    from mcap.writer import Writer

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "mini_session"
    shutil.copytree(fixture, destination)
    shutil.rmtree(destination / "sources")
    source = destination / "sources" / "sim.video"
    segments = source / "streams" / "frames" / "segments"
    segments.mkdir(parents=True)
    (source / "health").mkdir()
    (source / "source.json").write_text(json.dumps({"sourceId": "sim.video", "modality": "video"}))
    (segments.parent / "stream.json").write_text(
        json.dumps(
            {
                "streamId": "frames",
                "modality": "video",
                "dataSchemaId": "video.timing/1",
                "nominalRateHz": 10.0,
                "units": "ns",
                "dimensions": [],
            }
        )
    )
    (source / "health" / "gaps.jsonl").write_text(
        json.dumps(
            {
                "streamId": "frames",
                "cause": "GAP_CAUSE_DISCONNECT",
                "startSessionTimeNs": "200000000",
                "endSessionTimeNs": "2000000000",
                "closed": True,
            }
        )
        + "\n"
    )
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sourceIds"] = ["sim.video"]
    manifest_path.write_text(json.dumps(manifest))
    with (segments / "000000.mcap").open("wb") as output:
        writer = Writer(output)
        writer.start(profile="", library="capturesuite-video-qc-test")
        schema = writer.register_schema(name="video.timing/1", encoding="protobuf", data=b"")
        channel = writer.register_channel(
            topic="video", message_encoding="protobuf", schema_id=schema
        )
        for sequence, timestamp in enumerate([0, 100_000_000, 2_100_000_000, 2_200_000_000]):
            message = video_timing_pb2.VideoFrameTiming()
            message.timing.session_time_ns = timestamp
            message.timing.sequence_number = sequence
            writer.add_message(
                channel_id=channel,
                log_time=timestamp,
                publish_time=timestamp,
                data=message.SerializeToString(),
            )
        writer.finish()
    (destination / "integrity.json").write_text(
        json.dumps({"files": [{"endSessionTimeNs": 2_200_000_000}]})
    )
    return destination


@pytest.mark.parametrize("command", ["features", "plots", "all"])
def test_real_mcap_job_preserves_gap_mask_in_saved_tables_and_plots(tmp_path, monkeypatch, command):
    from capture_analysis import JobParams, hash_sources_tree, run
    from capture_analysis.plugins import handlers

    plotted = []
    original_plot = handlers.plot_series

    def receive_plot(path, t_ns, y, **kwargs):
        plotted.append((t_ns.copy(), y.copy()))
        return original_plot(path, t_ns, y, **kwargs)

    monkeypatch.setattr(handlers, "plot_series", receive_plot)

    package = write_video_package(tmp_path / "video.mmsession")
    original = hash_sources_tree(package)
    result = run(package, JobParams(command=command, overwrite_job_id="video-intervals"))
    assert result.status in ("completed", "completed_with_warnings")
    assert hash_sources_tree(package) == original
    relative = "features/video/sim.video/timing_qc.parquet"
    parquet = pd.read_parquet(result.job_dir / relative)
    csv = pd.read_csv(result.job_dir / relative.replace(".parquet", ".csv"))
    assert parquet.valid.tolist() == [1, 0, 1]
    assert parquet.dt_s.tolist() == [0.1, 2.0, 0.1]
    assert parquet.fps_inst.isna().tolist() == [False, True, False]
    pd.testing.assert_frame_equal(csv, parquet, check_dtype=False)
    schema = json.loads((result.job_dir / "features" / "_schema.json").read_text())
    assert schema["tables"][relative]["featureSchemaVersion"] == 1
    assert [c["name"] for c in schema["tables"][relative]["columns"]] == list(parquet.columns)
    if command != "features":
        assert len(plotted) == 1
        np.testing.assert_array_equal(plotted[0][0], [100_000_000, 2_100_000_000, 2_200_000_000])
        np.testing.assert_allclose(plotted[0][1], [10.0, np.nan, 10.0], equal_nan=True)
        assert (result.job_dir / "figures" / "video_sim.video_fps.png").stat().st_size > 0
        assert (result.job_dir / "figures" / "sync_dashboard.png").stat().st_size > 0
        series = json.loads((result.job_dir / "figures" / "sync_dashboard_series.json").read_text())
        assert series["series"][0]["t_ns"] == [100_000_000, 2_100_000_000, 2_200_000_000]
        np.testing.assert_allclose(
            np.asarray(series["series"][0]["y"], dtype=np.float64),
            [10.0, np.nan, 10.0], equal_nan=True,
        )
    else:
        assert not plotted
