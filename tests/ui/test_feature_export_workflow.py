# SPDX-License-Identifier: GPL-3.0-only
"""Exercise the native saved-result handoff with actual retained MCAP feature jobs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def _wait(predicate) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    if predicate():
        return
    loop = QEventLoop()
    deadline = QTimer()
    deadline.setSingleShot(True)
    poll = QTimer()
    deadline.timeout.connect(loop.quit)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline.start(30_000)
    poll.start(10)
    loop.exec()
    deadline.stop()
    poll.stop()
    assert predicate(), "actual export thread did not settle"


def _files(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


@pytest.fixture
def retained(tmp_path):
    from capture_analysis import JobParams, run

    from tests.ui.test_analysis_sources import _package

    package = _package(tmp_path / "two streams.mmsession")
    result = run(
        package,
        JobParams(command="all", sources=["sampler.a"], overwrite_job_id="saved-study"),
    )
    return package, result


def test_saved_result_exports_selected_columns_in_visible_order(qapp, retained, tmp_path):
    import pyarrow.parquet as pq
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    package, result = retained
    before = _files(package)
    screen = AnalysisScreen(CaptureState())
    screen.resize(1400, 900)
    screen.set_package(str(package))
    screen.show()
    QTest.mouseClick(screen._history._open, Qt.MouseButton.LeftButton)
    bar = screen._inspector._feature_export
    assert bar._button.isEnabled()
    QTest.mouseClick(bar._button, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    dialog = bar._dialog
    assert dialog is not None and dialog.isVisible()
    manifest = json.loads((result.job_dir / "job_manifest.json").read_text())
    assert manifest["sessionId"] in dialog._context.text()
    assert manifest["jobId"] in dialog._context.text()
    table = dialog._table.currentData()
    source = pq.read_table(result.job_dir / table["relativePath"])
    QTest.mouseClick(dialog._none, Qt.MouseButton.LeftButton)
    assert not dialog._export.isEnabled()
    assert dialog._columns.topLevelItemCount() >= 3
    first = dialog._columns.topLevelItem(0)
    third = dialog._columns.topLevelItem(2)
    expected = [third.text(0), first.text(0)]
    first.setCheckState(0, Qt.CheckState.Checked)
    third.setCheckState(0, Qt.CheckState.Checked)
    dialog._columns.setCurrentItem(third)
    QTest.mouseClick(dialog._up, Qt.MouseButton.LeftButton)
    QTest.mouseClick(dialog._up, Qt.MouseButton.LeftButton)
    assert dialog.selected_columns() == tuple(expected)
    # Finding one column never silently removes the other selected measurement.
    dialog._search.setText(expected[0])
    assert dialog.selected_columns() == tuple(expected)
    dialog._parent.setText(str(tmp_path))
    dialog._name.setText("ordered-measurements")
    QTest.mouseClick(dialog._export, Qt.MouseButton.LeftButton)
    _wait(lambda: dialog._worker is None)
    output = tmp_path / "ordered-measurements"
    exported = pq.read_table(output / "table.parquet")
    assert exported.column_names == expected
    assert exported.equals(source.select(expected), check_metadata=False)
    manifest = json.loads((output / "manifest.json").read_text())
    metadata = json.loads((output / "_schema.json").read_text())
    assert manifest["selection"]["columns"] == expected
    assert manifest["selection"]["rows"] == source.num_rows
    assert [c["name"] for c in metadata["tableMetadata"]["columns"]] == expected
    assert (output / "table.csv").read_text().splitlines()[0] == ",".join(
        f'"{name}"' for name in expected
    )
    assert "Exported" in dialog._status.text()
    assert dialog._open_folder.isVisible()
    assert _files(package) == before
    dialog.close()
    screen.close()


def test_export_refusal_can_retry_and_package_change_clears_context(
    qapp,
    retained,
    tmp_path,
):
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from tests.ui.test_analysis_sources import _package

    package, _result = retained
    screen = AnalysisScreen(CaptureState())
    screen.set_package(str(package))
    screen.show()
    screen._history._open.click()
    bar = screen._inspector._feature_export
    bar._button.click()
    dialog = bar._dialog
    assert dialog is not None
    existing = tmp_path / "keep-existing"
    existing.mkdir()
    (existing / "important.txt").write_text("keep")
    dialog._parent.setText(str(tmp_path))
    dialog._name.setText(existing.name)
    QTest.mouseClick(dialog._export, Qt.MouseButton.LeftButton)
    _wait(lambda: dialog._worker is None)
    assert "Export failed" in dialog._status.text()
    assert (existing / "important.txt").read_text() == "keep"
    assert not (existing / "manifest.json").exists()
    assert dialog._export.isEnabled()
    dialog._name.setText("retry-measurements")
    QTest.mouseClick(dialog._export, Qt.MouseButton.LeftButton)
    _wait(lambda: dialog._worker is None)
    assert (tmp_path / "retry-measurements/manifest.json").is_file()
    other = _package(tmp_path / "other.mmsession")
    screen.set_package(str(other))
    qapp.processEvents()
    assert not bar._button.isEnabled()
    assert bar._job is None
    assert bar._dialog is None
    assert not screen._last_job_dir
    assert screen._gallery._tabs.count() == 1
    screen.close()


def test_offline_window_opens_recorded_session_without_windows_transport(
    qapp,
    retained,
    tmp_path,
    monkeypatch,
):
    from capture_desktop.offline import OfflineWindow

    package, result = retained
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "app-state"))
    window = OfflineWindow(str(package))
    window.show()
    qapp.processEvents()
    assert window.analysis.package_path == str(package.resolve())
    assert window.analysis.summary is not None
    assert window._session_header.is_sealed
    assert window.analysis._history._jobs.count() == 1
    window.analysis._history._open.click()
    assert window.analysis._last_job_dir == str(result.job_dir)
    assert window.analysis._inspector._feature_export._button.isEnabled()
    choices = [
        window.analysis._command.itemData(i) for i in range(window.analysis._command.count())
    ]
    assert choices == ["qc", "all", "features", "plots"]
    window.close()


def test_unknown_duration_never_offers_a_fabricated_timeline(qapp, retained, monkeypatch, tmp_path):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from capture_desktop.offline import OfflineWindow

    package, _result = retained
    # This is the receiving condition seen in Ibis's actual MCAP session:
    # sealed file hashes are present, but no recorded end-time metadata.
    integrity_path = package / "integrity.json"
    integrity = json.loads(integrity_path.read_text())
    for row in integrity["files"]:
        row.pop("endSessionTimeNs", None)
    integrity_path.write_text(json.dumps(integrity))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "unknown-state"))
    window = OfflineWindow(str(package))
    window.show()
    qapp.processEvents()
    header = window._session_header
    assert window.analysis.summary.duration_ns <= 1
    assert not header._timeline._model.duration_known
    assert not header._cursor.text()
    assert not header._scope_picker._mark_start.isEnabled()
    assert not header._scope_picker._mark_end.isEnabled()
    QTest.mouseClick(header._timeline, Qt.MouseButton.LeftButton, pos=QPoint(300, 20))
    assert not header._cursor.text()
    header._scope_picker._mode.setCurrentIndex(header._scope_picker._mode.findData("range"))
    assert header._scope_picker.selection is None
    assert not header._scope_picker._end.text()
    window.close()
