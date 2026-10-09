# SPDX-License-Identifier: GPL-3.0-only
"""Whole-session video artifacts retain package-relative segment identity."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _exporter():
    spec = importlib.util.spec_from_file_location(
        "whole_video_identity_exporter", ROOT / "tools/export_session.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _segment(package: Path, relative: str, content: bytes) -> Path:
    path = package / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_fallback_preserves_same_basename_across_sources_and_streams(tmp_path, monkeypatch):
    exporter = _exporter()
    monkeypatch.setattr(exporter.shutil, "which", lambda _name: None)
    package = tmp_path / "recorded.mmsession"
    inputs = {
        "sources/sim.left/streams/front/segments/0001.mkv": b"left front",
        "sources/sim.left/streams/back/segments/0001.mkv": b"left back",
        "sources/sim.right/streams/front/segments/0001.mkv": b"right front",
        "sources/sim.right/streams/front/segments/0002.mkv": b"right second",
    }
    for relative, content in inputs.items():
        _segment(package, relative, content)
    metadata = package / "sources/sim.left/streams/front/stream.json"
    metadata.write_text(
        '{"sourceId":"sim.left <literal>","streamId":"front & camera"}',
        encoding="utf-8",
    )
    metadata_before = metadata.read_bytes()
    out = tmp_path / "export"
    manifest = {}
    exporter.export_video(package, out, manifest)
    rows = manifest["video"]
    assert len(rows) == len(inputs)
    assert len({row["mkv_copy"].casefold() for row in rows}) == len(inputs)
    for row in rows:
        relative = Path(row["mkv"]).as_posix()
        copied = Path(row["mkv_copy"])
        assert copied.parent == out / "video"
        assert copied.read_bytes() == inputs[relative]
        assert copied.name == (
            Path(relative).stem + "--"
            + hashlib.sha256(relative.encode("utf-8")).hexdigest() + ".mkv"
        )
        assert row["mp4"] is None
        assert row["source_id"] == "camera"
        assert "ok" not in row
        assert row["note"] == "ffmpeg not on PATH; copied MKV instead of MP4"
    assert metadata.read_bytes() == metadata_before
    for relative, content in inputs.items():
        assert (package / relative).read_bytes() == content


@pytest.mark.parametrize(
    ("stem", "display"),
    [
        ("0001", "0001"),
        ("CON", "CON"),
        ("A B.<literal>", "A_B__literal_"),
        ("café-Δ", "caf_-_"),
        ("a" * 60, "a" * 32),
    ],
)
def test_display_stem_is_bounded_and_portable_without_losing_path_identity(stem, display):
    exporter = _exporter()
    relative = Path("sources/sim.one/streams/front/segments") / (stem + ".mkv")
    actual = exporter._video_export_basename(relative)
    assert actual == display + "--" + hashlib.sha256(relative.as_posix().encode("utf-8")).hexdigest()
    assert len(actual) <= 32 + 2 + 64
    assert set(actual) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")


def test_case_and_unicode_normalization_distinctions_remain_in_identity():
    exporter = _exporter()
    relatives = [
        Path("sources/Room/streams/front/segments/0001.mkv"),
        Path("sources/room/streams/front/segments/0001.mkv"),
        Path("sources/café/streams/front/segments/0001.mkv"),
        Path("sources/cafe\u0301/streams/front/segments/0001.mkv"),
    ]
    names = [exporter._video_export_basename(path) for path in relatives]
    assert len({name.casefold() for name in names}) == 4


def test_external_camera_named_ancestor_does_not_change_artifact_or_source_hint(tmp_path, monkeypatch):
    exporter = _exporter()
    monkeypatch.setattr(exporter.shutil, "which", lambda _name: None)
    relative = "sources/camera.actual/streams/front/segments/0001.mkv"
    observed = []
    for parent in ["PlainArchive", "CameraExports"]:
        package = tmp_path / parent / "session.mmsession"
        _segment(package, relative, b"same recording")
        manifest = {}
        exporter.export_video(package, tmp_path / (parent + "-out"), manifest)
        row = manifest["video"][0]
        observed.append((row["source_id"], Path(row["mkv_copy"]).name, row["mkv"]))
    assert observed[0] == observed[1]
    assert observed[0][0] == "camera.actual"


@pytest.mark.parametrize("ffmpeg", [None, "unused-ffmpeg"])
def test_duplicate_case_insensitive_plan_is_rejected_before_any_video_writer(tmp_path, monkeypatch, ffmpeg):
    exporter = _exporter()
    package = tmp_path / "session.mmsession"
    _segment(package, "sources/one/streams/front/segments/0001.mkv", b"one")
    _segment(package, "sources/two/streams/front/segments/0001.mkv", b"two")
    monkeypatch.setattr(exporter.shutil, "which", lambda _name: ffmpeg)
    # Exercise the explicit duplicate-plan defense, not a pretend SHA collision.
    monkeypatch.setattr(
        exporter, "_video_export_basename",
        lambda relative: "Duplicate" if relative.parts[1] == "one" else "duplicate",
    )
    writes = []
    monkeypatch.setattr(exporter.shutil, "copy2", lambda *args, **kwargs: writes.append(args))
    monkeypatch.setattr(exporter.subprocess, "run", lambda *args, **kwargs: writes.append(args))
    out = tmp_path / "export"
    manifest = {}
    with pytest.raises(exporter.ExportOutputError, match="destination collision") as failure:
        exporter.export_video(package, out, manifest)
    assert "sources/one/streams/front/segments/0001.mkv" in str(failure.value)
    assert "sources/two/streams/front/segments/0001.mkv" in str(failure.value)
    assert writes == []
    assert not (out / "video").exists()
    assert not manifest.get("video")


def test_prior_package_exports_are_not_rediscovered(tmp_path, monkeypatch):
    exporter = _exporter()
    monkeypatch.setattr(exporter.shutil, "which", lambda _name: None)
    package = tmp_path / "session.mmsession"
    _segment(package, "sources/sim.one/streams/front/segments/0001.mkv", b"raw")
    _segment(package, "exports/old/video/0001.mkv", b"previous export")
    manifest = {}
    exporter.export_video(package, tmp_path / "out", manifest)
    assert len(manifest["video"]) == 1
    assert Path(manifest["video"][0]["mkv_copy"]).read_bytes() == b"raw"

@pytest.mark.parametrize(
    ("external_parent", "package_name"),
    [
        ("ordinary", "recorded.mmsession"),
        ("exports", "recorded.mmsession"),
        ("ordinary", "exports"),
        ("exports", "exports"),
    ],
)
def test_only_package_internal_exports_components_exclude_video(
    tmp_path, monkeypatch, external_parent, package_name
):
    exporter = _exporter()
    monkeypatch.setattr(exporter.shutil, "which", lambda _name: None)
    package = tmp_path / external_parent / package_name
    relative = "sources/sim.one/streams/front/segments/0001.mkv"
    inputs = {
        relative: b"selected raw recording",
        "exports/old/video/0001.mkv": b"previous package export",
        "sources/sim.one/streams/exports/segments/0001.mkv": b"excluded internal component",
    }
    for path, content in inputs.items():
        _segment(package, path, content)
    out = tmp_path / "derived"
    manifest = {}
    exporter.export_video(package, out, manifest)
    rows = manifest.get("video", [])
    assert len(rows) == 1
    row = rows[0]
    assert Path(row["mkv"]).as_posix() == relative
    assert row["source_id"] == "camera"
    assert row["mp4"] is None
    copied = Path(row["mkv_copy"])
    assert copied.parent == out / "video"
    assert copied.name == (
        "0001--" + hashlib.sha256(relative.encode("utf-8")).hexdigest() + ".mkv"
    )
    assert copied.read_bytes() == inputs[relative]
    assert {path.relative_to(package).as_posix(): path.read_bytes()
            for path in package.rglob("*") if path.is_file()} == inputs
