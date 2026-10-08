# SPDX-License-Identifier: GPL-3.0-only
"""Saved-result browsing uses actual retained jobs and never launches analysis."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"


def _hashes(package: Path) -> dict[str, str]:
    return {
        path.relative_to(package).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in package.rglob("*") if path.is_file()
    }


@pytest.fixture
def package(tmp_path: Path) -> Path:
    target = tmp_path / "saved results.mmsession"
    shutil.copytree(FIXTURE, target)
    return target


def _qc(package: Path, job_id: str):
    from capture_analysis import JobParams, run

    return run(package, JobParams(command="qc", overwrite_job_id=job_id))


def _select(history, job_id: str) -> None:
    for index in range(history._jobs.count()):
        if history._jobs.itemData(index).job_id == job_id:
            history._jobs.setCurrentIndex(index)
            return
    raise AssertionError(f"saved job not listed: {job_id}")


def _finish_real_job(qapp, screen) -> None:
    """Run Qt's event loop and settle the worker before any widget teardown."""
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    assert screen._thread is not None
    screen._thread.finished.connect(loop.quit)
    deadline.start(30_000)
    loop.exec()
    deadline.stop()
    qapp.processEvents()
    try:
        assert screen._thread is None, "actual analysis QThread did not finish"
    finally:
        if screen._thread is not None:
            screen._cancel_job()
            deadline.start(10_000)
            loop.exec()
            deadline.stop()
            qapp.processEvents()
        assert screen._thread is None, "worker did not settle before widget teardown"


def test_real_completed_and_failed_jobs_are_read_only(package: Path) -> None:
    from capture_analysis import JobParams, run
    from capture_desktop.analysis_history import list_saved_jobs, load_saved_job

    _qc(package, "trial-qc")
    with pytest.raises(ValueError, match="requires extra.pose_job_id"):
        run(package, JobParams(command="kinematics", overwrite_job_id="trial-failed"))
    before = _hashes(package)
    rows = {job.job_id: job for job in list_saved_jobs(package)}
    assert rows["trial-qc"].status == "completed"
    assert rows["trial-failed"].status == "failed"
    assert not any(row.problem for row in rows.values())
    failed = load_saved_job(package, "trial-failed")
    assert json.loads(failed.params_text)["command"] == "kinematics"
    assert "requires extra.pose_job_id" in failed.log_text
    assert "ERROR:" in failed.log_text
    assert _hashes(package) == before


def test_copied_package_keeps_its_saved_result(package: Path, tmp_path: Path) -> None:
    from capture_desktop.analysis_history import load_saved_job

    original = _qc(package, "relocated-qc")
    moved = tmp_path / "renamed copy.mmsession"
    shutil.copytree(package, moved)
    before = _hashes(moved)
    job = load_saved_job(moved, "relocated-qc")
    assert job.manifest["packagePath"] == str(package)
    assert job.job.directory == moved / "processing/jobs/relocated-qc"
    assert job.job.directory != original.job_dir
    assert _hashes(moved) == before


