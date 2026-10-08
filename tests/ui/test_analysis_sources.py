# SPDX-License-Identifier: GPL-3.0-only
"""Real recorded-source selection, Qt admission and MCAP job provenance."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def _package(path: Path) -> Path:
    from tests.analysis.test_numeric_cli_receiving import make_package, write_json

    package = make_package(path)
    # The review reader reports folder-a, but the pipeline filters sampler.a.
    # Keep the actual sealed MCAP bytes and descriptor identities intact.
    (package / "sources" / "sampler.a").rename(package / "sources" / "folder-a")
    integrity = json.loads((package / "integrity.json").read_text(encoding="utf-8"))
    for entry in integrity["files"]:
        entry["path"] = entry["path"].replace("sources/sampler.a/", "sources/folder-a/")
    write_json(package / "integrity.json", integrity)
    return package


def _screen(qapp, package: Path):
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState

    screen = AnalysisScreen(CaptureState())
    screen.set_package(str(package))
    screen.resize(1200, 900)
    screen.show()
    qapp.processEvents()
    return screen


def _close(qapp, screen):
    from tests.ui.test_analysis_scope import _close_widgets

    _close_widgets(qapp, screen)


def test_operator_can_choose_exact_recorded_sources(qapp, tmp_path: Path):
    from capture_analysis.discover import discover_streams
    from capture_session import load_review_summary
    from PySide6.QtWidgets import QComboBox

    package = _package(tmp_path / "sources μ.mmsession")
    assert load_review_summary(package).source_ids == ["folder-a", "sampler.b"]
    assert sorted({ref.source_id for ref in discover_streams(package)}) == [
        "sampler.a", "sampler.b",
    ]
    screen = _screen(qapp, package)
    try:
        modes = [w for w in screen.findChildren(QComboBox)
                 if w.accessibleName() == "Analysis source mode"]
        assert len(modes) == 1, "Analysis has no operator-accessible recorded-source picker"
        assert [modes[0].itemText(i) for i in range(modes[0].count())] == [
            "All recorded sources", "Selected sources",
        ]
    finally:
        _close(qapp, screen)


def _choose(qapp, picker, requested: set[str], *, accept: bool = True) -> set[str]:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListWidget

    picker._mode.setCurrentIndex(picker._mode.findData("selected"))
    offered = set()
    errors = []

    def operate():
        dialog = qapp.activeModalWidget()
        try:
            assert isinstance(dialog, QDialog)
            rows = dialog.findChild(QListWidget)
            assert rows is not None
            for i in range(rows.count()):
                item = rows.item(i)
                source = item.data(Qt.ItemDataRole.UserRole)
                offered.add(source)
                desired = source in requested
                if (item.checkState() == Qt.CheckState.Checked) != desired:
                    rows.setCurrentItem(item)
                    QTest.keyClick(rows, Qt.Key.Key_Space)
                assert (item.checkState() == Qt.CheckState.Checked) == desired
            assert requested <= offered
            buttons = dialog.findChild(QDialogButtonBox)
            kind = (QDialogButtonBox.StandardButton.Ok if accept
                    else QDialogButtonBox.StandardButton.Cancel)
            QTest.mouseClick(buttons.button(kind), Qt.MouseButton.LeftButton)
        except BaseException as exc:
            errors.append(exc)
            if isinstance(dialog, QDialog):
                dialog.reject()

    QTimer.singleShot(0, operate)
    QTest.mouseClick(picker._choose, Qt.MouseButton.LeftButton)
    if errors:
        raise errors[0]
    return offered


def _warning_timer(qapp):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox

    messages = []

    def close_warning():
        dialog = qapp.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            messages.append(dialog.text())
            dialog.accept()

    timer = QTimer()
    timer.timeout.connect(close_warning)
    timer.start(20)
    return timer, messages


def _wait_for_job(qapp, screen, timeout: float = 120) -> bool:
    from PySide6.QtCore import QEventLoop, QTimer

    if screen._thread is None:
        return True
    # Exercise normal Qt event delivery, including the existing completion and
    # thread cleanup slots. A completed artifact alone is not a settled UI job.
    loop = QEventLoop()
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    settled = QTimer()
    settled.timeout.connect(lambda: loop.quit() if screen._thread is None else None)
    deadline.start(round(timeout * 1000))
    settled.start(20)
    loop.exec()
    deadline.stop()
    settled.stop()
    qapp.processEvents()
    return screen._thread is None


@pytest.mark.parametrize("selected", [None, "sampler.a", "sampler.b"])
def test_source_choice_reaches_real_thread_job_and_mcap_outputs(
    qapp, tmp_path: Path, selected: str | None,
):
    import pandas as pd
    from capture_desktop.widgets_analysis_scope import ScopeSelection
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from tests.analysis.test_numeric_cli_receiving import retained_files

    package = _package(tmp_path / "source choice μ.mmsession")
    before = retained_files(package)
    screen = _screen(qapp, package)
    picker = screen._sources
    screen._command.setCurrentIndex(screen._command.findData("features"))
    timer, dialogs = _warning_timer(qapp)
    try:
        if selected is not None:
            assert _choose(qapp, picker, {selected}) == {"sampler.a", "sampler.b"}
        if selected == "sampler.b":
            screen.set_scope(
                str(package),
                ScopeSelection(mode="range", start_ns=1_200_000_001, end_ns=2_400_000_001),
            )
        assert screen._btn_run.isEnabled()
        QTest.mouseClick(screen._btn_run, Qt.MouseButton.LeftButton)
        assert screen._thread is not None
        # The actual next choice differs from the running worker's snapshot.
        other = "sampler.b" if selected != "sampler.b" else "sampler.a"
        _choose(qapp, picker, {other})
        assert picker.selected_ids == (other,)
        assert _wait_for_job(qapp, screen), "real analysis thread did not finish"
        assert not dialogs, dialogs
        assert screen._last_job_dir, screen._log.toPlainText()
        job = Path(screen._last_job_dir)
        params = json.loads((job / "params.json").read_text(encoding="utf-8"))
        manifest = json.loads((job / "job_manifest.json").read_text(encoding="utf-8"))
        qc = json.loads((job / "reports" / "qc.json").read_text(encoding="utf-8"))
        tables = json.loads((job / "features" / "_schema.json").read_text())["tables"]
        identities = sorted((item["sourceId"], item["streamId"]) for item in tables.values())
        expected = [
            (source, stream)
            for source, stream in [
                ("sampler.a", "force"), ("sampler.a", "voltage"), ("sampler.b", "temperature"),
            ]
            if selected is None or source == selected
        ]
        table_rows = {
            relative: pd.read_parquet(job / relative).to_dict(orient="records")
            for relative in tables
        }
        after = retained_files(package)
        record = {
            "requested_source": selected,
            "params": params,
            "manifest": manifest,
            "feature_identities": identities,
            "feature_rows": table_rows,
            "qc_source_ids": sorted({stream["sourceId"] for stream in qc["streams"]}),
            "raw_before": before,
            "raw_after": after,
            "raw_unchanged": before == after,
        }
        (tmp_path / "source-receiving.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        assert params["sources"] == ([] if selected is None else [selected])
        assert manifest["sourcesSelected"] == (
            ["sampler.a", "sampler.b"] if selected is None else [selected]
        )
        assert identities == expected
        assert record["qc_source_ids"] == ["sampler.a", "sampler.b"]
        assert manifest["status"] == "completed", manifest["warnings"]
        for relative, rows in table_rows.items():
            assert rows
            stream = tables[relative]["streamId"]
            offset = {"force": 3.0, "voltage": 1.0, "temperature": 7.0}[stream]
            assert rows[0]["input 1_mean"] == pytest.approx(offset + 0.45)
        if selected == "sampler.b":
            assert params["startSessionNs"] == 1_200_000_001
            assert params["endSessionNs"] == 2_400_000_001
            assert manifest["timeRange"]["startSessionNs"] == 1_200_000_001
            assert manifest["timeRange"]["endSessionNs"] == 2_400_000_001
            assert len(next(iter(table_rows.values()))) == 1
            assert next(iter(table_rows.values()))[0]["t_start_ns"] == 1_250_000_000
        assert before == after
    finally:
        if screen._thread is not None:
            screen._cancel_job()
            assert _wait_for_job(qapp, screen), "cancelled worker did not finish"
        timer.stop()
        _close(qapp, screen)


def test_empty_selected_sources_never_become_all_sources(qapp, tmp_path: Path):
    package = _package(tmp_path / "empty.mmsession")
    screen = _screen(qapp, package)
    timer, warnings = _warning_timer(qapp)
    try:
        screen._command.setCurrentIndex(screen._command.findData("features"))
        _choose(qapp, screen._sources, set())
        assert screen._sources.mode == "selected"
        assert not screen._btn_run.isEnabled()
        assert "at least one source" in screen._sources._note.text()
        screen._start_job()  # Programmatic admission also refuses the empty subset.
        assert len(warnings) == 1 and "at least one source" in warnings[0]
        assert screen._thread is None
        assert not (package / "processing" / "jobs").exists()
        screen._sources._mode.setCurrentIndex(screen._sources._mode.findData("all"))
        assert screen._btn_run.isEnabled()
    finally:
        timer.stop()
        _close(qapp, screen)


@pytest.mark.parametrize("refresh_package", [False, True])
def test_vanished_selection_stays_invalid_and_is_rechecked_at_launch(
    qapp, tmp_path: Path, refresh_package: bool,
):
    package = _package(tmp_path / "vanished.mmsession")
    screen = _screen(qapp, package)
    timer, warnings = _warning_timer(qapp)
    try:
        screen._command.setCurrentIndex(screen._command.findData("features"))
        _choose(qapp, screen._sources, {"sampler.a"})
        assert screen._btn_run.isEnabled()
        (package / "sources" / "folder-a").rename(package / "removed-source")
        if refresh_package:
            screen.set_package(str(package))
            assert not screen._btn_run.isEnabled()
        else:
            screen.refresh_from_state()  # Timer refresh uses the cached inventory.
            assert screen._btn_run.isEnabled()
        screen._start_job()
        assert screen._sources.selected_ids == ("sampler.a",)
        assert not screen._btn_run.isEnabled()
        assert len(warnings) == 1
        assert "sampler.a" in warnings[0] and "no longer recorded" in warnings[0]
        assert screen._thread is None
        assert not (package / "processing" / "jobs").exists()
        assert _choose(qapp, screen._sources, {"sampler.b"}) == {"sampler.a", "sampler.b"}
        assert screen._sources.selected_ids == ("sampler.b",)
        assert screen._btn_run.isEnabled()
    finally:
        timer.stop()
        _close(qapp, screen)


def test_cancel_command_limits_and_package_identity(qapp, tmp_path: Path):
    first = _package(tmp_path / "first.mmsession")
    second = _package(tmp_path / "second.mmsession")
    screen = _screen(qapp, first)
    try:
        screen._command.setCurrentIndex(screen._command.findData("features"))
        picker = screen._sources
        _choose(qapp, picker, {"sampler.a"})
        _choose(qapp, picker, {"sampler.b"}, accept=False)
        assert picker.selected_ids == ("sampler.a",)
        picker._mode.setCurrentIndex(picker._mode.findData("all"))
        picker._mode.setCurrentIndex(picker._mode.findData("selected"))
        assert picker.selected_ids == ("sampler.a",)
        screen.set_package(str(first))
        assert picker.mode == "selected" and picker.selected_ids == ("sampler.a",)
        for command in ("all", "features", "plots", "pose"):
            screen._command.setCurrentIndex(screen._command.findData(command))
            assert screen._btn_run.isEnabled()
        for command in ("qc", "kinematics", "ml_bundle", "eval"):
            screen._command.setCurrentIndex(screen._command.findData(command))
            assert not screen._btn_run.isEnabled()
            assert "Select All recorded sources" in picker._note.text()
        screen.set_package(str(second))
        assert picker.mode == "all" and picker.selected_ids == ()
        assert screen._source_error() is None
        screen.set_package(str(tmp_path / "missing.mmsession"))
        assert not screen._btn_run.isEnabled()
        assert not picker.isEnabled()
        assert picker.selected_ids == ()
    finally:
        _close(qapp, screen)


def test_unreadable_inventory_refuses_explicit_subset(qapp, tmp_path: Path):
    package = _package(tmp_path / "invalid-descriptor.mmsession")
    screen = _screen(qapp, package)
    try:
        screen._command.setCurrentIndex(screen._command.findData("features"))
        picker = screen._sources
        _choose(qapp, picker, {"sampler.b"})
        descriptor = package / "sources" / "sampler.b" / "streams" / "temperature" / "stream.json"
        meta = json.loads(descriptor.read_text(encoding="utf-8"))
        meta["nominalRateHz"] = "not a recorded rate"
        descriptor.write_text(json.dumps(meta), encoding="utf-8")
        screen.set_package(str(package))
        assert picker.selected_ids == ("sampler.b",)
        assert not screen._btn_run.isEnabled()
        assert "Could not read recorded sources" in picker._note.text()
        assert not (package / "processing" / "jobs").exists()
        picker._mode.setCurrentIndex(picker._mode.findData("all"))
        # All keeps the original backend path; this UI adds no extra QC policy.
        assert screen._source_error() is None
        assert screen._btn_run.isEnabled()
    finally:
        _close(qapp, screen)


def test_worker_refuses_a_subset_for_a_nonconsuming_command(tmp_path: Path):
    from capture_desktop.screen_analysis import _AnalysisWorker

    package = _package(tmp_path / "guard.mmsession")
    worker = _AnalysisWorker(str(package), "qc", "mask", sources=("sampler.a",))
    errors = []
    worker.failed.connect(errors.append)
    worker.run()
    assert errors == ["This command requires All recorded sources."]
    assert not (package / "processing" / "jobs").exists()


@pytest.mark.skipif(
    sys.platform != "win32", reason="MainWindow imports native named-pipe transport"
)
def test_application_sources_survive_timer_and_review_navigation(qapp, tmp_path: Path):
    from capture_desktop.app import MainWindow
    from PySide6.QtTest import QTest

    from tests.ui.test_analysis_scope import _close_widgets

    package = _package(tmp_path / "shell.mmsession")
    window = MainWindow(auto_connect=False)
    window.resize(1400, 1000)
    window.show()
    try:
        window.state.package_path = str(package)
        window.state.review_mode = True
        window.review.load_package(str(package))
        window.analysis.set_package(str(package))
        window.tabs.setCurrentWidget(window.analysis)
        window.analysis._command.setCurrentIndex(window.analysis._command.findData("features"))
        picker = window.analysis._sources
        _choose(qapp, picker, {"sampler.b"})
        QTest.qWait(150)
        assert picker.mode == "selected" and picker.selected_ids == ("sampler.b",)
        window.tabs.setCurrentWidget(window.review)
        window.tabs.setCurrentWidget(window.analysis)
        assert picker.mode == "selected" and picker.selected_ids == ("sampler.b",)
        assert window.analysis._btn_run.isEnabled()
        evidence = Path("build/evidence/analysis-sources-234cae4aee53")
        evidence.mkdir(parents=True, exist_ok=True)
        qapp.processEvents()
        assert window.grab().save(str(evidence / "windows-mainwindow.png"))
        different = _package(tmp_path / "browsed.mmsession")
        window.analysis.set_package(str(different))
        assert picker.mode == "all" and picker.selected_ids == ()
        assert window.state.package_path == str(package)
    finally:
        window.link.stop()
        _close_widgets(qapp, window)
