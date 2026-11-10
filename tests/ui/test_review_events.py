# SPDX-License-Identifier: GPL-3.0-only
"""Native Review controls exercised with authored on-disk event records."""

from __future__ import annotations

import hashlib
import json
import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from capture_desktop.screen_review import ReviewScreen
from capture_desktop.state import CaptureState
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QTabWidget,
)


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _package(root):
    root.mkdir()
    _write_json(
        root / "manifest.json", {"sessionId": "authored-review", "state": "finalized_recovered"},
    )
    first = {
        "checkpointId": "duplicate", "name": "Trial 零", "originalTimestampNs": "99",
        "effectiveTimestampNs": "0", "tags": ["touch <x>", "α"],
        "structuredFields": {"phase": "trial", "null": None, "zero": 0, "flag": False},
        "notes": "Retained original notes\nsecond line",
        "timestampModified": True, "modificationReason": "authored correction",
        "revisionHistory": [{"effectiveTimestampNs": "99", "reason": "original retained"}],
    }
    checkpoints = [
        first,
        {"checkpointId": "before", "name": "Before zero", "effectiveTimestampNs": "-1"},
        {"checkpointId": "large", "name": "Exact large time",
         "effectiveTimestampNs": "9007199254740993"},
        {"checkpointId": "bad", "name": "Unavailable time",
         "effectiveTimestampNs": None, "originalTimestampNs": "500"},
        dict(first),
    ]
    _write_json(root / "events/checkpoints.json", checkpoints)
    _write_json(root / "events/annotations.json", [
        {"annotationId": "a", "timestampNs": "10", "sourceId": "Source.A",
         "category": "Observation", "text": 'Operator noted <b>literal</b> & "quoted" 雪',
         "tags": ["needle.*", "α"], "futureField": {"keep": "all details"}},
        {"annotationId": "b", "timestampNs": "20", "sourceId": "source.a", "text": "Other source"},
        {"annotationId": "c", "timestampNs": "0", "text": "Session note"},
        {"annotationId": "d", "timestampNs": "bad", "sourceId": False, "text": "Unplaced note"},
    ])
    for folder, record in (
        ("one", {"sourceId": "Source.A", "streamId": "alpha", "cause": "disconnect",
                 "startSessionTimeNs": "5", "endSessionTimeNs": "15", "closed": False,
                 "estimatedLostCount": "9007199254740993"}),
        ("two", {"sourceId": "source.a", "streamId": "beta", "cause": "writer",
                 "startSessionTimeNs": "10", "closed": True, "estimatedLostCount": "0"}),
    ):
        path = root / "sources" / folder / "health/gaps.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return root


def _hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def recorded_package(tmp_path):
    path = _package(tmp_path / "authored.mmsession")
    original = _hashes(path)
    yield path
    assert _hashes(path) == original, "Review changed an authored package file"


def _open_events(screen, qapp):
    tabs = screen.findChild(QTabWidget, "ReviewViews")
    assert tabs is not None
    index = next(i for i in range(tabs.count()) if tabs.tabText(i) == "Events")
    QTest.mouseClick(
        tabs.tabBar(), Qt.MouseButton.LeftButton, pos=tabs.tabBar().tabRect(index).center(),
    )
    qapp.processEvents()
    assert tabs.currentIndex() == index


def _screen(qapp, path):
    screen = ReviewScreen(CaptureState())
    screen.resize(1200, 850)
    screen.load_package(str(path), recovered=True)
    screen.show()
    qapp.processEvents()
    _open_events(screen, qapp)
    return screen


def _control(screen, cls, name):
    widget = screen.findChild(cls, name)
    assert widget is not None, f"Missing event browser control: {name}"
    return widget


def _table(screen):
    return _control(screen, QTableView, "ReviewEventTable")


def _select_first(screen, qapp):
    table = _table(screen)
    assert table.model().rowCount() > 0
    cell = table.model().index(0, 0)
    table.scrollTo(cell)
    QTest.mouseClick(
        table.viewport(), Qt.MouseButton.LeftButton, pos=table.visualRect(cell).center(),
    )
    qapp.processEvents()
    return _control(screen, QPlainTextEdit, "ReviewEventDetails").toPlainText()


def _choose(box, value):
    index = box.findData(value)
    assert index >= 0
    box.setFocus()
    QTest.keyClick(box, Qt.Key.Key_Home)
    for _ in range(index):
        QTest.keyClick(box, Qt.Key.Key_Down)
    QTest.keyClick(box, Qt.Key.Key_Enter)
    assert box.currentData() == value