def test_catalog_explains_unreadable_rows_without_hiding_good_jobs(package: Path) -> None:
    from capture_desktop.analysis_history import list_saved_jobs

    result = _qc(package, "good")
    parent = result.job_dir.parent
    for name, changes in (
        ("future", {"schemaId": "capture.analysis_job/99"}),
        ("bad-status", {"status": []}),
        ("bad-outputs", {"outputs": ["unexpected"]}),
        ("foreign-session", {"sessionId": "another-session"}),
    ):
        dest = parent / name
        dest.mkdir()
        manifest = dict(result.manifest, jobId=name, **changes)
        (dest / "job_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    broken = parent / "broken-json"
    broken.mkdir()
    (broken / "job_manifest.json").write_text("[", encoding="utf-8")
    (parent / ".attempt_unfinished").mkdir()
    before = _hashes(package)
    rows = {job.job_id: job for job in list_saved_jobs(package)}
    assert len(rows) == 6
    assert not rows["good"].problem
    assert all(row.problem for name, row in rows.items() if name != "good")
    assert "different session" in rows["foreign-session"].problem
    assert _hashes(package) == before


def test_missing_details_and_long_log_are_explicit(package: Path) -> None:
    from capture_desktop.analysis_history import load_saved_job

    result = _qc(package, "long-log")
    log = result.job_dir / "logs/job.log"
    log.write_text("x" * (300 * 1024) + "\nFINAL ORIGINAL DIAGNOSTIC", encoding="utf-8")
    before = _hashes(package)
    loaded = load_saved_job(package, "long-log")
    assert loaded.log_text.startswith("Showing the final 262,144 bytes")
    assert loaded.log_text.endswith("FINAL ORIGINAL DIAGNOSTIC")
    assert _hashes(package) == before
    minimal = result.job_dir.parent / "minimal-failure"
    minimal.mkdir()
    (minimal / "job_manifest.json").write_text(json.dumps({
        "schemaId": "capture.analysis_job/1", "jobId": minimal.name,
        "sessionId": result.manifest["sessionId"], "status": "failed", "outputs": [],
    }), encoding="utf-8")
    loaded = load_saved_job(package, minimal.name)
    assert loaded.job.status == "failed"
    assert loaded.params_text.startswith("Parameters unavailable:")
    assert loaded.log_text.startswith("Log unavailable:")


def test_native_open_and_details_leave_the_package_unchanged(qapp, package: Path) -> None:
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState
    from PySide6.QtWidgets import QPlainTextEdit

    result = _qc(package, "saved-qc")
    (result.job_dir / "logs/job.log").write_text(
        "Original diagnostic <b>literal text</b>\n", encoding="utf-8"
    )
    before = _hashes(package)
    screen = AnalysisScreen(CaptureState())
    screen.set_package(str(package))
    assert not screen._last_job_dir
    assert screen._history._jobs.count() == 1
    screen._history._open.click()
    qapp.processEvents()
    assert screen._thread is None
    assert screen._last_job_dir == str(result.job_dir)
    assert "job_id=saved-qc" in screen._inspector._meta.text()
    assert screen._btn_open_report.isEnabled()
    screen._history._details.click()
    qapp.processEvents()
    dialog = screen._history._dialog
    assert dialog is not None and dialog.isVisible()
    editors = {view.objectName(): view for view in dialog.findChildren(QPlainTextEdit)}
    assert all(view.isReadOnly() for view in editors.values())
    assert json.loads(editors["analysisHistoryParameters"].toPlainText())["command"] == "qc"
    assert "<b>literal text</b>" in editors["analysisHistoryLog"].toPlainText()
    assert json.loads(editors["analysisHistoryManifest"].toPlainText())["jobId"] == "saved-qc"
    assert _hashes(package) == before
    dialog.close()
    screen.close()


def test_refresh_preserves_the_view_and_offers_a_new_retained_job(qapp, package: Path) -> None:
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState

    first = _qc(package, "first")
    screen = AnalysisScreen(CaptureState())
    screen.set_package(str(package))
    screen._history._open.click()
    second = _qc(package, "second")
    before = _hashes(package)
    screen._history._refresh.click()
    assert screen._history._jobs.count() == 2
    assert screen._last_job_dir == str(first.job_dir)
    assert screen._history.loaded_job_id == "first"
    _select(screen._history, "second")
    assert screen._last_job_dir == str(first.job_dir)
    screen._history._open.click()
    qapp.processEvents()
    assert screen._last_job_dir == str(second.job_dir)
    assert screen._history.loaded_job_id == "second"
    assert screen._thread is None
    assert _hashes(package) == before
    screen.close()


def test_real_threaded_completion_populates_history(qapp, package: Path) -> None:
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState

    screen = AnalysisScreen(CaptureState())
    screen.set_package(str(package))
    before = _hashes(package)
    screen._btn_run.click()
    _finish_real_job(qapp, screen)
    assert screen._history._jobs.count() == 1
    assert screen._history.loaded_job_id
    assert screen._last_job_dir
    assert screen._history._open.isEnabled()
    assert "status=completed" in screen._inspector._meta.text()
    after = _hashes(package)
    assert {name: after[name] for name in before} == before
    assert all(name.startswith("processing/") for name in after.keys() - before.keys())
    screen.close()


def test_real_threaded_failure_offers_its_retained_diagnostics(qapp, package: Path,
                                                            monkeypatch) -> None:
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState
    from PySide6.QtWidgets import QMessageBox

    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text))
    screen = AnalysisScreen(CaptureState())
    screen.set_package(str(package))
    screen._command.setCurrentIndex(screen._command.findData("kinematics"))
    screen._extras._pose_job.setEditText("missing-pose")
    before = _hashes(package)
    screen._btn_run.click()
    _finish_real_job(qapp, screen)
    assert warnings and "missing-pose" in warnings[0]
    assert screen._history._jobs.count() == 1
    assert screen._history._jobs.currentData().status == "failed"
    assert not screen._last_job_dir
    screen._history._open.click()
    assert "status=failed" in screen._inspector._meta.text()
    assert "missing-pose" in screen._history._loaded.log_text
    after = _hashes(package)
    assert {name: after[name] for name in before} == before
    assert all(name.startswith("processing/") for name in after.keys() - before.keys())
    screen.close()


@pytest.fixture(autouse=True)
def _history_ci_boundary(request, capfd):
    """Temporary timing evidence for the two retained 300-second CI timeouts."""
    import time

    started = time.perf_counter()
    with capfd.disabled():
        print(f"[analysis-history:start] {request.node.nodeid}", flush=True)
    yield
    with capfd.disabled():
        elapsed = time.perf_counter() - started
        print(f"[analysis-history:finish] {request.node.nodeid} {elapsed:.3f}s", flush=True)
