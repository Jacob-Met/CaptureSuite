# SPDX-License-Identifier: GPL-3.0-only
"""External numeric CSV handoff through real protobuf MCAP and native export."""

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from capture_protocol.generated.capture.v1.data.numeric_batch_pb2 import NumericBatch
from mcap.writer import Writer

ROOT = Path(__file__).resolve().parents[2]


def make_package(root: Path, *, bad=False) -> Path:
    source = root / "sources" / "strain.sensor"
    segments = source / "streams" / "force" / "segments"
    segments.mkdir(parents=True)
    (root / "manifest.json").write_text('{"state":"finalized","synthetic":true}')
    (segments.parent / "stream.json").write_text(
        '{"data_schema_id":"generic.numeric_batch/1","units":"N"}'
    )
    (source / "health").mkdir()
    (source / "health/gaps.jsonl").write_text(
        '{"startSessionNs":"7000000021","endSessionNs":"7000000041","reason":"disconnect"}\n'
    )
    for segment in range(2):
        with (segments / f"{segment:03}.mcap").open("wb") as stream:
            writer = Writer(stream)
            writer.start()
            schema = writer.register_schema("capture.v1.data.NumericBatch", "protobuf", b"")
            channel = writer.register_channel("force/strain", "protobuf", schema)
            msg = NumericBatch(
                channel_count=2,
                channel_names=["left, N", "right 雪"],
                units="N",
                dtype="f64",
                samples=[1.25, -3.5, 5.75, 9.0],
                device_time_ns=[9007199254740993, 9007199254741013] if segment == 0 else [],
            )
            if bad:
                msg.samples.append(1)
            writer.add_message(
                channel,
                7000000001 + segment * 100,
                msg.SerializeToString(),
                8000000001 + segment * 100,
            )
            writer.finish()
    return root


def export(package: Path, out: Path):
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/export_session.py"),
            str(package),
            str(out),
            "--modalities",
            "numeric",
            "--verify",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


def hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


def test_exact_samples_native_clocks_gaps_and_missing_time(tmp_path):
    package = make_package(tmp_path / "recording.mmsession")
    before = hashes(package)
    out = tmp_path / "external analysis"
    result = export(package, out)
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((out / "export_manifest.json").read_text())
    assert manifest["modalities"] == ["numeric"]
    (entry,) = manifest["numeric"]
    assert entry["frame_count"] == 4 and entry["row_count"] == 8
    assert entry["frames_without_device_time"] == 2
    with (out / entry["samples_csv"]).open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["value"] for r in rows] == ["1.25", "-3.5", "5.75", "9.0"] * 2
    assert rows[0]["channel_name"] == "left, N"
    assert rows[1]["channel_name"] == "right 雪"
    assert rows[0]["device_time_ns"] == "9007199254740993"
    assert rows[2]["session_estimate_ns"] == "7000000021"
    assert rows[0]["mcap_publish_time_ns"] == "8000000001"
    assert rows[4]["device_time_ns"] == rows[4]["session_estimate_ns"] == ""
    assert rows[4]["time_basis"] == "unavailable"
    assert (out / entry["provenance"][-1]).read_bytes() == (
        package / "sources/strain.sensor/health/gaps.jsonl"
    ).read_bytes()
    assert hashes(package) == before
    assert export(package, out).returncode != 0


def test_malformed_selected_payload_cannot_publish_success_manifest(tmp_path):
    package = make_package(tmp_path / "bad.mmsession", bad=True)
    out = tmp_path / "bad-out"
    result = export(package, out)
    assert result.returncode != 0
    assert "whole frames" in result.stderr
    assert not (out / "export_manifest.json").exists()


def test_native_wizard_selects_numeric_and_records_actual_output(tmp_path, qapp):
    from capture_desktop.export_wizard import ExportWizard, run_export

    package = make_package(tmp_path / "native.mmsession")
    out = tmp_path / "native-out"
    wizard = ExportWizard(str(package), default_out=str(out))
    for box in (wizard._radar, wizard._video, wizard._emg, wizard._imu):
        box.setChecked(False)
    wizard._accept()
    code, tail = run_export(str(package), wizard.options, repo_root=ROOT)
    assert code == 0, tail
    sidecar = json.loads((out / "provenance_sidecar.json").read_text())
    assert sidecar["actualStreams"]["numeric"]
    assert not any(sidecar["actualStreams"][k] for k in ("imu", "emg", "video", "radar"))
    wizard.close()


def test_standalone_entry_dispatches_recorded_sample_export(tmp_path):
    package = make_package(tmp_path / "entry.mmsession")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/analysis_bundle_entry.py"),
            "export-session",
            str(package),
            str(tmp_path / "entry-out"),
            "--modalities",
            "numeric",
            "--verify",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        env=__import__("os").environ
        | {
            "PYTHONPATH": ":".join(
                str(ROOT / p)
                for p in (
                    "libs/python/capture_analysis",
                    "libs/python/capture_session",
                    "libs/python/capture_protocol",
                )
            )
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
