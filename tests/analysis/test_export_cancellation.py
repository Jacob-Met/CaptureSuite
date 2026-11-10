# SPDX-License-Identifier: GPL-3.0-only
"""A stopped recorded-data export cannot report a completed handoff."""

import hashlib
import json
from pathlib import Path

from capture_desktop.export_wizard import ExportOptions, run_export
from capture_protocol.generated.capture.v1.data.numeric_batch_pb2 import NumericBatch
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from mcap.writer import Writer

ROOT = Path(__file__).resolve().parents[2]


def _options(out):
    return ExportOptions(
        str(out), include_radar=False, include_video=False,
        include_emg=False, include_imu=False,
    )


def test_cancel_before_launch_does_not_create_destination(tmp_path):
    package = tmp_path / "input.mmsession"
    package.mkdir()
    out = tmp_path / "cancelled"
    code, message = run_export(
        str(package), _options(out), repo_root=ROOT, cancel=lambda: True
    )
    assert code == 130 and "cancelled" in message.lower()
    assert not out.exists()


def test_cancel_during_recorded_numeric_write_preserves_source(tmp_path):
    package = tmp_path / "input.mmsession"
    path = package / "sources/load/streams/measurements/segments/000.mcap"
    path.parent.mkdir(parents=True)
    (package / "manifest.json").write_text(json.dumps({"state": "finalized", "synthetic": True}))
    msg = NumericBatch(channel_count=8, units="N", dtype="f64")
    msg.channel_names.extend(f"load-{i}" for i in range(8))
    msg.samples.extend([1.25, -2.5, 3.0, 4.5, 5.0, 6.75, 7.0, 8.125] * 100_000)
    msg.device_time_ns.extend(i * 1_000_000 for i in range(100_000))
    schema = FileDescriptorSet()
    NumericBatch.DESCRIPTOR.file.CopyToProto(schema.file.add())
    with path.open("wb") as file:
        writer = Writer(file)
        writer.start()
        schema_id = writer.register_schema(
            "capture.v1.data.NumericBatch", "protobuf", schema.SerializeToString()
        )
        channel = writer.register_channel("load/numeric", "protobuf", schema_id)
        writer.add_message(channel, 1_000_000_000, msg.SerializeToString(), 1_000_000_000)
        writer.finish()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    out = tmp_path / "stopped"
    observed_write = []

    def cancel_after_real_write():
        writing = any(out.rglob("*.csv"))
        if writing:
            observed_write.append(True)
        return writing

    code, message = run_export(
        str(package), _options(out), repo_root=ROOT, cancel=cancel_after_real_write
    )
    assert observed_write and code == 130
    assert "Partial files" in message
    assert any(out.rglob("*.csv"))
    assert not (out / "export_manifest.json").exists()
    assert not (out / "provenance_sidecar.json").exists()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