def _search_literal_note(screen, qapp):
    search = _control(screen, QLineEdit, "ReviewEventSearch")
    search.setFocus()
    QTest.keyClicks(search, "literal")
    qapp.processEvents()
    assert _table(screen).model().rowCount() == 1
    details = _select_first(screen, qapp)
    assert 'Operator noted <b>literal</b> & \\"quoted\\" 雪' in details
    assert '"futureField": {' in details and '"keep": "all details"' in details
    return details




def test_native_kind_source_and_literal_filters_clear_together(qapp, recorded_package):
    screen = _screen(qapp, recorded_package)
    try:
        _choose(_control(screen, QComboBox, "ReviewEventKind"), "Annotation")
        _choose(_control(screen, QComboBox, "ReviewEventSource"), "Source.A")
        search = _control(screen, QLineEdit, "ReviewEventSearch")
        search.setFocus()
        QTest.keyClicks(search, "needle.*")
        assert _table(screen).model().rowCount() == 1
        assert '"sourceId": "Source.A"' in _select_first(screen, qapp)
        _choose(_control(screen, QComboBox, "ReviewEventSource"), "source.a")
        assert _table(screen).model().rowCount() == 0
        assert _control(screen, QPlainTextEdit, "ReviewEventDetails").toPlainText() == ""
        QTest.mouseClick(
            _control(screen, QPushButton, "ReviewEventClear"), Qt.MouseButton.LeftButton,
        )
        assert search.text() == ""
        assert _table(screen).model().rowCount() == 11
        assert _control(screen, QComboBox, "ReviewEventKind").currentData() is None
        assert _control(screen, QComboBox, "ReviewEventSource").currentData() is None
    finally:
        screen.close()


def test_native_exact_time_order_original_fields_and_unknowns(qapp, recorded_package):
    screen = _screen(qapp, recorded_package)
    try:
        table = _table(screen)
        actual = [table.model().data(table.model().index(i, 0)) for i in range(11)]
        assert actual == ["-1", "0", "0", "0", "5", "10", "10", "20",
                          "9007199254740993", "Unavailable", "Unavailable"]
        _choose(_control(screen, QComboBox, "ReviewEventKind"), "Checkpoint")
        table.setFocus()
        table.setCurrentIndex(table.model().index(0, 0))
        QTest.keyClick(table, Qt.Key.Key_Down)
        details = _control(screen, QPlainTextEdit, "ReviewEventDetails")
        assert "Session time: 0 ns (effectiveTimestampNs)" in details.toPlainText()
        assert '"originalTimestampNs": "99"' in details.toPlainText()
        assert '"revisionHistory": [' in details.toPlainText()
        assert details.isReadOnly()
        before = details.toPlainText()
        details.setFocus()
        QTest.keyClicks(details, "MUST_NOT_EDIT")
        assert details.toPlainText() == before
        _choose(_control(screen, QComboBox, "ReviewEventSource"), "")
        assert table.model().rowCount() == 5
        table.setCurrentIndex(table.model().index(4, 0))
        assert "Unavailable: invalid effectiveTimestampNs" in details.toPlainText()
        assert '"originalTimestampNs": "500"' in details.toPlainText()
        assert '"effectiveTimestampNs": null' in details.toPlainText()
    finally:
        screen.close()


def test_native_gap_state_does_not_infer_closure_from_end(qapp, recorded_package):
    screen = _screen(qapp, recorded_package)
    try:
        _choose(_control(screen, QComboBox, "ReviewEventKind"), "Gap")
        table = _table(screen)
        assert table.model().rowCount() == 2
        assert table.model().data(table.model().index(0, 4)) == "Open · disconnect"
        assert table.model().data(table.model().index(1, 4)) == "Closed · writer"
        details = _select_first(screen, qapp)
        assert '"endSessionTimeNs": 15' in details and '"closed": false' in details
        assert '"estimatedLostCount": 9007199254740993' in details
        table.setFocus()
        QTest.keyClick(table, Qt.Key.Key_Down)
        details = _control(screen, QPlainTextEdit, "ReviewEventDetails").toPlainText()
        assert '"endSessionTimeNs": null' in details and '"closed": true' in details
    finally:
        screen.close()


