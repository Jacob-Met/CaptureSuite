# SPDX-License-Identifier: GPL-3.0-only
"""Phase 5 pose job — sim teacher on sealed video timing fixture."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"

pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("mcap")


def _write_pose_package(dest: Path) -> Path:
    shutil.copytree(FIXTURE, dest)
    for p in dest.rglob("*.mcap"):
        p.unlink()

    from capture_protocol.generated.capture.v1.data import video_timing_pb2
    from mcap.writer import Writer

    cam_dir = dest / "sources" / "sim.camera.main"
    stream_dir = cam_dir / "streams" / "sim.camera.main.timing"
    seg_dir = stream_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    cam_dir.mkdir(parents=True, exist_ok=True)
    (cam_dir / "source.json").write_text(
        json.dumps(
            {
                "sourceId": "sim.camera.main",
                "sourceType": "camera",
                "modality": "video",
                "alias": "Camera sim",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (stream_dir / "stream.json").write_text(
        json.dumps(
            {
                "streamId": "sim.camera.main.timing",
                "sourceId": "sim.camera.main",
                "modality": "video",
                "units": "frame",
                "nominalRateHz": 30.0,
                "dataSchemaId": "video.timing/1",
                "dataSchemaVersion": "1",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    timing_path = seg_dir / "000000.timing.mcap"
    with timing_path.open("wb") as fh:
        w = Writer(fh)
        w.start(profile="", library="test")
        sid = w.register_schema(name="video.timing/1", encoding="protobuf", data=b"")
        cid = w.register_channel(topic="video_timing", message_encoding="protobuf", schema_id=sid)
        for i in range(10):
            msg = video_timing_pb2.VideoFrameTiming()
            msg.timing.session_time_ns = int(i * 1e9 / 30.0)
            msg.timing.sequence_number = i
            msg.frame_index = i
            msg.pts_ns = msg.timing.session_time_ns
            msg.keyframe = i == 0
            payload = msg.SerializeToString()
            w.add_message(
                channel_id=cid,
                log_time=msg.timing.session_time_ns,
                data=payload,
                publish_time=msg.timing.session_time_ns,
            )
        w.finish()

    mkv_path = seg_dir / "000000.mkv"
    mkv_path.write_bytes(b"\x1a\x45\xdf\xa3")  # minimal EBML header stub

    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    manifest["sourceIds"] = list(manifest.get("sourceIds", [])) + ["sim.camera.main"]
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return dest


def _add_camera_stream(dest: Path, source_id: str, *, n_frames: int = 10) -> None:
    from capture_protocol.generated.capture.v1.data import video_timing_pb2
    from mcap.writer import Writer

    cam_dir = dest / "sources" / source_id
    stream_dir = cam_dir / "streams" / f"{source_id}.timing"
    seg_dir = stream_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    (cam_dir / "source.json").write_text(
        json.dumps(
            {
                "sourceId": source_id,
                "sourceType": "camera",
                "modality": "video",
                "alias": source_id,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (stream_dir / "stream.json").write_text(
        json.dumps(
            {
                "streamId": f"{source_id}.timing",
                "sourceId": source_id,
                "modality": "video",
                "units": "frame",
                "nominalRateHz": 30.0,
                "dataSchemaId": "video.timing/1",
                "dataSchemaVersion": "1",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    timing_path = seg_dir / "000000.timing.mcap"
    with timing_path.open("wb") as fh:
        w = Writer(fh)
        w.start(profile="", library="test")
        sid = w.register_schema(name="video.timing/1", encoding="protobuf", data=b"")
        cid = w.register_channel(topic="video_timing", message_encoding="protobuf", schema_id=sid)
        for i in range(n_frames):
            msg = video_timing_pb2.VideoFrameTiming()
            msg.timing.session_time_ns = int(i * 1e9 / 30.0)
            msg.timing.sequence_number = i
            msg.frame_index = i
            msg.pts_ns = msg.timing.session_time_ns
            payload = msg.SerializeToString()
            w.add_message(
                channel_id=cid,
                log_time=msg.timing.session_time_ns,
                data=payload,
                publish_time=msg.timing.session_time_ns,
            )
        w.finish()
    (seg_dir / "000000.mkv").write_bytes(b"\x1a\x45\xdf\xa3")
    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    ids = list(manifest.get("sourceIds") or [])
    if source_id not in ids:
        ids.append(source_id)
    manifest["sourceIds"] = ids
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def test_pose_job_writes_landmarks_parquet(tmp_path: Path) -> None:
    from capture_analysis.jobs import JobParams, run

    pkg = _write_pose_package(tmp_path / "pose_pkg")
    result = run(pkg, JobParams(command="pose"))
    assert result.status in ("completed", "completed_with_warnings")
    lm = result.job_dir / "pose" / "sim.camera.main" / "landmarks.parquet"
    card = result.job_dir / "pose" / "sim.camera.main" / "model_card.json"
    assert lm.is_file()
    assert card.is_file()

    import pandas as pd

    df = pd.read_parquet(lm)
    assert set(df.columns) >= {
        "session_time_ns",
        "frame_index",
        "joint_index",
        "x",
        "y",
        "z",
        "confidence",
        "source_model",
    }
    assert df["joint_index"].max() == 24
    assert len(df) == 10 * 25
    card_doc = json.loads(card.read_text(encoding="utf-8"))
    assert card_doc["role"] == "body"
    assert card_doc["provisional"] is True
    assert result.manifest.get("poseModelId") == "sim_teacher_v1"


def test_pose_job_two_camera_session(tmp_path: Path) -> None:
    """Phase 5 gate: pose on sealed 2-cam package."""
    from capture_analysis.jobs import JobParams, run
    from capture_analysis.kinematics.registry import validate_parquet_columns

    pkg = _write_pose_package(tmp_path / "dual_cam")
    _add_camera_stream(pkg, "sim.camera.oblique")
    pose = run(pkg, JobParams(command="pose", overwrite_job_id="pose-2cam"))
    assert (pose.job_dir / "pose" / "sim.camera.main" / "landmarks.parquet").is_file()
    assert (pose.job_dir / "pose" / "sim.camera.oblique" / "landmarks.parquet").is_file()
    kin = run(
        pkg,
        JobParams(
            command="kinematics",
            overwrite_job_id="kin-2cam",
            extra={"pose_job_id": pose.job_id},
        ),
    )
    import pandas as pd

    df = pd.read_parquet(kin.job_dir / "kinematics" / "kinematics.parquet")
    assert validate_parquet_columns(list(df.columns)) == []
    assert len(df) >= 10


def test_run_analysis_cli_pose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    pkg = _write_pose_package(tmp_path / "pose_cli")
    monkeypatch.chdir(ROOT)
    sys.path[:0] = [
        str(ROOT / "libs" / "python" / "capture_analysis"),
        str(ROOT / "libs" / "python" / "capture_session"),
        str(ROOT / "libs" / "python" / "capture_protocol"),
    ]
    from tools.run_analysis import main

    rc = main(["pose", str(pkg)])
    assert rc == 0
