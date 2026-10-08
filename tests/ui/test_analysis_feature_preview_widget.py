# SPDX-License-Identifier: GPL-3.0-only
"""Real Qt feature preview: exact retained values and asynchronous lifecycle."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from threading import Event, get_ident

import pyarrow as pa
import pyarrow.parquet as pq
from capture_desktop import widgets_analysis_feature_preview as ui
from PySide6.QtCore import QCoreApplication, QEvent, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QWidget,
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _job(root: Path, name: str, tables: list[tuple[str, pa.Table]]) -> Path:
    job = root / name
    job.mkdir()
    params = {"command": "features", "extra": {"fixture": "retained-preview-widget"}}
    raw = (json.dumps(params, ensure_ascii=False, indent=2) + "\n").encode()
    (job / "params.json").write_bytes(raw)
    outputs = [
        {"kind": "params", "relativePath": "params.json", "bytes": len(raw), "sha256": _sha(raw)}
    ]
    schema_doc = {"schemaId": "capture.analysis_feature_schema/1", "tables": {}}
    for relative, table in tables:
        target = job / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, target, row_group_size=100)
        data = target.read_bytes()
        outputs.append(
            {
                "kind": "feature_parquet",
                "relativePath": relative,
                "bytes": len(data),
                "sha256": _sha(data),
            }
        )
        schema_doc["tables"][relative] = {
            "featureSchemaVersion": 1,
            "rows": table.num_rows,
            "columns": [
                {
                    "name": name,
                    "units": "ns" if name == "t/native_ns" else "",
                    "calibrated": name == "voltage",
                    "description": "Literal <b>retained</b> µ metadata" if i == 0 else "",
                }
                for i, name in enumerate(table.column_names)
            ],
        }
    schema_path = job / "features/_schema.json"
    schema_path.parent.mkdir(exist_ok=True)
    schema_raw = (json.dumps(schema_doc, ensure_ascii=False, indent=2) + "\n").encode()
    schema_path.write_bytes(schema_raw)
    outputs.append(
        {
            "kind": "feature_schema",
            "relativePath": "features/_schema.json",
            "bytes": len(schema_raw),
            "sha256": _sha(schema_raw),
        }
    )
    manifest = {
        "schemaId": "capture.analysis_job/1",
        "jobId": name,
        "sessionId": "synthetic-widget-session",
        "status": "completed",
        "captureAnalysisVersion": "synthetic-test-version",
        "manifestSha256": "a" * 64,
        "paramsDigest": _sha(
            json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ),
        "outputs": outputs,
    }
    (job / "job_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return job


def _wait(qapp, predicate, *, timeout: float = 8.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        # Yield the GIL for real worker reads while retaining an active Qt loop.
        QTest.qWait(2)
        time.sleep(0.001)
    assert predicate(), "The expected native preview state did not arrive."


def _control(parent, cls, name):
    value = parent.findChild(cls, name)
    assert value is not None, name
    return value


def _load(qapp, job: Path):
    bar = ui.FeatureTableBar()
    bar.show()
    bar.load_job_dir(job)
    button = _control(bar, QPushButton, "PreviewFeatureTable")
    _wait(qapp, button.isEnabled)
    return bar


def _open(qapp, bar):
    button = _control(bar, QPushButton, "PreviewFeatureTable")
    button.setFocus()
    QTest.keyClick(button, Qt.Key.Key_Space)
    _wait(qapp, lambda: bar.findChild(QDialog, "FeaturePreviewDialog") is not None)
    dialog = _control(bar, QDialog, "FeaturePreviewDialog")
    assert dialog.isVisible()
    assert not dialog.isModal()
    status = _control(dialog, QLabel, "FeaturePreviewStatus")
    _wait(qapp, lambda: not status.text().startswith("Reading"))
    return dialog


def _dispose(qapp, bar):
    bar.clear()
    bar.close()
    bar.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def _one_table(values=(1, 2, 3)) -> pa.Table:
    return pa.table({"t/native_ns": pa.array(values, type=pa.int64())})


def test_real_parquet_exact_values_types_metadata_and_read_only_conservation(qapp, tmp_path):
    table = pa.table(
        {
            "t/native_ns": pa.array([9007199254740993, -(2**63), None, 2**63 - 1], type=pa.int64()),
            "unsigned": pa.array([2**64 - 1, 0, None, 9007199254740995], type=pa.uint64()),
            "voltage": pa.array([None, float("nan"), float("inf"), -0.0], type=pa.float64()),
            "literal <name> µ": pa.array(
                ["NULL", "NaN", "<b>µ\nliteral</b>", ""], type=pa.string()
            ),
            "active": pa.array([True, False, None, True], type=pa.bool_()),
        }
    )
    job = _job(tmp_path, "exact-values", [("features/exact.parquet", table)])
    before = _files(tmp_path)
    bar = _load(qapp, job)
    try:
        dialog = _open(qapp, bar)
        identity = _control(dialog, QLabel, "FeaturePreviewIdentity")
        assert identity.text() == "Table: features/exact.parquet\nJob: exact-values"
        assert identity.textFormat() == Qt.TextFormat.PlainText
        view = _control(dialog, QTableView, "FeaturePreviewTable")
        model = view.model()
        assert (model.rowCount(), model.columnCount()) == (4, 5)
        assert [
            model.headerData(i, Qt.Orientation.Horizontal) for i in range(5)
        ] == table.column_names
        expected = [
            ["9007199254740993", "18446744073709551615", "NULL", '"NULL"', "true"],
            ["-9223372036854775808", "0", "NaN", '"NaN"', "false"],
            ["NULL", "NULL", "Infinity", '"<b>µ\\nliteral</b>"', "NULL"],
            ["9223372036854775807", "9007199254740995", "-0.0", '""', "true"],
        ]
        assert [
            [model.data(model.index(row, column)) for column in range(5)] for row in range(4)
        ] == expected
        assert all(
            not model.flags(model.index(row, column)) & Qt.ItemFlag.ItemIsEditable
            for row in range(4)
            for column in range(5)
        )
        index = model.index(0, 0)
        assert not model.setData(index, "999", Qt.ItemDataRole.EditRole)
        assert model.data(index) == "9007199254740993"
        assert not view.isSortingEnabled()
        view.setCurrentIndex(model.index(2, 3))
        qapp.processEvents()
        complete = _control(dialog, QPlainTextEdit, "FeaturePreviewCellValue")
        assert complete.isReadOnly()
        assert complete.toPlainText() == '"<b>µ\\nliteral</b>"'

        columns = _control(dialog, QTableView, "FeaturePreviewColumns").model()
        assert [
            [columns.data(columns.index(row, column)) for column in range(4)] for row in range(5)
        ] == [
            ["t/native_ns", "int64", "ns", "false"],
            ["unsigned", "uint64", "", "false"],
            ["voltage", "double", "", "true"],
            ["literal <name> µ", "string", "", "false"],
            ["active", "bool", "", "false"],
        ]
        assert columns.data(columns.index(0, 4)) == "Literal <b>retained</b> µ metadata"
        provenance = _control(dialog, QPlainTextEdit, "FeaturePreviewProvenance")
        assert provenance.isReadOnly()
        record = json.loads(provenance.toPlainText())
        assert record["job_id"] == "exact-values"
        assert record["session_id"] == "synthetic-widget-session"
        assert record["table_sha256"] == _sha((job / "features/exact.parquet").read_bytes())
        assert record["manifest_sha256"] == _sha((job / "job_manifest.json").read_bytes())
        assert (record["total_rows"], record["shown_rows"], record["preview_row_limit"]) == (
            4,
            4,
            200,
        )
        assert (
            _control(dialog, QLabel, "FeaturePreviewStatus").textFormat() == Qt.TextFormat.PlainText
        )
        assert _files(tmp_path) == before
    finally:
        _dispose(qapp, bar)
    assert _files(tmp_path) == before


def test_first_200_rows_and_empty_table_keep_actual_column_metadata(qapp, tmp_path):
    full = _one_table(range(205))
    empty = _one_table([])
    job = _job(
        tmp_path, "bounded", [("features/full.parquet", full), ("features/empty.parquet", empty)]
    )
    before = _files(tmp_path)
    bar = _load(qapp, job)
    try:
        choice = _control(bar, QComboBox, "FeatureTableChoice")
        assert [choice.itemText(i) for i in range(choice.count())] == [
            "features/full.parquet",
            "features/empty.parquet",
        ]
        dialog = _open(qapp, bar)
        model = _control(dialog, QTableView, "FeaturePreviewTable").model()
        assert model.rowCount() == 200
        assert model.data(model.index(199, 0)) == "199"
        summary = _control(dialog, QLabel, "FeaturePreviewSummary").text()
        assert "200 of 205" in summary and "200 rows" in summary
        choice.setFocus()
        QTest.keyClick(choice, Qt.Key.Key_Down)
        qapp.processEvents()
        assert choice.currentText() == "features/empty.parquet"
        _wait(
            qapp,
            lambda: (
                not any(d.isVisible() for d in bar.findChildren(QDialog, "FeaturePreviewDialog"))
            ),
        )
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        empty_dialog = _open(qapp, bar)
        empty_model = _control(empty_dialog, QTableView, "FeaturePreviewTable").model()
        assert (empty_model.rowCount(), empty_model.columnCount()) == (0, 1)
        assert (
            "Empty retained table (0 rows)"
            in _control(empty_dialog, QLabel, "FeaturePreviewSummary").text()
        )
        assert _control(empty_dialog, QTableView, "FeaturePreviewColumns").model().rowCount() == 1
        empty_dialog.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()
        choice.setCurrentIndex(-1)
        button = _control(bar, QPushButton, "PreviewFeatureTable")
        assert not button.isEnabled()
        button.click()
        qapp.processEvents()
        assert not any(d.isVisible() for d in bar.findChildren(QDialog, "FeaturePreviewDialog"))
        choice.setCurrentIndex(0)
        assert button.isEnabled()
        assert _files(tmp_path) == before
    finally:
        _dispose(qapp, bar)


def test_catalog_and_changed_output_refusals_are_visible_and_do_not_write(qapp, tmp_path):
    featureless = _job(tmp_path, "no-tables", [])
    bar = ui.FeatureTableBar()
    bar.show()
    try:
        bar.load_job_dir(featureless)
        status = _control(bar, QLabel, "FeatureTableStatus")
        _wait(qapp, lambda: "no retained feature tables" in status.text())
        assert not _control(bar, QPushButton, "PreviewFeatureTable").isEnabled()

        damaged = _job(tmp_path, "bad-manifest", [("features/value.parquet", _one_table())])
        (damaged / "job_manifest.json").write_text("<b>not JSON</b>")
        damaged_before = _files(damaged)
        bar.load_job_dir(damaged)
        _wait(qapp, lambda: "unavailable" in status.text())
        assert status.textFormat() == Qt.TextFormat.PlainText
        assert not _control(bar, QPushButton, "PreviewFeatureTable").isEnabled()
        assert _files(damaged) == damaged_before

        good = _job(tmp_path, "changed-output", [("features/value.parquet", _one_table())])
        bar.load_job_dir(good)
        _wait(qapp, _control(bar, QPushButton, "PreviewFeatureTable").isEnabled)
        retained = good / "features/value.parquet"
        retained.write_bytes(retained.read_bytes() + b"intentional fixture mutation")
        changed_before = _files(good)
        dialog = _open(qapp, bar)
        assert "unavailable" in _control(dialog, QLabel, "FeaturePreviewStatus").text()
        assert _control(dialog, QTableView, "FeaturePreviewTable").model().rowCount() == 0
        assert not _control(dialog, QPlainTextEdit, "FeaturePreviewProvenance").toPlainText()
        assert _files(good) == changed_before
    finally:
        _dispose(qapp, bar)


def test_catalog_work_is_off_thread_and_only_latest_pending_job_is_read(
    qapp, tmp_path, monkeypatch
):
    jobs = [
        _job(tmp_path, name, [("features/value.parquet", _one_table())])
        for name in ("first", "superseded", "latest")
    ]
    original = ui.load_feature_catalog
    entered, release = Event(), Event()
    calls = []
    main_thread = get_ident()

    def delayed(job_dir, *, cancel_event=None):
        calls.append((Path(job_dir).name, get_ident()))
        if Path(job_dir) == jobs[0]:
            entered.set()
            assert release.wait(8), "Test barrier was not released."
        return original(job_dir, cancel_event=cancel_event)

    monkeypatch.setattr(ui, "load_feature_catalog", delayed)
    bar = ui.FeatureTableBar()
    bar.show()
    ticks = []
    timer = QTimer()
    timer.setInterval(1)
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start()
    try:
        bar.load_job_dir(jobs[0])
        _wait(qapp, entered.is_set)
        started = time.monotonic()
        bar.load_job_dir(jobs[1])
        bar.load_job_dir(jobs[2])
        assert time.monotonic() - started < 0.5
        _wait(qapp, lambda: len(ticks) >= 3)
        assert calls == [("first", calls[0][1])]
        release.set()
        _wait(qapp, _control(bar, QPushButton, "PreviewFeatureTable").isEnabled)
        assert [name for name, _thread in calls] == ["first", "latest"]
        assert all(thread != main_thread for _name, thread in calls)
        dialog = _open(qapp, bar)
        record = json.loads(
            _control(dialog, QPlainTextEdit, "FeaturePreviewProvenance").toPlainText()
        )
        assert record["job_id"] == "latest"
    finally:
        release.set()
        timer.stop()
        _dispose(qapp, bar)


def test_clear_and_reload_discard_late_preview_without_blocking_qt(qapp, tmp_path, monkeypatch):
    first = _job(tmp_path, "first-preview", [("features/value.parquet", _one_table())])
    latest = _job(tmp_path, "latest-preview", [("features/value.parquet", _one_table([91]))])
    original = ui.load_feature_preview
    entered, release, completed = Event(), Event(), Event()
    captured_events = []
    main_thread = get_ident()
    read_threads = []

    def delayed(catalog, relative_path, *, cancel_event=None):
        read_threads.append(get_ident())
        if catalog.source.job_id == "first-preview":
            captured_events.append(cancel_event)
            entered.set()
            assert release.wait(8), "Test barrier was not released."
            # Simulate a filesystem reader finishing after it missed cancellation.
            result = original(catalog, relative_path)
            completed.set()
            return result
        return original(catalog, relative_path, cancel_event=cancel_event)

    monkeypatch.setattr(ui, "load_feature_preview", delayed)
    before = _files(tmp_path)
    bar = _load(qapp, first)
    try:
        QTest.mouseClick(
            _control(bar, QPushButton, "PreviewFeatureTable"), Qt.MouseButton.LeftButton
        )
        _wait(qapp, entered.is_set)
        dialog = _control(bar, QDialog, "FeaturePreviewDialog")
        started = time.monotonic()
        bar.clear()
        bar.load_job_dir(latest)
        assert time.monotonic() - started < 0.5
        assert captured_events[0].is_set()
        assert not dialog.isVisible()
        release.set()
        _wait(qapp, completed.is_set)
        _wait(qapp, _control(bar, QPushButton, "PreviewFeatureTable").isEnabled)
        assert not any(d.isVisible() for d in bar.findChildren(QDialog, "FeaturePreviewDialog"))
        current = _open(qapp, bar)
        view = _control(current, QTableView, "FeaturePreviewTable")
        assert view.model().data(view.model().index(0, 0)) == "91"
        record = json.loads(
            _control(current, QPlainTextEdit, "FeaturePreviewProvenance").toPlainText()
        )
        assert record["job_id"] == "latest-preview"
        assert all(thread != main_thread for thread in read_threads)
        assert _files(tmp_path) == before
    finally:
        release.set()
        _dispose(qapp, bar)


def test_parent_deletion_cancels_active_read_and_late_completion_has_no_ui(
    qapp, tmp_path, monkeypatch
):
    job = _job(tmp_path, "deleted-parent", [("features/value.parquet", _one_table())])
    original = ui.load_feature_preview
    entered, release, completed = Event(), Event(), Event()
    captured_events = []

    def delayed(catalog, relative_path, *, cancel_event=None):
        captured_events.append(cancel_event)
        entered.set()
        assert release.wait(8), "Test barrier was not released."
        result = original(catalog, relative_path)
        completed.set()
        return result

    monkeypatch.setattr(ui, "load_feature_preview", delayed)
    parent = QWidget()
    bar = ui.FeatureTableBar(parent)
    parent.show()
    bar.show()
    bar.load_job_dir(job)
    _wait(qapp, _control(bar, QPushButton, "PreviewFeatureTable").isEnabled)
    QTest.mouseClick(_control(bar, QPushButton, "PreviewFeatureTable"), Qt.MouseButton.LeftButton)
    _wait(qapp, entered.is_set)
    destroyed = []
    parent.destroyed.connect(lambda: destroyed.append(True))
    try:
        parent.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()
        assert destroyed == [True]
        assert captured_events[0].is_set()
        release.set()
        _wait(qapp, completed.is_set)
        # Let the worker's queued completion reach the event loop after deletion.
        for _ in range(5):
            qapp.processEvents()
            QTest.qWait(2)
        assert not any(
            isinstance(widget, QDialog)
            and widget.objectName() == "FeaturePreviewDialog"
            and widget.isVisible()
            for widget in qapp.topLevelWidgets()
        )
    finally:
        release.set()
