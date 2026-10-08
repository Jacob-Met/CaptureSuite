# SPDX-License-Identifier: GPL-3.0-only
"""Real Qt figure selection and byte-preserving bundle export receiving."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import zipfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from capture_desktop import analysis_figure_export as bundles
from capture_desktop import widgets_figure_export as widgets
from capture_desktop.widgets_analysis_plots import FigureGallery
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QMessageBox


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(job, relative, kind):
    data = (job / relative).read_bytes()
    return {"relativePath": relative, "kind": kind, "bytes": len(data), "sha256": digest(data)}


def write_manifest(job, manifest):
    (job / "job_manifest.json").write_text(json.dumps(manifest, indent=3) + "\n", encoding="utf-8")


@pytest.fixture
def make_job(tmp_path, qapp):
    def make(name="job-one"):
        package = tmp_path / f"{name}.mmsession"
        job = package / "processing" / "jobs" / name
        (job / "figures").mkdir(parents=True)
        (package / "sources").mkdir()
        (package / "sources" / "raw.bin").write_bytes(b"immutable native source\0\xff")
        for name, color in (("alpha", 0xFF1565C0), ("beta", 0xFFE65100)):
            image = QImage(37, 23, QImage.Format.Format_ARGB32)
            image.fill(color)
            assert image.save(str(job / "figures" / f"{name}.png"), "PNG")
        params = {
            "command": "plots",
            "gapPolicy": "mask",
            "startSessionNs": -123456789,
            "sources": ["source-α"],
            "extra": {"units": "mV", "provisional": True},
        }
        (job / "params.json").write_text(
            json.dumps(params, indent=4, ensure_ascii=False), encoding="utf-8"
        )
        canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        manifest = {
            "schemaId": "capture.analysis_job/1",
            "jobId": job.name,
            "sessionId": "synthetic-session-α",
            "createdUtc": "2026-10-08T00:00:00Z",
            "captureAnalysisVersion": "test-fixture",
            "status": "completed_with_warnings",
            "gapPolicy": "mask",
            "paramsDigest": digest(canonical.encode()),
            "packagePath": "C:\\Recorded Sessions\\original.mmsession",
            "manifestSha256": "1" * 64,
            "warnings": ["Synthetic units are provisional."],
            "analysisGrids": [{"rateHz": 20, "sourceStreams": ["source-α"]}],
            "tooling": {"fixture": "native Qt PNG"},
            "futureProvenance": {"keep": [1, None]},
            "outputs": [
                record(job, "params.json", "params"),
                record(job, "figures/alpha.png", "figure"),
                record(job, "figures/beta.png", "figure"),
                {
                    "relativePath": "job_manifest.json",
                    "kind": "manifest",
                    "bytes": 1,
                    "sha256": "0" * 64,
                },
            ],
        }
        write_manifest(job, manifest)
        return job

    return make


def package_bytes(job):
    root = job.parents[2]
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def assert_bundle(path, job, selected):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(selected) | {
            "source/job_manifest.json",
            "source/params.json",
            "manifest.json",
        }
        manifest = json.loads(archive.read("manifest.json"))
        original = json.loads((job / "job_manifest.json").read_bytes())
        assert manifest["schemaId"] == "capture.analysis_figure_bundle/1"
        assert manifest["jobId"] == original["jobId"]
        assert manifest["sessionId"] == original["sessionId"]
        assert manifest["paramsDigest"] == original["paramsDigest"]
        assert [r["sourceRelativePath"] for r in manifest["figures"]] == list(selected)
        for row in manifest["figures"] + manifest["sourceFiles"]:
            data = archive.read(row["path"])
            assert data == (job / row["sourceRelativePath"]).read_bytes()
            assert row["bytes"] == len(data)
            assert row["sha256"] == digest(data)
        # The original manifest's historical self-hash is retained, never promoted
        # into a claim about the current bytes exported in source/job_manifest.json.
        assert manifest["sourceFiles"][0]["sha256"] != "0" * 64


def test_exact_subset_and_all_original_provenance(make_job, tmp_path):
    job = make_job()
    before = package_bytes(job)
    source = bundles.load_figure_source(job)
    source.manifest["warnings"].clear()  # a consumer cannot mutate the bound source
    selected = ("figures/beta.png",)
    result = bundles.export_figure_bundle(source, selected, tmp_path / "selected.zip")
    assert result.figure_count == 1
    assert_bundle(result.path, job, selected)
    assert package_bytes(job) == before


@pytest.mark.parametrize(
    "selected", [(), ("figures/unknown.png",), ("figures/alpha.png", "figures/alpha.png")]
)
def test_invalid_selection_creates_nothing(make_job, tmp_path, selected):
    source = bundles.load_figure_source(make_job())
    with pytest.raises(bundles.FigureExportError, match="Select"):
        bundles.export_figure_bundle(source, selected, tmp_path / "invalid.zip")
    assert not (tmp_path / "invalid.zip").exists()
    assert not list(tmp_path.glob(".capture-figures-*"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("schemaId", "capture.analysis_job/999"),
        ("jobId", "other-job"),
        ("status", "failed"),
        ("sessionId", None),
        ("paramsDigest", "0" * 64),
        ("outputs", {}),
        ("outputs", [None]),
    ],
)
def test_malformed_job_is_refused(make_job, field, value):
    job = make_job()
    manifest = json.loads((job / "job_manifest.json").read_bytes())
    manifest[field] = value
    write_manifest(job, manifest)
    with pytest.raises(bundles.FigureExportError):
        bundles.load_figure_source(job)


@pytest.mark.parametrize(
    "field,value",
    [
        ("relativePath", "../outside.png"),
        ("relativePath", "/absolute.png"),
        ("relativePath", "C:\\outside.png"),
        ("relativePath", "figures/CON.png"),
        ("relativePath", "figures/ALPHA.png"),
        ("bytes", True),
        ("bytes", -1),
        ("sha256", "bad"),
    ],
)
def test_invalid_or_ambiguous_output_inventory(make_job, field, value):
    job = make_job()
    manifest = json.loads((job / "job_manifest.json").read_bytes())
    manifest["outputs"][2][field] = value
    write_manifest(job, manifest)
    with pytest.raises(bundles.FigureExportError):
        bundles.load_figure_source(job)


@pytest.mark.parametrize("changed", ["job_manifest.json", "params.json", "figures/alpha.png"])
def test_changed_source_preserves_previous_export_and_all_other_inputs(make_job, tmp_path, changed):
    job = make_job()
    source = bundles.load_figure_source(job)
    path = job / changed
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    destination = tmp_path / "previous.zip"
    destination.write_bytes(b"prior user export")
    before = package_bytes(job)
    with pytest.raises(bundles.FigureExportError):
        bundles.export_figure_bundle(
            source, ["figures/alpha.png"], destination, replace_existing=True
        )
    assert destination.read_bytes() == b"prior user export"
    assert package_bytes(job) == before
    assert not list(tmp_path.glob(".capture-figures-*"))
    path.write_bytes(original)
    bundles.export_figure_bundle(source, ["figures/alpha.png"], destination, replace_existing=True)
    assert_bundle(destination, job, ["figures/alpha.png"])


def test_only_selected_pngs_are_required_and_unrecorded_files_are_excluded(make_job, tmp_path):
    job = make_job()
    (job / "figures" / "beta.png").unlink()
    (job / "figures" / "orphan.png").write_bytes(b"not a recorded output")
    source = bundles.load_figure_source(job)
    bundles.export_figure_bundle(source, ["figures/alpha.png"], tmp_path / "one.zip")
    assert_bundle(tmp_path / "one.zip", job, ["figures/alpha.png"])
    with pytest.raises(FileNotFoundError):
        bundles.export_figure_bundle(source, ["figures/beta.png"], tmp_path / "missing.zip")
    assert not (tmp_path / "missing.zip").exists()


def test_matching_hash_does_not_turn_invalid_png_into_a_figure(make_job, tmp_path):
    job = make_job()
    (job / "figures" / "alpha.png").write_bytes(b"\x89PNG\r\n\x1a\nnot an image")
    manifest = json.loads((job / "job_manifest.json").read_bytes())
    manifest["outputs"][1] = record(job, "figures/alpha.png", "figure")
    write_manifest(job, manifest)
    with pytest.raises(bundles.FigureExportError, match="readable PNG"):
        bundles.export_figure_bundle(
            bundles.load_figure_source(job), ["figures/alpha.png"], tmp_path / "invalid.zip"
        )


def test_linked_png_cannot_substitute_an_external_file(make_job, tmp_path):
    job = make_job()
    source = bundles.load_figure_source(job)
    path = job / "figures" / "alpha.png"
    external = tmp_path / "external.png"
    external.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(external)
    except OSError:
        pytest.skip("Creating symlinks requires host permission on this platform.")
    with pytest.raises(bundles.FigureExportError, match="Linked"):
        bundles.export_figure_bundle(source, ["figures/alpha.png"], tmp_path / "linked.zip")
    assert external.read_bytes() == (job / "figures" / "alpha.png").read_bytes()


def test_source_session_destinations_are_refused(make_job):
    job = make_job()
    before = package_bytes(job)
    source = bundles.load_figure_source(job)
    for target in (job / "export.zip", job.parents[2] / "sources" / "export.zip"):
        with pytest.raises(bundles.FigureExportError, match="outside the source"):
            bundles.export_figure_bundle(source, ["figures/alpha.png"], target)
    assert package_bytes(job) == before


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b'{"jobId":"one","jobId":"two"}',
        b'{"value":NaN}',
        b"\xff",
        b'{"deep":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}",
    ],
    ids=["array", "duplicate-key", "nonfinite", "invalid-utf8", "deep-nonschema-object"],
)
def test_ambiguous_or_unreadable_manifest_cannot_enable_export(make_job, payload):
    job = make_job()
    (job / "job_manifest.json").write_bytes(payload)
    with pytest.raises(bundles.FigureExportError):
        bundles.load_figure_source(job)


@pytest.mark.parametrize("failure", ["write", "flush", "publish"])
def test_output_failure_preserves_previous_file_and_retry_succeeds(
    make_job, tmp_path, monkeypatch, failure
):
    job = make_job()
    source = bundles.load_figure_source(job)
    destination = tmp_path / "previous.zip"
    destination.write_bytes(b"previous export content")
    before = package_bytes(job)

    def refused(*args, **kwargs):
        raise OSError("injected output failure")

    with monkeypatch.context() as patch:
        if failure == "write":
            original = zipfile.ZipFile.writestr

            def partial_write(archive, *args, **kwargs):
                original(archive, *args, **kwargs)
                refused()

            patch.setattr(zipfile.ZipFile, "writestr", partial_write)
        elif failure == "flush":
            patch.setattr(bundles.os, "fsync", refused)
        else:
            patch.setattr(bundles.os, "replace", refused)
        with pytest.raises(OSError, match="injected output failure"):
            bundles.export_figure_bundle(
                source, ["figures/alpha.png"], destination, replace_existing=True
            )
    assert destination.read_bytes() == b"previous export content"
    assert package_bytes(job) == before
    assert not list(tmp_path.glob(".capture-figures-*"))
    bundles.export_figure_bundle(source, ["figures/alpha.png"], destination, replace_existing=True)
    assert_bundle(destination, job, ["figures/alpha.png"])


def test_new_destination_does_not_replace_a_raced_in_user_file(make_job, tmp_path, monkeypatch):
    job = make_job()
    source = bundles.load_figure_source(job)
    destination = tmp_path / "new.zip"
    original = zipfile.ZipFile.writestr

    def write_and_arrive(archive, *args, **kwargs):
        original(archive, *args, **kwargs)
        destination.write_bytes(b"other user's export")

    monkeypatch.setattr(zipfile.ZipFile, "writestr", write_and_arrive)
    with pytest.raises(FileExistsError):
        bundles.export_figure_bundle(source, ["figures/alpha.png"], destination)
    assert destination.read_bytes() == b"other user's export"
    assert not list(tmp_path.glob(".capture-figures-*"))


def wait_until(qapp, condition):
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(10)
    qapp.processEvents()
    assert condition(), "Qt receiving transition did not finish"


def choose_destination(dialog, path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
    QTest.mouseClick(dialog._browse, Qt.MouseButton.LeftButton)


def test_qt_selection_keyboard_export_and_clear_reload(make_job, tmp_path, qapp, monkeypatch):
    job = make_job()
    before = package_bytes(job)
    gallery = FigureGallery()
    gallery.show()
    gallery.load_job_dir(job)
    bar = gallery._figure_export
    assert bar._button.isEnabled()
    QTest.mouseClick(bar._button, Qt.MouseButton.LeftButton)
    dialog = bar._dialog
    assert dialog.isVisible()
    assert not dialog._export.isEnabled()
    choose_destination(dialog, tmp_path / "keyboard.zip", monkeypatch)
    dialog._figures.setCurrentRow(0)
    dialog._figures.setFocus()
    QTest.keyClick(dialog._figures, Qt.Key.Key_Space)
    assert dialog.selected_paths() == ("figures/beta.png",)
    dialog._export.setFocus()
    QTest.keyClick(dialog._export, Qt.Key.Key_Return)
    wait_until(qapp, lambda: dialog._worker is None)
    assert dialog._status.text().startswith("Exported 1 figures to")
    assert_bundle(tmp_path / "keyboard.zip", job, ["figures/beta.png"])
    assert package_bytes(job) == before
    gallery.clear()
    assert bar._dialog is None
    assert not bar._button.isEnabled()
    second = make_job("second-job")
    gallery.load_job_dir(second)
    QTest.mouseClick(bar._button, Qt.MouseButton.LeftButton)
    assert bar._dialog._source.job_id == "second-job"
    assert len(bar._dialog.selected_paths()) == 2
    gallery.clear()
    gallery.close()


def test_empty_invalid_and_cancelled_destination_are_truthful(
    make_job, tmp_path, qapp, monkeypatch
):
    job = make_job()
    gallery = FigureGallery()
    gallery.show()
    gallery.load_job_dir(job)
    bar = gallery._figure_export
    QTest.mouseClick(bar._button, Qt.MouseButton.LeftButton)
    dialog = bar._dialog
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    QTest.mouseClick(dialog._browse, Qt.MouseButton.LeftButton)
    assert not dialog._destination.text()
    assert not dialog._export.isEnabled()
    choose_destination(dialog, tmp_path / "selected.zip", monkeypatch)
    QTest.mouseClick(dialog._none, Qt.MouseButton.LeftButton)
    assert not dialog.selected_paths()
    assert not dialog._export.isEnabled()
    QTest.mouseClick(dialog._all, Qt.MouseButton.LeftButton)
    assert dialog._export.isEnabled()
    gallery.clear()
    manifest = json.loads((job / "job_manifest.json").read_bytes())
    manifest["outputs"] = [r for r in manifest["outputs"] if r["kind"] != "figure"]
    write_manifest(job, manifest)
    gallery.load_job_dir(job)
    assert not bar._button.isEnabled()
    assert "no recorded PNG" in bar._status.text()
    (job / "job_manifest.json").write_text("invalid JSON", encoding="utf-8")
    gallery.load_job_dir(job)
    assert not bar._button.isEnabled()
    assert "unavailable" in bar._status.text()
    assert not (tmp_path / "selected.zip").exists()
    gallery.close()


def test_native_ui_failed_export_can_retry_with_explicit_replacement(
    make_job, tmp_path, qapp, monkeypatch
):
    job = make_job()
    source = bundles.load_figure_source(job)
    dialog = widgets.FigureExportDialog(source)
    dialog.show()
    destination = tmp_path / "prior.zip"
    destination.write_bytes(b"existing user bytes")
    choose_destination(dialog, destination, monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    QTest.mouseClick(dialog._export, Qt.MouseButton.LeftButton)
    assert dialog._worker is None
    assert destination.read_bytes() == b"existing user bytes"
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    png = job / "figures" / "alpha.png"
    original = png.read_bytes()
    png.write_bytes(original + b"stale")
    QTest.mouseClick(dialog._export, Qt.MouseButton.LeftButton)
    wait_until(qapp, lambda: dialog._worker is None)
    assert "Export failed" in dialog._status.text()
    assert destination.read_bytes() == b"existing user bytes"
    assert dialog._export.isEnabled()
    png.write_bytes(original)
    QTest.mouseClick(dialog._export, Qt.MouseButton.LeftButton)
    wait_until(qapp, lambda: dialog._worker is None)
    assert dialog._status.text().startswith("Exported 2 figures")
    assert_bundle(destination, job, dialog.selected_paths())
    dialog.close()


def test_clear_cancels_running_worker_before_a_new_job_can_be_exported(
    make_job, tmp_path, qapp, monkeypatch
):
    gallery = FigureGallery()
    gallery.show()
    gallery.load_job_dir(make_job())
    QTest.mouseClick(gallery._figure_export._button, Qt.MouseButton.LeftButton)
    dialog = gallery._figure_export._dialog
    choose_destination(dialog, tmp_path / "cancelled.zip", monkeypatch)
    entered = threading.Event()
    original = widgets.export_figure_bundle

    def held_export(*args, **kwargs):
        entered.set()
        deadline = time.monotonic() + 5
        while not kwargs["cancel"]() and time.monotonic() < deadline:
            threading.Event().wait(0.005)
        return original(*args, **kwargs)

    monkeypatch.setattr(widgets, "export_figure_bundle", held_export)
    QTest.mouseClick(dialog._export, Qt.MouseButton.LeftButton)
    wait_until(qapp, entered.is_set)
    gallery.clear()  # real event-loop callback while the export thread is alive
    wait_until(qapp, lambda: gallery._figure_export._dialog is None)
    assert not (tmp_path / "cancelled.zip").exists()
    assert not gallery._figure_export._button.isEnabled()
    gallery.close()


def test_actual_analysis_job_figures_export_through_native_dialog(tmp_path, qapp, monkeypatch):
    from capture_analysis import JobParams, run

    from tests.analysis.test_phase_b_features import _write_emg_imu_package

    package = _write_emg_imu_package(tmp_path / "native.mmsession")
    result = run(package, JobParams(command="all", overwrite_job_id="figure-export-native"))
    before = package_bytes(result.job_dir)
    gallery = FigureGallery()
    gallery.show()
    gallery.load_job_dir(result.job_dir)
    assert gallery._figure_export._button.isEnabled()
    QTest.mouseClick(gallery._figure_export._button, Qt.MouseButton.LeftButton)
    dialog = gallery._figure_export._dialog
    assert len(dialog.selected_paths()) >= 3
    assert "figures/sync_dashboard.png" in dialog.selected_paths()
    choose_destination(dialog, tmp_path / "native-output.zip", monkeypatch)
    QTest.mouseClick(dialog._export, Qt.MouseButton.LeftButton)
    wait_until(qapp, lambda: dialog._worker is None)
    assert dialog._status.text().startswith("Exported ")
    assert_bundle(tmp_path / "native-output.zip", result.job_dir, dialog.selected_paths())
    assert package_bytes(result.job_dir) == before
    gallery.clear()
    gallery.close()
