# SPDX-License-Identifier: GPL-3.0-only
"""Real Qt scope selection reaches MCAP analysis and retained job provenance."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def _package(path: Path) -> Path:
    from tests.analysis.test_phase_b_features import _write_emg_imu_package

    package = _write_emg_imu_package(path)
    checkpoints = [
        {"checkpointId": "section-one", "name": "Movement", "effectiveTimestampNs": 50_000_001},
        {"checkpointId": "section-two", "name": "Movement", "effectiveTimestampNs": 150_000_001},
    ]
    (package / "events" / "checkpoints.json").write_text(json.dumps(checkpoints), encoding="utf-8")
    return package


def _raw_hashes(package: Path) -> dict[str, str]:
    return {
        p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in package.rglob("*")
        if p.is_file() and "processing" not in p.parts
    }


def _close_widgets(qapp, *widgets):
    from PySide6.QtCore import QCoreApplication, QEvent

    for widget in widgets:
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def _widgets(qapp, package: Path):
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState
    from capture_desktop.widgets_session_header import SessionHeader
    from capture_session import load_review_summary

    screen = AnalysisScreen(CaptureState())
    header = SessionHeader()
    header.scope_changed.connect(screen.set_scope)
    screen.set_package(str(package))
    header.refresh_sealed(load_review_summary(package))
    screen.resize(1200, 900)
    header.resize(1200, 280)
    screen.show()
    header.show()
    qapp.processEvents()
    return header, screen


def test_operator_can_choose_a_sealed_session_scope(qapp, tmp_path: Path):
    from capture_desktop.widgets_session_header import SessionHeader
    from capture_session import load_review_summary
    from PySide6.QtWidgets import QComboBox

    package = _package(tmp_path / "operator.mmsession")
    header = SessionHeader()
    header.refresh_sealed(load_review_summary(package))
    modes = [
        w for w in header.findChildren(QComboBox) if w.accessibleName() == "Analysis scope mode"
    ]
    assert len(modes) == 1, "sealed session has no operator-accessible analysis scope picker"
    assert [modes[0].itemText(i) for i in range(modes[0].count())] == [
        "Full session",
        "Checkpoint section",
        "Time range",
    ]
    _close_widgets(qapp, header)


@pytest.mark.parametrize("mode", ["range", "section"])
def test_selected_scope_reaches_real_thread_job_and_mcap_outputs(qapp, tmp_path: Path, mode: str):
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox

    package = _package(tmp_path / f"{mode} space μ.mmsession")
    raw = _raw_hashes(package)
    header, screen = _widgets(qapp, package)
    picker = header._scope_picker
    screen._command.setCurrentIndex(screen._command.findData("all"))
    picker._mode.setCurrentIndex(picker._mode.findData(mode))
    if mode == "range":
        picker._start.setText("0.050000001")
        picker._end.setText("0.150000001")
    else:
        assert picker._sections.count() == 2
        assert "section-one" in picker._sections.itemText(0)
        assert "section-two" in picker._sections.itemText(1)
        picker._sections.setCurrentIndex(1)
    assert screen._btn_run.isEnabled()
    assert screen.scope.start_ns == 50_000_001
    assert screen.scope.end_ns == 150_000_001
    selected = screen.scope
    dialogs = []

    def close_failure_dialog():
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            dialogs.append(dialog.text())
            dialog.accept()

    timer = QTimer()
    timer.timeout.connect(close_failure_dialog)
    timer.start(20)
    try:
        QTest.mouseClick(screen._btn_run, Qt.MouseButton.LeftButton)
        # Changing the next selection must not mutate the running job's snapshot.
        picker._mode.setCurrentIndex(picker._mode.findData("full"))
        until = time.monotonic() + 120
        while screen._thread is not None and time.monotonic() < until:
            QTest.qWait(20)
        assert screen._thread is None, "real analysis thread did not finish"
        assert not dialogs, dialogs
        assert screen._last_job_dir, screen._log.toPlainText()
        job = Path(screen._last_job_dir)
        params = json.loads((job / "params.json").read_text(encoding="utf-8"))
        manifest = json.loads((job / "job_manifest.json").read_text(encoding="utf-8"))
        series = json.loads((job / "figures" / "sync_dashboard_series.json").read_text())
        assert manifest["timeRange"]["startSessionNs"] == selected.start_ns
        assert manifest["timeRange"]["endSessionNs"] == selected.end_ns
        if mode == "section":
            assert params["checkpointSection"] == "section-two"
            assert params["startSessionNs"] is None
            assert manifest["timeRange"]["checkpointIds"] == ["section-two"]
        else:
            assert params["startSessionNs"] == selected.start_ns
            assert params["endSessionNs"] == selected.end_ns
            assert params["checkpointSection"] is None
        assert len(series["series"]) == 2
        for item in series["series"]:
            assert item["t_ns"], item["label"]
            assert all(selected.start_ns <= t <= selected.end_ns for t in item["t_ns"])
        assert _raw_hashes(package) == raw
        assert selected.describe() in screen._log.toPlainText()
    finally:
        if screen._thread is not None:
            screen._cancel_job()
            # Cancellation is observed between backend stages. Keep Qt and the
            # widgets alive until the actual worker has finished; a short wait
            # can otherwise leak a plotting thread into the next test.
            while screen._thread is not None:
                QTest.qWait(20)
        timer.stop()
        _close_widgets(qapp, header, screen)


@pytest.mark.parametrize(
    "start,end",
    [
        ("0.2", "0.1"),
        ("0.1", "0.1"),
        ("NaN", "1"),
        ("inf", "1"),
        ("0.0000000001", "1"),
        ("1.00000000000000000000000000001", "2"),
        ("", "1"),
        ("0", "9223372036.854775808"),
    ],
)
def test_invalid_scope_blocks_job_before_outputs(qapp, tmp_path: Path, start: str, end: str):
    package = _package(tmp_path / "invalid.mmsession")
    header, screen = _widgets(qapp, package)
    screen._command.setCurrentIndex(screen._command.findData("features"))
    picker = header._scope_picker
    picker._mode.setCurrentIndex(picker._mode.findData("range"))
    picker._start.setText(start)
    picker._end.setText(end)
    assert screen.scope is None
    assert not screen._btn_run.isEnabled()
    assert not (package / "processing" / "jobs").exists()
    assert "scope bounds" in screen._scope_note.text()
    _close_widgets(qapp, header, screen)


def test_scope_command_limits_and_package_identity(qapp, tmp_path: Path):
    from capture_desktop.widgets_analysis_scope import ScopeSelection
    from capture_session import load_review_summary

    first = _package(tmp_path / "first.mmsession")
    second = _package(tmp_path / "second.mmsession")
    header, screen = _widgets(qapp, first)
    picker = header._scope_picker
    picker._mode.setCurrentIndex(picker._mode.findData("section"))
    assert not screen._btn_run.isEnabled()  # QC does not apply a time window.
    assert "Select Full session" in screen._scope_note.text()
    for command in ("all", "features", "plots", "pose"):
        screen._command.setCurrentIndex(screen._command.findData(command))
        assert screen._btn_run.isEnabled()
    for command in ("kinematics", "ml_bundle", "eval", "qc"):
        screen._command.setCurrentIndex(screen._command.findData(command))
        assert not screen._btn_run.isEnabled()
    screen.set_scope(str(second), ScopeSelection())
    assert screen.scope.mode == "section", "a different package must not change this scope"
    picker._mode.setCurrentIndex(picker._mode.findData("full"))
    assert screen._btn_run.isEnabled()
    screen.set_package(str(second))
    header.refresh_sealed(load_review_summary(second))
    assert screen.scope.mode == "full"
    screen.set_package(str(tmp_path / "missing.mmsession"))
    assert not screen._btn_run.isEnabled()
    assert screen.summary is None
    assert screen._card_session.text() == "—"
    _close_widgets(qapp, header, screen)


def test_timeline_cursor_marks_range_without_losing_gaps(qapp, tmp_path: Path):
    from capture_session import load_review_summary
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    package = _package(tmp_path / "cursor.mmsession")
    header, screen = _widgets(qapp, package)
    picker = header._scope_picker
    picker._mode.setCurrentIndex(picker._mode.findData("range"))
    timeline = header._timeline
    gaps = timeline._model.gaps[:]
    QTest.mouseClick(timeline, Qt.MouseButton.LeftButton, pos=QPoint(360, 35))
    assert timeline._model.playhead_s > 0
    QTest.mouseClick(picker._mark_start, Qt.MouseButton.LeftButton)
    assert picker.selection.start_ns == round(timeline._model.playhead_s * 1e9)
    assert timeline._model.selection_start_s == picker.selection.start_ns / 1e9
    assert timeline._model.gaps == gaps
    selected = picker.selection
    cursor = timeline._model.playhead_s
    header.refresh_sealed(load_review_summary(package))
    assert picker.selection == selected
    assert timeline._model.playhead_s == cursor
    qapp.processEvents()
    _close_widgets(qapp, header, screen)


def test_invalid_scope_stays_invalid_across_header_refresh(qapp, tmp_path: Path):
    from capture_desktop.state import CaptureState
    from capture_session import load_review_summary

    package = _package(tmp_path / "invalid-refresh.mmsession")
    header, screen = _widgets(qapp, package)
    picker = header._scope_picker
    screen._command.setCurrentIndex(screen._command.findData("features"))
    picker._mode.setCurrentIndex(picker._mode.findData("range"))
    picker._start.setText("bad value")
    assert screen.scope is None
    header.refresh_live(CaptureState())
    header.refresh_sealed(load_review_summary(package), selection=screen.scope)
    assert picker.selection is None
    assert screen.scope is None
    assert not screen._btn_run.isEnabled()
    # Different context, then return to an invalid analysis selection.
    other = _package(tmp_path / "other.mmsession")
    header.refresh_sealed(load_review_summary(other))
    header.refresh_sealed(load_review_summary(package), selection=screen.scope)
    assert picker.selection is None
    assert not screen._btn_run.isEnabled()
    _close_widgets(qapp, header, screen)


@pytest.mark.parametrize("reverse_record_order", [False, True])
def test_shadowed_checkpoint_id_is_unavailable_with_time_range_fallback(
    qapp,
    tmp_path: Path,
    reverse_record_order: bool,
):
    package = _package(tmp_path / "shadowed-id.mmsession")
    path = package / "events" / "checkpoints.json"
    checkpoints = json.loads(path.read_text())
    checkpoints[0]["name"] = "section-two"
    if reverse_record_order:
        checkpoints.reverse()
    path.write_text(json.dumps(checkpoints), encoding="utf-8")
    raw = _raw_hashes(package)
    header, screen = _widgets(qapp, package)
    screen._command.setCurrentIndex(screen._command.findData("features"))
    picker = header._scope_picker
    picker._mode.setCurrentIndex(picker._mode.findData("section"))
    offered = [picker._sections.itemData(i).section_name for i in range(picker._sections.count())]
    assert offered == ["section-one"], "shadowed ID must not offer another checkpoint's bounds"
    assert "Movement (section-two)" in picker._section_notice.text()
    assert "unavailable" in picker._section_notice.text()
    assert "Time range" in picker._section_notice.text()
    assert not picker._section_notice.isHidden()
    picker._mode.setCurrentIndex(picker._mode.findData("range"))
    picker._start.setText("0.150000001")
    picker._end.setText("0.500000000")
    assert screen._btn_run.isEnabled()
    assert screen.scope.job_fields() == {
        "start_session_ns": 150_000_001,
        "end_session_ns": 500_000_000,
    }
    assert _raw_hashes(package) == raw
    _close_widgets(qapp, header, screen)


@pytest.mark.skipif(
    sys.platform != "win32", reason="MainWindow imports native named-pipe transport"
)
def test_application_scope_survives_timer_and_review_navigation(qapp, tmp_path: Path):
    from capture_desktop.app import MainWindow
    from PySide6.QtTest import QTest

    package = _package(tmp_path / "shell.mmsession")
    window = MainWindow(auto_connect=False)
    try:
        window.state.package_path = str(package)
        window.state.review_mode = True
        window.review.load_package(str(package))
        window.analysis.set_package(str(package))
        window.tabs.setCurrentWidget(window.analysis)
        picker = window._session_header._scope_picker
        picker._mode.setCurrentIndex(picker._mode.findData("section"))
        selected = window.analysis.scope
        QTest.qWait(150)  # Exercise the real 100 ms chrome refresh.
        assert window._session_header.is_sealed
        assert picker.selection == selected
        window.tabs.setCurrentWidget(window.review)
        window.tabs.setCurrentWidget(window.analysis)
        assert picker.selection == window.analysis.scope == selected
        different = _package(tmp_path / "browsed.mmsession")
        window.analysis.set_package(str(different))
        assert window._session_header.package_path == str(different.resolve())
        assert window.analysis.scope.mode == "full"
        assert window.state.package_path == str(package)
        window.analysis.set_package(str(tmp_path / "missing.mmsession"))
        assert not window.analysis._btn_run.isEnabled()
        assert window._session_header.isHidden()
    finally:
        window.link.stop()
        window.close()