def test_different_and_failed_package_loads_clear_stale_view_and_recover(
    qapp, recorded_package, tmp_path,
):
    screen = _screen(qapp, recorded_package)
    try:
        _search_literal_note(screen, qapp)
        empty = tmp_path / "empty.mmsession"
        empty.mkdir()
        _write_json(empty / "manifest.json", {"sessionId": "empty", "state": "finalized"})
        screen.load_package(str(empty))
        assert _table(screen).model().rowCount() == 0
        assert not _control(screen, QLineEdit, "ReviewEventSearch").isEnabled()
        assert _control(screen, QPlainTextEdit, "ReviewEventDetails").toPlainText() == ""
        assert screen._card_session.text().startswith("empty\n")
        assert not screen._recovered_banner.isVisible()
        invalid = tmp_path / "invalid.mmsession"
        invalid.mkdir()
        (invalid / "manifest.json").write_text("{invalid", encoding="utf-8")
        screen.load_package(str(recorded_package), recovered=True)
        _search_literal_note(screen, qapp)
        screen.load_package(str(invalid))
        assert "Could not load package" in screen._banner.text()
        assert _table(screen).model().rowCount() == 0
        assert _control(screen, QPlainTextEdit, "ReviewEventDetails").toPlainText() == ""
        assert screen._checkpoints.count() == screen._gaps.count() == screen._streams.count() == 0
        assert screen._card_session.text() == "—"
        assert not screen._btn_export.isEnabled() and screen._package == ""
        screen.load_package(str(recorded_package), recovered=True)
        assert _table(screen).model().rowCount() == 11
        assert _control(screen, QLineEdit, "ReviewEventSearch").text() == ""
        assert screen._btn_export.isEnabled()
        assert screen._recovered_banner.isVisible()
    finally:
        screen.close()


def test_native_long_session_uses_one_table_and_retains_all_rows(qapp, tmp_path):
    package = tmp_path / "long.mmsession"
    package.mkdir()
    _write_json(package / "manifest.json", {"sessionId": "long", "state": "finalized"})
    _write_json(package / "events/annotations.json", [
        {"timestampNs": str(i), "sourceId": f"s{i % 3}", "text": f"authored event {i}"}
        for i in range(2000)
    ])
    before = _hashes(package)
    screen = _screen(qapp, package)
    try:
        assert _table(screen).model().rowCount() == 2000
        assert len(screen.findChildren(QTableView)) == 1
        search = _control(screen, QLineEdit, "ReviewEventSearch")
        search.setFocus()
        QTest.keyClicks(search, "authored event 1997")
        assert _table(screen).model().rowCount() == 1
        assert "Session time: 1997 ns" in _select_first(screen, qapp)
        assert _hashes(package) == before
    finally:
        screen.close()

def test_native_search_keeps_literal_notes_and_package_bytes(qapp, recorded_package):
    before = _hashes(recorded_package)
    screen = _screen(qapp, recorded_package)
    try:
        details = _search_literal_note(screen, qapp)
        assert "needle.*" in details.casefold()
        assert _hashes(recorded_package) == before
    finally:
        screen.close()


def test_actual_mainwindow_opens_review_without_capture_connection(
    qapp, recorded_package, monkeypatch, tmp_path,
):
    from capture_desktop.app import MainWindow
    from PySide6.QtWidgets import QFileDialog

    window = MainWindow(auto_connect=False, analysis_only=True)
    window.show()
    try:
        window.tabs.setCurrentWidget(window.review)
        monkeypatch.setattr(
            QFileDialog, "getExistingDirectory", lambda *_a, **_k: str(recorded_package),
        )
        QTest.mouseClick(window.review._btn_open, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert window.review.summary.session_id == "authored-review"
        assert not window._transport.isVisible()
        assert not window.tabs.isTabVisible(window.tabs.indexOf(window.capture))
        assert not window.state.connected
        assert window.state.package_path == ""
        assert window._session_header.is_sealed
        assert window._session_header.package_path == str(recorded_package.resolve())
        assert window.review._recovered_banner.isVisible()
        window.tabs.setCurrentWidget(window.analysis)
        window.tabs.setCurrentWidget(window.review)
        assert window._session_header.package_path == str(recorded_package.resolve())
        window.review.load_package(str(tmp_path / "missing"))
        assert window.review.summary is None
        assert not window._session_header.is_sealed
        assert not window.review._btn_export.isEnabled()
    finally:
        window.close()


def test_review_refuses_active_package_and_keeps_source_bytes(qapp, tmp_path):
    package = tmp_path / "active.mmsession"
    package.mkdir()
    _write_json(package / "manifest.json", {"sessionId": "active", "state": "recording"})
    before = _hashes(package)
    screen = _screen(qapp, package)
    try:
        assert "Choose a finalized session" in screen._banner.text()
        assert screen.summary is None
        assert not screen._btn_export.isEnabled()
        assert _table(screen).model().rowCount() == 0
        assert _hashes(package) == before
    finally:
        screen.close()


def test_non_windows_transport_failure_is_actionable_without_touching_files():
    import os

    from capture_protocol.control_client import ControlClient, ControlClientError

    if os.name == "nt":
        pytest.skip("Windows named-pipe transport remains supported")
    with pytest.raises(ControlClientError, match="Windows named pipes"):
        ControlClient("/not/a/pipe").connect()
