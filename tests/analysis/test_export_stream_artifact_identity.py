# SPDX-License-Identifier: GPL-3.0-only
"""Each admitted stream descriptor retains its own export artifacts."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _exporter():
    spec = importlib.util.spec_from_file_location(
        "stream_artifact_exporter", ROOT / "tools/export_session.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _descriptor(package, relative, doc):
    path = package / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(doc, indent=2, sort_keys=True).encode() + b"\n"
    path.write_bytes(data)
    return path, data


def _sim_descriptor(source, stream):
    return {
        "sourceId": source,
        "streamId": stream,
        "modality": "radar",
        "nominalRateHz": 30.0,
        "dataSchemaId": "radar.frame/1",
        "dataSchemaVersion": "1",
    }


def test_descriptors_with_shared_hint_keep_distinct_configuration_bodies(tmp_path):
    exporter = _exporter()
    package = tmp_path / "recording.mmsession"
    inputs = {}
    for number in (1, 2):
        source = f"sim.radar.{number}"
        stream = source + ".frame"
        relative = f"sources/{source}/streams/{stream}/stream.json"
        _, data = _descriptor(package, relative, _sim_descriptor(source, stream))
        inputs[relative] = data
    manifest = {}
    out = tmp_path / "derived"
    exporter.export_radar_mcaps(package, out, manifest)
    rows = manifest["radar"]
    assert len(rows) == 2
    assert len({row["stream_json"].casefold() for row in rows}) == 2
    for relative, data in inputs.items():
        display = Path(relative).parent.name.replace(".", "_")
        leaf = display + "--" + hashlib.sha256(relative.encode()).hexdigest()
        copied = out / "radar" / leaf / "stream.json"
        row = next(item for item in rows if item["stream_json"] == str(copied))
        assert copied.read_bytes() == data
        assert row["source_id"] == "streams"
        assert row["mcap_files"] == []
        assert row["geometry"] is None
        assert "frames_npy" not in row
        assert (package / relative).read_bytes() == data


def test_prefixed_and_legacy_layout_keep_hints_and_geometry(tmp_path):
    exporter = _exporter()
    package = tmp_path / "recording.mmsession"
    canonical, canonical_bytes = _descriptor(
        package,
        "sources/radar.control/streams/radar.control.frame/stream.json",
        _sim_descriptor("radar.control", "radar.control.frame"),
    )
    legacy, legacy_bytes = _descriptor(
        package,
        "radar.legacy/stream.json",
        {"schema": "radar.config/1", "num_rx": 1, "num_chirps": 1, "num_samples": 2},
    )
    manifest = {}
    exporter.export_radar_mcaps(package, tmp_path / "derived", manifest)
    rows = {row["source_id"]: row for row in manifest["radar"]}
    assert set(rows) == {"radar.control.frame", "radar.legacy"}
    assert Path(rows["radar.control.frame"]["stream_json"]).read_bytes() == canonical_bytes
    assert Path(rows["radar.legacy"]["stream_json"]).read_bytes() == legacy_bytes
    assert rows["radar.control.frame"]["geometry"] is None
    assert rows["radar.legacy"]["geometry"] == {
        "num_rx": 1, "num_chirps": 1, "num_samples": 2, "bytes_per_frame": 4
    }
    assert canonical.read_bytes() == canonical_bytes
    assert legacy.read_bytes() == legacy_bytes


@pytest.mark.parametrize(
    ("stream", "display"),
    [
        ("frame", "frame"),
        ("CON", "CON"),
        ("a.b <literal>", "a_b__literal_"),
        ("café-Δ", "caf_-_"),
        ("a" * 60, "a" * 32),
    ],
)
def test_portable_bounded_display_keeps_full_relative_identity(stream, display):
    exporter = _exporter()
    relative = Path("sources/device/streams") / stream / "stream.json"
    actual = exporter._radar_export_dirname(relative)
    assert actual == (
        display + "--" + hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()
    )
    assert len(actual) <= 32 + 2 + 64
    assert set(actual) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")


def test_case_and_unicode_distinctions_remain_in_the_digest():
    exporter = _exporter()
    relatives = [
        Path("sources/Room/streams/frame/stream.json"),
        Path("sources/room/streams/frame/stream.json"),
        Path("sources/café/streams/frame/stream.json"),
        Path("sources/cafe\u0301/streams/frame/stream.json"),
    ]
    assert len({exporter._radar_export_dirname(path).casefold() for path in relatives}) == 4


@pytest.mark.parametrize("array_support", [None, object()])
def test_duplicate_casefolded_plan_fails_before_copy_or_decode(tmp_path, monkeypatch, array_support):
    exporter = _exporter()
    package = tmp_path / "recording.mmsession"
    for number in (1, 2):
        source = f"sim.radar.{number}"
        stream = source + ".frame"
        path, _ = _descriptor(
            package, f"sources/{source}/streams/{stream}/stream.json",
            _sim_descriptor(source, stream),
        )
        (path.parent / "segments").mkdir()
        (path.parent / "segments/0001.mcap").write_bytes(b"must not be decoded")
    monkeypatch.setattr(exporter, "np", array_support)
    # Force an allocation collision, rather than pretend to create a SHA256 collision.
    monkeypatch.setattr(
        exporter, "_radar_export_dirname",
        lambda relative: "Same" if relative.parts[1] == "sim.radar.1" else "same",
    )
    writes = []
    monkeypatch.setattr(exporter.shutil, "copy2", lambda *args, **kwargs: writes.append(args))
    out = tmp_path / "derived"
    manifest = {}
    with pytest.raises(exporter.ExportOutputError, match="destination collision") as error:
        exporter.export_radar_mcaps(package, out, manifest)
    assert "sources/sim.radar.1/streams/sim.radar.1.frame/stream.json" in str(error.value)
    assert "sources/sim.radar.2/streams/sim.radar.2.frame/stream.json" in str(error.value)
    assert writes == []
    assert not (out / "radar").exists()
    assert not manifest.get("radar")


def test_unselected_descriptors_and_malformed_json_remain_ignored(tmp_path):
    exporter = _exporter()
    package = tmp_path / "recording.mmsession"
    _, valid = _descriptor(
        package, "sources/sim.radar.1/streams/sim.radar.1.frame/stream.json",
        _sim_descriptor("sim.radar.1", "sim.radar.1.frame"),
    )
    invalid = package / "sources/sim.radar.bad/streams/frame/stream.json"
    invalid.parent.mkdir(parents=True)
    invalid.write_text("{ invalid json", encoding="utf-8")
    _descriptor(
        package, "sources/camera/streams/front/stream.json",
        {"sourceId": "camera", "streamId": "front", "modality": "video"},
    )
    manifest = {}
    exporter.export_radar_mcaps(package, tmp_path / "derived", manifest)
    assert len(manifest["radar"]) == 1
    assert Path(manifest["radar"][0]["stream_json"]).read_bytes() == valid
    assert invalid.read_text(encoding="utf-8") == "{ invalid json"


def test_existing_package_exports_exclusion_is_preserved(tmp_path):
    exporter = _exporter()
    package = tmp_path / "recording.mmsession"
    _, valid = _descriptor(
        package, "sources/sim.radar.1/streams/sim.radar.1.frame/stream.json",
        _sim_descriptor("sim.radar.1", "sim.radar.1.frame"),
    )
    _descriptor(
        package, "exports/old/radar.previous/stream.json",
        _sim_descriptor("sim.radar.previous", "sim.radar.previous.frame"),
    )
    manifest = {}
    exporter.export_radar_mcaps(package, tmp_path / "derived", manifest)
    assert len(manifest["radar"]) == 1
    assert Path(manifest["radar"][0]["stream_json"]).read_bytes() == valid
