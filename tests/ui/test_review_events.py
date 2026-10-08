# SPDX-License-Identifier: GPL-3.0-only
"""Real Qt Review consumers with authored physical packages and original-screen control."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import sys
import time
import uuid
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from capture_desktop import theme
from capture_desktop.screen_review import ReviewScreen
from capture_desktop.state import CaptureState
from PySide6 import __version__ as qt_version
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

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "docs/evidence/review-events-31a349052b90/baseline/screen_review.py"
BASELINE_SHA256 = "e5aff59de4b194123ca4c4518b34e7b6103326fbd6b0280e2122d984d01072ec"


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


def test_original_absence_and_native_written_record_receiving(qapp, recorded_package):
    output = ROOT / "build/evidence" / f"review-events-{uuid.uuid4().hex[:12]}"
    output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema": "capturesuite.review-events-receiving.v1",
        "accepted": False, "python": sys.version, "platform": platform.platform(),
        "qt": qt_version, "baseline_sha256": BASELINE_SHA256,
        "github_checkout": os.environ.get("GITHUB_SHA"),
        "inputs_before": _hashes(recorded_package), "checks": [], "screenshots": {},
    }
    _write_json(output / "authored-inputs.json", {
        name: (recorded_package / name).read_text(encoding="utf-8")
        for name in receipt["inputs_before"]
    })
    started = time.perf_counter()
    original = None
    candidate = None
    try:
        assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == BASELINE_SHA256
        spec = importlib.util.spec_from_file_location(
            "capture_desktop._review_original_31a", BASELINE,
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = module.ReviewScreen(CaptureState())
        original.resize(1200, 850)
        original.load_package(str(recorded_package), recovered=True)
        original.show()
        qapp.processEvents()
        assert original._checkpoints.count() == 5 and original._gaps.count() == 2
        with pytest.raises(AssertionError, match="Missing event browser control") as failure:
            _search_literal_note(original, qapp)
        receipt["baseline_expected_failure"] = {
            "type": type(failure.value).__name__, "message": str(failure.value),
            "loaded_checkpoint_count": original._checkpoints.count(),
            "loaded_gap_count": original._gaps.count(),
        }
        assert original.grab().save(str(output / "original-overview.png"))
        original.close()
        candidate = _screen(qapp, recorded_package)
        assert _table(candidate).model().rowCount() == 11
        details = _search_literal_note(candidate, qapp)
        receipt["selected_details"] = details
        receipt["checks"].append("Native keyboard search and selected literal annotation details")
        for setting in ("dark", "light"):
            theme.apply_theme(qapp, setting=setting)
            qapp.processEvents()
            image = output / f"events-{setting}.png"
            assert candidate.grab().save(str(image))
            receipt["screenshots"][image.name] = hashlib.sha256(image.read_bytes()).hexdigest()
        receipt["inputs_after"] = _hashes(recorded_package)
        assert receipt["inputs_after"] == receipt["inputs_before"]
        receipt["checks"].append("Every physical package byte unchanged")
        receipt["source_sha256"] = {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "desktop/capture_desktop/review_events.py",
                "desktop/capture_desktop/widgets_review_events.py",
                "desktop/capture_desktop/screen_review.py",
                "libs/python/capture_session/capture_session/package_reader.py",
                "tests/ui/test_review_events.py",
            )
        }
        receipt["accepted"] = True
    except Exception as exc:
        receipt["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        receipt["seconds"] = time.perf_counter() - started
        _write_json(output / "receipt.json", receipt)
        for screen in (original, candidate):
            if screen is not None:
                screen.close()
                screen.deleteLater()
        theme.apply_theme(qapp, setting="dark")
        qapp.processEvents()


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
