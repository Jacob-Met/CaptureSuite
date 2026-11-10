# SPDX-License-Identifier: GPL-3.0-only
"""Recorded metadata context must not invent sample counts or hide unknown data."""

import pytest
from capture_session.export_inventory import inspect_export_inventory
from mcap.writer import Writer
from test_numeric_sample_export import make_package


def test_numeric_rotation_counts_messages_and_preserves_originals(tmp_path):
    package = make_package(tmp_path / "numbers.mmsession")
    inventory = inspect_export_inventory(package)
    assert not inventory.incomplete
    numeric = inventory.kinds["numeric"]
    assert len(numeric.streams) == 1
    assert numeric.messages == 2
    assert len(numeric.files) == 2
    assert numeric.sources == {"strain.sensor"}
    assert not inventory.kinds["emg"].streams


def test_unreadable_index_leaves_availability_unknown(tmp_path):
    package = make_package(tmp_path / "numbers.mmsession")
    path = package / "sources/unknown/streams/a/segments/bad.mcap"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"unreadable")
    inventory = inspect_export_inventory(package)
    assert inventory.incomplete
    assert inventory.kinds["numeric"].messages == 2


def test_unknown_schema_does_not_masquerade_as_absent(tmp_path):
    root = tmp_path / "unknown.mmsession"
    path = root / "sources/opaque/segments/data.mcap"
    path.parent.mkdir(parents=True)
    with path.open("wb") as fh:
        writer = Writer(fh)
        writer.start()
        schema = writer.register_schema("unrecognized/2", "protobuf", b"")
        channel = writer.register_channel("unrecognized", "protobuf", schema)
        writer.add_message(channel, 100, b"opaque", 100)
        writer.finish()
    inventory = inspect_export_inventory(root)
    assert inventory.incomplete
    assert not inventory.kinds["numeric"].streams


def test_dialog_defaults_to_present_data_and_explains_counts(tmp_path, qapp):
    from capture_desktop.export_wizard import ExportWizard

    package = make_package(tmp_path / "research.mmsession")
    dialog = ExportWizard(str(package), default_out=str(tmp_path / "out"))
    assert dialog._numeric.isChecked() and dialog._numeric.isEnabled()
    assert not dialog._emg.isChecked() and not dialog._emg.isEnabled()
    assert dialog._inventory.kinds["numeric"].messages == 2
    assert "uncalibrated" in dialog._timing_note.text()
    assert "many samples" in dialog._inventory_note.text()
    dialog._numeric.setChecked(False)
    assert not dialog._export_button.isEnabled()
    dialog._accept()
    assert dialog.result() == 0
    dialog.close()


def test_incomplete_dialog_keeps_explicit_choices_available(tmp_path, qapp):
    from capture_desktop.export_wizard import ExportWizard

    package = tmp_path / "unknown.mmsession"
    package.mkdir()
    dialog = ExportWizard(str(package))
    assert all(box.isEnabled() for box in dialog._data_boxes)
    assert "Choices remain available" in dialog._inventory_note.text()
    dialog.close()

@pytest.mark.parametrize("canonical", [False, True])
def test_recorded_emg_and_imu_inventory_drives_actual_export(tmp_path, qapp, canonical):
    """Both recorded schema conventions must be selectable and export real rows."""
    import json

    from capture_desktop.export_wizard import ExportWizard, run_export
    from test_export_selection_mcap import _write_mcap

    package = tmp_path / "sensors.mmsession"
    _write_mcap(
        package / "sources/device-A/streams/mixed/segments/000.mcap",
        ("emg", "imu"),
        canonical=canonical,
    )
    output = tmp_path / "selected"
    dialog = ExportWizard(str(package), default_out=str(output))
    assert not dialog._inventory.incomplete
    for kind in ("emg", "imu"):
        assert dialog._inventory.kinds[kind].messages == 1
        assert len(dialog._inventory.kinds[kind].streams) == 1
        assert getattr(dialog, "_" + kind).isChecked()
    for kind in ("numeric", "video", "radar"):
        assert not getattr(dialog, "_" + kind).isChecked()
    dialog._accept()
    code, detail = run_export(str(package), dialog.options)
    assert code == 0, detail
    for kind, filename in (("emg", "batches.jsonl"), ("imu", "frames.jsonl")):
        rows = (output / kind / "device-A" / filename).read_text().splitlines()
        assert len(rows) == 1
        assert json.loads(rows[0])["session_time_ns"] > 0
    dialog.close()
