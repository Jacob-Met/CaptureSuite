# SPDX-License-Identifier: GPL-3.0-only
"""Independent user-outcome receiving for the selected-figure bundle workflow.

Fixtures are independently authored, valid PNGs and capture.analysis_job/1 files.
No capture device, real session, account, or original job is modified.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QLabel, QListWidget, QPushButton


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png(seed: int, padding: int = 0) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    pixels = b"".join(
        b"\0" + bytes(((seed + row * 17 + col * 31) % 256 for col in range(12)))
        for row in range(2)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 3, 2, 8, 6, 0, 0, 0))
        + chunk(b"tEXt", b"original-note\0" + b"x" * padding)
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def saved_job(root: Path, name: str = "review-A", *, padding: int = 0):
    package = root / f"{name}.mmsession"
    job = package / "processing" / "jobs" / name
    (job / "figures" / "radar").mkdir(parents=True)
    (package / "sources").mkdir()
    (package / "sources" / "raw.bin").write_bytes(b"immutable authored raw control")
    params = {"command": "all", "gapPolicy": "split", "extra": {"caption": "EMG α", "window": [17, 29]}}
    params_bytes = (json.dumps(params, ensure_ascii=False, indent=3) + "\n").encode()
    files = {
        "params.json": params_bytes,
        "figures/EMG_α.png": png(19, padding),
        "figures/radar/detail.png": png(101),
        "figures/timing.png": png(211),
    }
    for rel, data in files.items():
        (job / rel).write_bytes(data)
    manifest = {
        "schemaId": "capture.analysis_job/1",
        "jobId": name,
        "createdUtc": "2026-10-08T00:00:00Z",
        "captureAnalysisVersion": "receiving-fixture",
        "sessionId": f"authored-session-{name}",
        "packagePath": "C:\\original workstation\\retained-session.mmsession",
        "packageState": "SEALED",
        "manifestSha256": "1" * 64,
        "gapPolicy": "split",
        "paramsDigest": digest(json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()),
        "tooling": {"captureAnalysis": "original-version", "platform": "original-platform"},
        "warnings": ["Authored gap warning; do not erase", "<literal provenance> α"],
        "errors": [],
        "status": "completed_with_warnings",
        "outputs": [
            {"relativePath": rel, "bytes": len(data), "sha256": digest(data), "kind": "params" if rel == "params.json" else "figure"}
            for rel, data in files.items()
        ] + [{"relativePath": "job_manifest.json", "bytes": 123, "sha256": "0" * 64, "kind": "manifest"}],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    (job / "job_manifest.json").write_bytes(manifest_bytes)
    files["job_manifest.json"] = manifest_bytes
    return package, job, files, manifest


def file_tree(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): digest(p.read_bytes()) for p in root.rglob("*") if p.is_file()}


def api():
    from capture_desktop import analysis_figure_export

    return analysis_figure_export


def assert_bundle(path: Path, selected, originals, original_manifest):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {*selected, "manifest.json", "source/job_manifest.json", "source/params.json"}
        for rel in selected:
            assert archive.read(rel) == originals[rel]
        for rel in ("job_manifest.json", "params.json"):
            assert archive.read(f"source/{rel}") == originals[rel]
        doc = json.loads(archive.read("manifest.json"))
        assert doc["schemaId"] == "capture.analysis_figure_bundle/1"
        for key in ("jobId", "sessionId", "paramsDigest"):
            assert doc[key] == original_manifest[key]
        assert {x["path"] for x in doc["figures"]} == set(selected)
        for row in doc["figures"] + doc["sourceFiles"]:
            data = archive.read(row["path"])
            assert row["bytes"] == len(data)
            assert row["sha256"] == digest(data)
        actual_manifest_digest = next(x["sha256"] for x in doc["sourceFiles"] if x["path"] == "source/job_manifest.json")
        assert actual_manifest_digest != original_manifest["outputs"][-1]["sha256"]
        assert json.loads(archive.read("source/job_manifest.json")) == original_manifest


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def wait_for(qapp, predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        qapp.processEvents()
        QTest.qWait(5)
    assert predicate(), "Native Qt workflow did not reach the expected state"
    qapp.processEvents()


def button(parent, text):
    matches = [b for b in parent.findChildren(QPushButton) if text.casefold() in b.text().replace("&", "").casefold()]
    assert len(matches) == 1, f"Expected exactly one {text!r} button; got {[b.text() for b in matches]}"
    return matches[0]


def test_native_gallery_exposes_selected_figure_export(qapp):
    from capture_desktop.widgets_analysis_plots import FigureGallery

    gallery = FigureGallery()
    gallery.show()
    qapp.processEvents()
    controls = [b for b in gallery.findChildren(QPushButton) if "export" in b.text().casefold()]
    assert controls, "Visible pre-feature gallery has no selected-figure export control"
    assert not controls[0].isEnabled(), "Empty gallery must not export a stale job"
    gallery.close()


def test_selected_original_bytes_and_recorded_provenance(tmp_path):
    package, job, originals, manifest = saved_job(tmp_path)
    before = file_tree(package)
    selected = ("figures/timing.png", "figures/EMG_α.png")
    source = api().load_figure_source(job)
    # Mutating a decoded metadata view must not change retained provenance.
    source.manifest["warnings"].clear()
    result = api().export_figure_bundle(source, selected, tmp_path / "selected.zip")
    assert result.figure_count == 2
    assert_bundle(result.path, selected, originals, manifest)
    assert file_tree(package) == before


@pytest.mark.parametrize("relative", ["job_manifest.json", "params.json", "figures/EMG_α.png"])
def test_changed_source_refusal_preserves_previous_export_and_allows_retry(tmp_path, relative):
    package, job, originals, manifest = saved_job(tmp_path)
    source = api().load_figure_source(job)
    destination = tmp_path / "existing.zip"
    previous = b"original user's prior export\n"
    destination.write_bytes(previous)
    (job / relative).write_bytes(originals[relative] + b" ")
    with pytest.raises((ValueError, OSError)):
        api().export_figure_bundle(source, ["figures/EMG_α.png"], destination, replace_existing=True)
    assert destination.read_bytes() == previous
    assert not list(tmp_path.glob(".capture-figures-*"))
    (job / relative).write_bytes(originals[relative])
    api().export_figure_bundle(source, ["figures/EMG_α.png"], destination, replace_existing=True)
    assert_bundle(destination, ["figures/EMG_α.png"], originals, manifest)
    assert (package / "sources" / "raw.bin").read_bytes() == b"immutable authored raw control"


@pytest.mark.parametrize("selection", [[], ["figures/timing.png", "figures/timing.png"], ["figures/unrecorded.png"]])
def test_empty_duplicate_and_unrecorded_selection_refused(tmp_path, selection):
    _, job, _, _ = saved_job(tmp_path)
    output = tmp_path / "refused.zip"
    with pytest.raises(ValueError):
        api().export_figure_bundle(api().load_figure_source(job), selection, output)
    assert not output.exists()


@pytest.mark.parametrize("kind", ["traversal", "case_alias", "nonfinite", "params_digest"])
def test_invalid_inventory_or_provenance_is_not_exportable(tmp_path, kind):
    _, job, _, manifest = saved_job(tmp_path)
    if kind == "traversal":
        manifest["outputs"][1]["relativePath"] = "../outside.png"
    elif kind == "case_alias":
        other = dict(manifest["outputs"][1])
        other["relativePath"] = other["relativePath"].upper()
        manifest["outputs"].append(other)
    elif kind == "nonfinite":
        manifest["extra"] = float("nan")
    else:
        manifest["paramsDigest"] = "2" * 64
    (job / "job_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        api().load_figure_source(job)


def test_replaced_job_directory_requires_an_explicit_reload(tmp_path):
    _, job, originals, manifest = saved_job(tmp_path)
    source = api().load_figure_source(job)
    retained = job.with_name("old-receiving-job")
    job.rename(retained)
    shutil.copytree(retained, job)
    output = tmp_path / "replacement.zip"
    with pytest.raises(ValueError):
        api().export_figure_bundle(source, ["figures/timing.png"], output)
    assert not output.exists()
    api().export_figure_bundle(api().load_figure_source(job), ["figures/timing.png"], output)
    assert_bundle(output, ["figures/timing.png"], originals, manifest)


def test_destination_that_appears_after_selection_is_preserved(tmp_path):
    _, job, _, _ = saved_job(tmp_path)
    output = tmp_path / "another-writer.zip"
    sentry = b"created by a second writer after destination selection"

    def another_writer():
        if not output.exists():
            output.write_bytes(sentry)
        return False

    with pytest.raises(FileExistsError):
        api().export_figure_bundle(api().load_figure_source(job), ["figures/timing.png"], output, cancel=another_writer)
    assert output.read_bytes() == sentry
    assert not list(tmp_path.glob(".capture-figures-*"))


def test_native_file_size_failure_does_not_replace_previous_export(tmp_path):
    if sys.platform != "linux":
        pytest.skip("This separate receiver uses Linux RLIMIT_FSIZE; supported Windows CI is independent")
    package, job, _, _ = saved_job(tmp_path, padding=96 * 1024)
    before = file_tree(package)
    output = tmp_path / "existing.zip"
    previous = b"preserve this prior user export exactly"
    output.write_bytes(previous)
    script = r'''
import errno, json, resource, signal, sys
from pathlib import Path
from capture_desktop.analysis_figure_export import load_figure_source, export_figure_bundle
source = load_figure_source(Path(sys.argv[1]))
original = resource.getrlimit(resource.RLIMIT_FSIZE)
signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
resource.setrlimit(resource.RLIMIT_FSIZE, (8192, original[1]))
observed = None
try:
    export_figure_bundle(source, ["figures/EMG_α.png"], Path(sys.argv[2]), replace_existing=True)
except OSError as exc:
    observed = {"error": type(exc).__name__, "errno": exc.errno}
finally:
    resource.setrlimit(resource.RLIMIT_FSIZE, original)
print(json.dumps(observed))
raise SystemExit(0 if observed and observed["errno"] == errno.EFBIG else 2)
'''
    completed = subprocess.run([sys.executable, "-c", script, str(job), str(output)], text=True, capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["errno"] == errno.EFBIG
    assert output.read_bytes() == previous
    assert file_tree(package) == before
    assert not list(tmp_path.glob(".capture-figures-*"))


def test_real_qt_keyboard_selection_worker_export_and_gallery_switch(qapp, tmp_path, monkeypatch):
    from capture_desktop.widgets_analysis_plots import FigureGallery

    package, job, originals, manifest = saved_job(tmp_path)
    _, second_job, _, _ = saved_job(tmp_path, "review-B")
    before = file_tree(package)
    gallery = FigureGallery()
    gallery.resize(820, 620)
    gallery.load_job_dir(job)
    gallery.show()
    qapp.processEvents()
    QTest.mouseClick(button(gallery, "Export figures"), Qt.MouseButton.LeftButton)
    wait_for(qapp, lambda: any(w.isVisible() for w in gallery.findChildren(QDialog)))
    dialog = next(w for w in gallery.findChildren(QDialog) if w.isVisible())
    figures = dialog.findChild(QListWidget)
    assert figures is not None and figures.count() == 3
    assert "review-A" in "\n".join(w.text() for w in dialog.findChildren(QLabel))
    figures.setCurrentRow(0)
    figures.setFocus()
    QTest.keyClick(figures, Qt.Key.Key_Space)
    assert figures.item(0).checkState() == Qt.CheckState.Unchecked
    expected = tuple(figures.item(i).text() for i in range(1, figures.count()))
    assert not button(dialog, "Export ZIP").isEnabled()
    output = tmp_path / "keyboard-subset.zip"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(output), "Figure bundle (*.zip)"))
    QTest.mouseClick(button(dialog, "Choose ZIP"), Qt.MouseButton.LeftButton)
    assert button(dialog, "Export ZIP").isEnabled()
    QTest.mouseClick(button(dialog, "Export ZIP"), Qt.MouseButton.LeftButton)
    wait_for(qapp, lambda: any(w.text().startswith("Exported 2 figures") for w in dialog.findChildren(QLabel)))
    wait_for(qapp, lambda: button(dialog, "Export ZIP").isEnabled())
    assert_bundle(output, expected, originals, manifest)
    assert file_tree(package) == before
    gallery.clear()
    qapp.processEvents()
    assert not button(gallery, "Export figures").isEnabled()
    assert not any(w.isVisible() for w in gallery.findChildren(QDialog))
    gallery.load_job_dir(second_job)
    QTest.mouseClick(button(gallery, "Export figures"), Qt.MouseButton.LeftButton)
    wait_for(qapp, lambda: any(w.isVisible() for w in gallery.findChildren(QDialog)))
    fresh = next(w for w in gallery.findChildren(QDialog) if w.isVisible())
    text = "\n".join(w.text() for w in fresh.findChildren(QLabel))
    assert "review-B" in text and "review-A" not in text
    fresh.reject()
    gallery.close()
    qapp.processEvents()
