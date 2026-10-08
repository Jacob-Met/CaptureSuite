# SPDX-License-Identifier: GPL-3.0-only
"""Receive closing checkpoint sections through the public API and real CLI."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from capture_analysis.types import TimeWindow
from capture_analysis.windows import checkpoint_section_window, resolve_window
from capture_session.package_reader import ReviewSummary

ROOT = Path(__file__).resolve().parents[2]
SECOND = 1_000_000_000
STEP = 100_000_000


def _summary(checkpoints: list[dict], duration_ns: int = 8 * SECOND) -> ReviewSummary:
    return ReviewSummary(
        package_path="fixture.mmsession",
        session_id="closing-checkpoints",
        state="finalized",
        checkpoints=checkpoints,
        duration_ns=duration_ns,
    )


def _checkpoints() -> list[dict]:
    # Stored order is deliberately not chronological; equal times retain order.
    return [
        {"checkpointId": "finish", "name": "Finish", "originalTimestampNs": str(7 * SECOND)},
        {"checkpointId": "zero", "name": "Start", "originalTimestampNs": "0"},
        {"checkpointId": "warmup", "name": "Warm-up", "originalTimestampNs": str(2 * SECOND)},
        {"checkpointId": "reach", "name": "Reach – 左", "originalTimestampNs": str(5 * SECOND)},
        {"checkpointId": "tie", "name": "Same instant", "originalTimestampNs": str(5 * SECOND)},
    ]


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ("warmup", (0, 2 * SECOND)),
        ("reach", (2 * SECOND, 5 * SECOND)),
        ("Reach – 左", (2 * SECOND, 5 * SECOND)),
        ("finish", (5 * SECOND, 7 * SECOND)),
        ("zero", (0, 0)),
        ("tie", (5 * SECOND, 5 * SECOND)),
    ],
)
def test_named_checkpoint_closes_its_preceding_section(selection, expected):
    summary = _summary(_checkpoints())
    before = copy.deepcopy(summary.checkpoints)
    window = checkpoint_section_window(summary, selection)
    assert window == TimeWindow(*expected, label=f"cp:{selection}")
    assert window.contains(expected[0]) and window.contains(expected[1])
    assert summary.checkpoints == before, "resolving must not reorder or edit stored checkpoints"


@pytest.mark.parametrize(
    "time_field",
    [
        "effectiveTimestampNs",
        "effective_timestamp_ns",
        "originalTimestampNs",
        "original_timestamp_ns",
        "timestampNs",
        "timestamp_ns",
    ],
)
def test_existing_timestamp_aliases_keep_exact_closing_bounds(time_field):
    summary = _summary(
        [
            {"checkpoint_id": "first", time_field: "2000000000"},
            {"checkpoint_id": "second", time_field: "5000000000"},
        ]
    )
    assert checkpoint_section_window(summary, "second") == TimeWindow(
        2 * SECOND, 5 * SECOND, "cp:second"
    )


def test_edited_effective_times_change_order_without_rewriting_originals():
    checkpoints = _checkpoints()
    checkpoints[3]["effectiveTimestampNs"] = str(SECOND)
    summary = _summary(checkpoints)
    before = copy.deepcopy(checkpoints)
    assert checkpoint_section_window(summary, "reach") == TimeWindow(0, SECOND, "cp:reach")
    assert checkpoint_section_window(summary, "warmup") == TimeWindow(
        SECOND, 2 * SECOND, "cp:warmup"
    )
    assert summary.checkpoints == before


def test_effective_zero_is_retained_and_null_falls_back():
    summary = _summary(
        [
            {"name": "zero", "originalTimestampNs": "100", "effectiveTimestampNs": "0"},
            {"name": "next", "originalTimestampNs": "200", "effectiveTimestampNs": None},
        ]
    )
    assert checkpoint_section_window(summary, "zero") == TimeWindow(0, 0, "cp:zero")
    assert checkpoint_section_window(summary, "next") == TimeWindow(0, 200, "cp:next")


def test_decimal_nanoseconds_remain_exact_beyond_float_precision():
    start, end = 9_007_199_254_740_993, 9_007_199_254_741_003
    summary = _summary(
        [
            {"name": "first", "effectiveTimestampNs": str(start)},
            {"name": "second", "effectiveTimestampNs": str(end)},
        ],
        end + 1,
    )
    assert checkpoint_section_window(summary, "second") == TimeWindow(start, end, "cp:second")


@pytest.mark.parametrize(
    ("checkpoints", "selection", "message"),
    [([], "missing", "no checkpoints"), (_checkpoints(), "missing", "section not found")],
)
def test_missing_section_is_not_silently_replaced(checkpoints, selection, message):
    with pytest.raises(ValueError, match=message):
        resolve_window(_summary(checkpoints), checkpoint_section=selection)


def test_out_of_session_first_checkpoint_cannot_form_an_inverted_window():
    summary = _summary([{"name": "before-start", "effectiveTimestampNs": "-1"}])
    with pytest.raises(ValueError, match=r"start=0.*end=-1"):
        resolve_window(summary, checkpoint_section="before-start")


def test_later_signed_adjacent_endpoints_are_not_clamped():
    summary = _summary(
        [
            {"name": "before-start", "effectiveTimestampNs": "-1"},
            {"name": "at-start", "effectiveTimestampNs": "0"},
        ]
    )
    assert resolve_window(summary, checkpoint_section="at-start") == TimeWindow(
        -1, 0, "cp:at-start"
    )


def test_full_custom_and_explicit_section_precedence_remain_unchanged():
    summary = _summary(_checkpoints())
    assert resolve_window(summary) == TimeWindow(0, 8 * SECOND, "full")
    assert resolve_window(_summary([])) == TimeWindow(0, 8 * SECOND, "full")
    assert resolve_window(summary, start_ns=-1, end_ns=0) == TimeWindow(-1, 0, "custom")
    assert resolve_window(summary, start_ns=4, end_ns=4) == TimeWindow(4, 4, "custom")
    assert resolve_window(
        summary, start_ns=6 * SECOND, end_ns=8 * SECOND, checkpoint_section="warmup"
    ) == TimeWindow(0, 2 * SECOND, "cp:warmup")
    with pytest.raises(ValueError, match="invalid window"):
        resolve_window(summary, start_ns=2, end_ns=1)
    assert resolve_window(_summary([], 0)) == TimeWindow(-(1 << 62) + 1, (1 << 62) - 1, "full")


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_imu_package(path: Path, checkpoints: list[dict]) -> Path:
    """Eighty-one actual protobuf/MCAP frames; x=i at t=i/10 seconds."""
    from capture_protocol.generated.capture.v1.data import imu_frame_pb2
    from mcap.writer import Writer

    path.mkdir()
    source_id, stream_id = "sim.imu.upper", "sim.imu.upper.frames"
    _write_json(
        path / "manifest.json",
        {
            "session_schema_version": "1.0.0",
            "sessionId": "checkpoint-sections-receiving",
            "state": "finalized",
            "t0WallUtc": "2026-10-08T00:00:00Z",
            "finalizedUtc": "2026-10-08T00:00:08Z",
            "sourceIds": [source_id],
        },
    )
    _write_json(path / "events/checkpoints.json", checkpoints)
    _write_json(path / "events/annotations.json", [])
    _write_json(path / "events/sync_anchors.json", [])
    source = path / "sources" / source_id
    _write_json(
        source / "source.json",
        {"sourceId": source_id, "sourceType": "sim.imu", "pluginId": "sim.imu"},
    )
    stream = source / "streams" / stream_id
    _write_json(
        stream / "stream.json",
        {
            "streamId": stream_id,
            "sourceId": source_id,
            "modality": "imu",
            "units": "a.u.",
            "dimensions": [3],
            "nominalRateHz": 10.0,
            "dataSchemaId": "imu.frame/1",
            "dataSchemaVersion": "1",
        },
    )
    raw = stream / "segments/000000.mcap"
    raw.parent.mkdir()
    with raw.open("wb") as handle:
        writer = Writer(handle)
        writer.start(profile="", library="capturesuite-checkpoint-test")
        schema = writer.register_schema(name="imu.frame/1", encoding="protobuf", data=b"")
        channel = writer.register_channel(
            topic="imu", message_encoding="protobuf", schema_id=schema
        )
        for index in range(81):
            frame = imu_frame_pb2.ImuFrame()
            frame.timing.session_time_ns = index * STEP
            frame.timing.sequence_number = index
            frame.frame_index = index
            sensor = frame.sensors.add()
            sensor.sensor_id = "wrist"
            sensor.accel_x = float(index)
            sensor.qw = 1.0
            writer.add_message(
                channel_id=channel,
                log_time=index * STEP,
                publish_time=index * STEP,
                data=frame.SerializeToString(),
            )
        writer.finish()
    _write_json(
        path / "integrity.json",
        {
            "schemaVersion": "1",
            "files": [
                {
                    "path": raw.relative_to(path).as_posix(),
                    "sizeBytes": raw.stat().st_size,
                    "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                    "endSessionTimeNs": 8 * SECOND,
                }
            ],
        },
    )
    return path


def _raw_hashes(package: Path) -> dict[str, str]:
    return {
        p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(package.rglob("*"))
        if p.is_file() and p.relative_to(package).parts[0] != "processing"
    }


@pytest.mark.parametrize(
    ("case", "arguments", "bounds", "command"),
    [
        ("first", ["--checkpoint-section", "warmup"], (0, 2 * SECOND), "features"),
        ("middle", ["--checkpoint-section", "Reach – 左"], (2 * SECOND, 5 * SECOND), "all"),
        ("last", ["--checkpoint-section", "finish"], (5 * SECOND, 7 * SECOND), "features"),
        ("zero", ["--checkpoint-section", "zero"], (0, 0), "features"),
        ("tie", ["--checkpoint-section", "tie"], (5 * SECOND, 5 * SECOND), "features"),
        ("edited", ["--checkpoint-section", "reach"], (2 * SECOND, 4 * SECOND), "features"),
        ("full", [], (0, 8 * SECOND), "features"),
        ("no-checkpoints", [], (0, 8 * SECOND), "features"),
        (
            "custom",
            ["--start-ns", str(7 * SECOND), "--end-ns", str(8 * SECOND)],
            (7 * SECOND, 8 * SECOND),
            "features",
        ),
    ],
)
def test_real_cli_emits_the_selected_section_without_changing_raw(
    tmp_path: Path, case, arguments, bounds, command
):
    checkpoints = [] if case == "no-checkpoints" else _checkpoints()
    if case == "edited":
        checkpoints[3]["effectiveTimestampNs"] = str(4 * SECOND)
    package = _write_imu_package(tmp_path / "sections.mmsession", checkpoints)
    before = _raw_hashes(package)
    env = {**os.environ, "MPLBACKEND": "Agg", "MPLCONFIGDIR": str(tmp_path / "mpl")}
    invocation = [
        sys.executable,
        str(ROOT / "tools/run_analysis.py"),
        command,
        str(package),
        "--overwrite-job-id",
        "checkpoint-receiving",
        *arguments,
    ]
    received = subprocess.run(invocation, capture_output=True, text=True, env=env, timeout=60)
    after = _raw_hashes(package)
    job = package / "processing/jobs/checkpoint-receiving"
    manifest = json.loads((job / "job_manifest.json").read_text(encoding="utf-8"))
    _write_json(
        tmp_path / "receiving.json",
        {
            "case": case,
            "invocation": invocation,
            "returncode": received.returncode,
            "stdout": received.stdout,
            "stderr": received.stderr,
            "expected_bounds": bounds,
            "actual_time_range": manifest.get("timeRange"),
            "raw_before": before,
            "raw_after": after,
        },
    )
    assert before == after
    assert received.returncode == 0, received.stderr
    assert manifest["status"] == "completed", manifest.get("warnings")
    assert (
        manifest["timeRange"]["startSessionNs"],
        manifest["timeRange"]["endSessionNs"],
    ) == bounds

    feature = job / "features/imu/sim.imu.upper/windows.parquet"
    frame = pd.read_parquet(feature)
    csv = pd.read_csv(feature.with_suffix(".csv"))
    pd.testing.assert_frame_equal(frame, csv, check_dtype=False)
    # The fixture's 10 Hz samples and existing 0.2 s windows produce exact pair
    # means; a point section keeps its one boundary sample under TimeWindow's
    # existing inclusive policy. These values distinguish every neighboring task.
    first, last = bounds[0] // STEP, bounds[1] // STEP
    expected_x = (
        np.arange(first, last, dtype=float) + 0.5 if last > first else np.array([float(first)])
    )
    expected_t = (expected_x * STEP).astype(np.int64)
    np.testing.assert_array_equal(frame["t_mid_ns"].to_numpy(), expected_t)
    np.testing.assert_allclose(frame["wrist_acc_x_mean"].to_numpy(), expected_x, rtol=0, atol=0)
    np.testing.assert_array_equal(frame["valid_fraction"].to_numpy(), np.ones(expected_x.size))
    if command == "all":
        series = json.loads(
            (job / "figures/sync_dashboard_series.json").read_text(encoding="utf-8")
        )
        np.testing.assert_array_equal(
            series["series"][0]["t_ns"], np.arange(first, last + 1) * STEP
        )
        np.testing.assert_array_equal(series["series"][0]["y"], np.arange(first, last + 1))
        assert (job / "figures/imu_sim.imu.upper_accel.png").stat().st_size > 0
        assert (job / "figures/sync_dashboard.png").stat().st_size > 0


def test_real_cli_reports_an_inverted_persisted_checkpoint(tmp_path: Path):
    # Signed values are accepted by the stored checkpoint schema/reader. This
    # qualifies persisted input, not a claim about a timestamp-editing UI.
    package = _write_imu_package(
        tmp_path / "signed.mmsession", [{"name": "before-start", "effectiveTimestampNs": "-1"}]
    )
    before = _raw_hashes(package)
    invocation = [
        sys.executable,
        str(ROOT / "tools/run_analysis.py"),
        "features",
        str(package),
        "--checkpoint-section",
        "before-start",
        "--overwrite-job-id",
        "negative-receiving",
    ]
    received = subprocess.run(invocation, capture_output=True, text=True, timeout=60)
    job = package / "processing/jobs/negative-receiving"
    manifest = json.loads((job / "job_manifest.json").read_text(encoding="utf-8"))
    after = _raw_hashes(package)
    _write_json(
        tmp_path / "receiving.json",
        {
            "invocation": invocation,
            "returncode": received.returncode,
            "stdout": received.stdout,
            "stderr": received.stderr,
            "manifest_status": manifest["status"],
            "errors": manifest.get("errors"),
            "raw_before": before,
            "raw_after": after,
        },
    )
    assert before == after
    assert received.returncode == 1
    assert manifest["status"] == "failed"
    assert any("start=0" in error and "end=-1" in error for error in manifest["errors"])
    assert not list(job.rglob("*.parquet"))
