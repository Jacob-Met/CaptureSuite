# SPDX-License-Identifier: GPL-3.0-only
"""Export selections through real protobuf MCAP and the native Qt wizard."""

from __future__ import annotations

import errno
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from capture_protocol.generated.capture.v1.data import emg_batch_pb2, imu_frame_pb2
from mcap.writer import Writer

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("radar", "video", "emg", "imu")


def _hash_files(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _message(kind: str, sequence: int):
    if kind == "imu":
        message = imu_frame_pb2.ImuFrame()
        sensor = message.sensors.add()
        sensor.sensor_id = "sensor-17"
        sensor.accel_z = 8.5
    else:
        message = emg_batch_pb2.EmgBatch()
        message.channel_ids.extend(["channel-A", "channel-B"])
        message.sample_count = 3
        message.samples_f32_le = struct.pack("<6f", 1, 2, 3, -1, -2, -3)
    message.timing.sequence_number = sequence
    message.timing.session_time_ns = 7_000_000_003 + sequence
    return message


def _write_mcap(path: Path, kinds: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        writer = Writer(stream)
        writer.start(profile="", library="capturesuite-export-receiving")
        for index, kind in enumerate(kinds):
            schema_name = "imu.frame/1" if kind == "imu" else "emg.batch/1"
            schema = writer.register_schema(schema_name, "protobuf", b"")
            channel = writer.register_channel(f"source/{kind}", "protobuf", schema)
            message = _message(kind, 41 + index)
            writer.add_message(
                channel_id=channel,
                log_time=message.timing.session_time_ns,
                publish_time=message.timing.session_time_ns,
                data=message.SerializeToString(),
            )
        writer.finish()


@pytest.fixture
def package(tmp_path: Path) -> Path:
    root = tmp_path / "synthetic.mmsession"
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps({"state": "finalized", "synthetic": True}), encoding="utf-8"
    )
    events = root / "events"
    events.mkdir()
    (events / "checkpoints.json").write_text(
        json.dumps([{"id": "cp-1", "sessionTimeNs": 7_000_000_044}]), encoding="utf-8"
    )
    return root


def _export(package: Path, out: Path, selected: tuple[str, ...] | None):
    command = [sys.executable, str(ROOT / "tools/export_session.py"), str(package), str(out)]
    if selected is not None:
        command.extend(["--modalities", ",".join(selected)])
    command.append("--verify")
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)


def _assert_selected(out: Path, selected: tuple[str, ...]) -> dict:
    manifest = json.loads((out / "export_manifest.json").read_text(encoding="utf-8"))
    for kind in KINDS:
        assert bool(manifest[kind]) == (kind in selected), (kind, manifest)
        if kind not in selected:
            assert not (out / kind).exists(), kind
    for kind in selected:
        entry = manifest[kind][0]
        assert entry["message_count"] == 1
        rows = (out / entry["summary"]).read_text(encoding="utf-8").splitlines()
        assert len(rows) == 1
        row = json.loads(rows[0])
        assert row["session_time_ns"] == 7_000_000_003 + row["sequence"]
        if kind == "imu":
            assert row["sensors"] == ["sensor-17"]
            assert row["sensor_count"] == 1
            assert row["accel_z0"] == 8.5
        else:
            assert row["channel_ids"] == ["channel-A", "channel-B"]
            assert row["sample_count"] == 3
            assert row["bytes"] == 24
    return manifest


@pytest.mark.parametrize("selected", [("imu",), ("emg",), ("emg", "imu")])
def test_real_mcap_selection_preserves_input_and_timestamps(package: Path, selected) -> None:
    _write_mcap(package / "sources/device-A/streams/one/segments/000.mcap", ("emg",))
    _write_mcap(package / "sources/device-B/streams/two/segments/000.mcap", ("imu",))
    before = _hash_files(package)
    out = package.parent / "selected output 雪"
    result = _export(package, out, selected)
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = _assert_selected(out, selected)
    assert manifest["events"]["checkpoints.json"][0]["id"] == "cp-1"
    assert _hash_files(package) == before


