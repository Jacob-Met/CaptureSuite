# SPDX-License-Identifier: GPL-3.0-only
"""Actual worker failures and cancellation expose retained-attempt notes in Qt."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"


def _failed_job_dir(package: Path) -> Path:
    jobs = list((package / "processing" / "jobs").iterdir())
    assert len(jobs) == 1
    job = jobs[0]
    manifest = json.loads((job / "job_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["jobId"] == job.name
    return job


def test_worker_failure_note_reaches_warning_and_log(qapp, tmp_path: Path) -> None:
    from capture_desktop.screen_analysis import AnalysisScreen, _AnalysisWorker
    from capture_desktop.state import CaptureState
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    package = tmp_path / "session with spaces.mmsession"
    shutil.copytree(FIXTURE, package)
    screen = AnalysisScreen(CaptureState())
    worker = _AnalysisWorker(
        str(package), "kinematics", "mask", {"pose_job_id": "missing-pose-job"}
    )
    messages: list[str] = []
    dialog_messages: list[str] = []
    worker.failed.connect(messages.append)
    worker.failed.connect(screen._on_failed)

    def close_warning() -> None:
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            dialog_messages.append(dialog.text())
            dialog.accept()

    QTimer.singleShot(0, close_warning)
    worker.run()
    qapp.processEvents()

    assert len(messages) == 1
    assert messages[0].startswith("analysis job not found: missing-pose-job")
    assert str(_failed_job_dir(package)) in messages[0]
    assert dialog_messages == messages
    assert messages[0] in screen._log.toPlainText()
    screen.close()


def test_worker_cancellation_logs_note_without_failure_dialog(qapp, tmp_path: Path) -> None:
    from capture_desktop.screen_analysis import AnalysisScreen, _AnalysisWorker
    from capture_desktop.state import CaptureState
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    package = tmp_path / "cancel.mmsession"
    shutil.copytree(FIXTURE, package)
    screen = AnalysisScreen(CaptureState())
    worker = _AnalysisWorker(str(package), "qc", "mask")
    messages: list[str] = []
    dialogs: list[str] = []
    worker.failed.connect(messages.append)
    worker.failed.connect(screen._on_failed)

    def cancel_at_write(stage: str, fraction: float) -> None:
        if stage == "write_qc":
            worker.request_cancel()

    def close_unexpected_warning() -> None:
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            dialogs.append(dialog.text())
            dialog.accept()

    worker.progress.connect(cancel_at_write)
    QTimer.singleShot(0, close_unexpected_warning)
    worker.run()
    qapp.processEvents()

    assert len(messages) == 1
    assert messages[0].split("\n", 1)[0] == "cancelled"
    assert str(_failed_job_dir(package)) in messages[0]
    assert messages[0] in screen._log.toPlainText()
    assert dialogs == [], "Cancellation must remain non-modal"
    screen.close()