def test_unicode_destination_with_legacy_pipe_encoding(package: Path, monkeypatch) -> None:
    """A Windows-style output pipe must not fail after writing valid export files."""
    _write_mcap(package / "sources/device-17/streams/mixed/segments/000.mcap", ("emg", "imu"))
    before = _hash_files(package)
    out = package.parent / "selected output 雪"
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252:strict")
    result = _export(package, out, ("emg", "imu"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "wrote " in result.stdout
    assert r"\u96ea" in result.stdout
    _assert_selected(out, ("emg", "imu"))
    assert _hash_files(package) == before


@pytest.mark.parametrize("layout", ["separate-streams", "multiplexed"])
@pytest.mark.parametrize("selected", [("imu",), ("emg", "imu")])
def test_selected_modality_can_follow_another_schema(package: Path, layout, selected) -> None:
    """A source's first message or name cannot determine all of its modalities."""
    source = package / "sources/device-17/streams"
    if layout == "multiplexed":
        _write_mcap(source / "mixed/segments/000.mcap", ("emg", "imu"))
    else:
        _write_mcap(source / "a/segments/000.mcap", ("emg",))
        _write_mcap(source / "b/segments/000.mcap", ("imu",))
    before = _hash_files(package)
    out = package.parent / "selected"
    result = _export(package, out, selected)
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_selected(out, selected)
    assert _hash_files(package) == before


def test_native_wizard_selection_and_requested_actual_sidecar(package: Path, qapp) -> None:
    from capture_desktop.export_wizard import ExportWizard, run_export

    _write_mcap(package / "sources/device-A/streams/one/segments/000.mcap", ("emg",))
    _write_mcap(package / "sources/device-B/streams/two/segments/000.mcap", ("imu",))
    before = _hash_files(package)
    out = package.parent / "wizard export"
    wizard = ExportWizard(str(package), default_out=str(out))
    try:
        wizard._radar.setChecked(True)  # Requested but absent: provenance must say so.
        wizard._video.setChecked(False)
        wizard._emg.setChecked(False)
        wizard._imu.setChecked(True)
        wizard._accept()
        assert wizard.result() == wizard.DialogCode.Accepted
        code, tail = run_export(str(package), wizard.options, repo_root=ROOT)
        assert code == 0, tail
        sidecar = json.loads((out / "provenance_sidecar.json").read_text(encoding="utf-8"))
        assert sidecar["streams"] == dict(radar=True, video=False, emg=False, imu=True)
        assert sidecar["actualStreams"] == dict(radar=False, video=False, emg=False, imu=True)
        assert not (out / "emg").exists()
        assert not (out / "video").exists()
        assert _hash_files(package) == before
    finally:
        wizard.close()
        wizard.deleteLater()
        qapp.processEvents()


def test_reused_destination_does_not_leave_unselected_streams(package: Path) -> None:
    _write_mcap(package / "sources/device-A/streams/one/segments/000.mcap", ("emg",))
    _write_mcap(package / "sources/device-B/streams/two/segments/000.mcap", ("imu",))
    out = package.parent / "selected"
    first = _export(package, out, ("imu",))
    assert first.returncode == 0, first.stdout + first.stderr
    before = _hash_files(out)
    second = _export(package, out, ("emg",))
    assert second.returncode != 0, "A second selection must not mix stale outputs into an export"
    assert "empty" in (second.stdout + second.stderr).lower()
    assert _hash_files(out) == before


def test_existing_empty_destination_is_supported(package: Path) -> None:
    _write_mcap(package / "sources/device-A/streams/one/segments/000.mcap", ("emg",))
    out = package.parent / "empty folder"
    out.mkdir()
    result = _export(package, out, ("emg",))
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_selected(out, ("emg",))


@pytest.mark.parametrize("contents", ["unrelated-file", "empty-subfolder"])
def test_existing_destination_contents_are_preserved(package: Path, contents) -> None:
    _write_mcap(package / "sources/device-A/streams/one/segments/000.mcap", ("emg",))
    out = package.parent / "existing folder"
    out.mkdir()
    if contents == "empty-subfolder":
        (out / "other-work").mkdir()
    else:
        (out / "notes.txt").write_text("Do not replace this work.", encoding="utf-8")
    before = _hash_files(out)
    source_before = _hash_files(package)
    result = _export(package, out, ("emg",))
    assert result.returncode != 0
    assert "empty" in (result.stdout + result.stderr).lower()
    assert _hash_files(out) == before
    assert _hash_files(package) == source_before
    assert not (out / "emg").exists()
    assert not (out / "export_manifest.json").exists()


@pytest.mark.parametrize("operation", ["mkdir", "open", "write", "close"])
def test_output_failure_is_fatal_with_another_selected_stream(
    package: Path, monkeypatch, capsys, operation
) -> None:
    import export_session

    _write_mcap(package / "sources/device-A/streams/one/segments/000.mcap", ("emg",))
    _write_mcap(package / "sources/device-B/streams/two/segments/000.mcap", ("imu",))
    before = _hash_files(package)
    out = package.parent / "output-fault"
    dest = out / "imu/device-B"
    real_mkdir = Path.mkdir
    real_open = Path.open

    def failed_mkdir(path, *args, **kwargs):
        if path == dest:
            raise PermissionError(errno.EACCES, "synthetic output directory denied")
        return real_mkdir(path, *args, **kwargs)

    class FailedOutput:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def write(self, value):
            if operation == "write":
                raise OSError(errno.ENOSPC, "synthetic output full")
            return self.stream.write(value)

        def __exit__(self, *args):
            result = self.stream.__exit__(*args)
            if operation == "close":
                raise OSError(errno.ENOSPC, "synthetic output flush failed")
            return result

    def failed_open(path, *args, **kwargs):
        if path != dest / "frames.jsonl":
            return real_open(path, *args, **kwargs)
        if operation == "open":
            raise PermissionError(errno.EACCES, "synthetic output file denied")
        return FailedOutput(real_open(path, *args, **kwargs))

    if operation == "mkdir":
        monkeypatch.setattr(Path, "mkdir", failed_mkdir)
    else:
        monkeypatch.setattr(Path, "open", failed_open)
    code = export_session.main(
        [str(package), str(out), "--modalities", "emg,imu", "--verify"]
    )
    assert code == 1
    assert "write" in capsys.readouterr().err.lower()
    assert not (out / "export_manifest.json").exists()
    assert _hash_files(package) == before


@pytest.mark.parametrize("operation", ["open", "iterate"])
def test_existing_input_read_failure_policy_is_preserved(package: Path, monkeypatch, operation):
    import export_session
    import mcap.reader

    unreadable = package / "sources/device-A/streams/one/segments/000.mcap"
    _write_mcap(unreadable, ("emg",))
    _write_mcap(package / "sources/device-B/streams/two/segments/000.mcap", ("imu",))
    before = _hash_files(package)
    real_open = Path.open
    real_reader = mcap.reader.make_reader

    def failed_open(path, *args, **kwargs):
        if path == unreadable:
            raise PermissionError(errno.EACCES, "synthetic input denied")
        return real_open(path, *args, **kwargs)

    def failed_messages():
        raise OSError(errno.EIO, "synthetic input read failed")

    def failed_reader(stream, *args, **kwargs):
        if stream.name == str(unreadable):
            return SimpleNamespace(iter_messages=failed_messages)
        return real_reader(stream, *args, **kwargs)

    with monkeypatch.context() as patch:
        if operation == "open":
            patch.setattr(Path, "open", failed_open)
        else:
            patch.setattr(mcap.reader, "make_reader", failed_reader)
        out = package.parent / "read-fault"
        code = export_session.main(
            [str(package), str(out), "--modalities", "emg,imu", "--verify"]
        )
    assert code == 0
    _assert_selected(out, ("imu",))
    assert _hash_files(package) == before
