# SPDX-License-Identifier: GPL-3.0-only
"""Receive the current source picker, saved history, comparison and nested gallery together."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def _files(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


def _wait(predicate, timeout_ms: int = 60_000) -> None:
    """Use native Qt event delivery while an actual analysis worker is alive."""
    from PySide6.QtCore import QEventLoop, QTimer

    if predicate():
        return
    loop = QEventLoop()
    poll = QTimer()
    deadline = QTimer()
    deadline.setSingleShot(True)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline.timeout.connect(loop.quit)
    poll.start(10)
    deadline.start(timeout_ms)
    try:
        loop.exec()
    finally:
        poll.stop()
        deadline.stop()
    assert predicate(), "the native analysis event loop did not settle"


def test_sources_history_comparison_and_gallery_share_package_lifetime(
    qapp, tmp_path: Path, monkeypatch,
):
    import capture_analysis
    from capture_analysis import JobParams
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLabel

    from tests.analysis.test_numeric_cli_receiving import retained_files
    from tests.ui.test_analysis_history import _select
    from tests.ui.test_analysis_sources import (
        _choose,
        _close,
        _package,
        _screen,
        _warning_timer,
    )

    checks = []
    release = threading.Event()
    written = threading.Event()
    actual_results = []
    actual_calls = []
    screen = None
    timer = None
    evidence = Path(os.environ["CAPTURE_ANALYSIS_COMPOSITION_EVIDENCE"]) \
        if os.environ.get("CAPTURE_ANALYSIS_COMPOSITION_EVIDENCE") else tmp_path / "receipt"
    evidence.mkdir(parents=True, exist_ok=True)

    def check(name: str, condition: bool, details=None) -> None:
        checks.append({"name": name, "passed": bool(condition), "details": details})
        assert condition, name

    first = _package(tmp_path / "first μ.mmsession")
    second = _package(tmp_path / "second μ.mmsession")
    raw_before = {str(p): retained_files(p) for p in (first, second)}
    real_run = capture_analysis.run
    # Warm actual plotting synchronously. The held QThread runs a real features
    # job; no loader, handler, result, plot or output format is replaced.
    a = real_run(first, JobParams(command="all", sources=["sampler.a"],
                                overwrite_job_id="retained-a"))
    b = real_run(first, JobParams(command="all", sources=["sampler.b"],
                                overwrite_job_id="retained-b"))
    seeds = {str(a.job_dir): _files(a.job_dir), str(b.job_dir): _files(b.job_dir)}
    check("actual source-filtered retained jobs contain nested numeric figures",
          len(list((a.job_dir / "figures/numeric").rglob("*.png"))) == 2
          and len(list((b.job_dir / "figures/numeric").rglob("*.png"))) == 1)

    def held_run(package, params, **kwargs):
        actual_calls.append({"package": str(package), "params": params.to_dict()})
        result = real_run(package, params, **kwargs)
        actual_results.append(result)
        written.set()
        if not release.wait(120):
            raise AssertionError("receiver did not release the actual written result")
        return result

    try:
        screen = _screen(qapp, first)
        screen.resize(1500, 950)
        timer, warnings = _warning_timer(qapp)
        screen._command.setCurrentIndex(screen._command.findData("features"))
        _choose(qapp, screen._sources, {"sampler.b"})
        _select(screen._history, a.job_id)
        QTest.mouseClick(screen._history._open, Qt.MouseButton.LeftButton)
        bar = screen._inspector._parameters
        check("history binds the retained job to the gallery and comparison inspector",
              screen._history.loaded_job_id == a.job_id
              and screen._last_job_dir == str(a.job_dir)
              and screen._gallery._tabs.count() == 3
              and bar._button.isEnabled()
              and bar._source.job_id == a.job_id)
        QTest.mouseClick(bar._button, Qt.MouseButton.LeftButton)
        prior_dialog = bar._dialog
        check("retained parameters can be opened from the history-loaded inspector",
              prior_dialog is not None and prior_dialog.isVisible())
        monkeypatch.setattr(capture_analysis, "run", held_run)
        QTest.mouseClick(screen._btn_run, Qt.MouseButton.LeftButton)
        check("run owns the source snapshot and disables history before thread startup",
              screen._thread is not None and screen._worker._sources == ("sampler.b",)
              and not screen._btn_run.isEnabled()
              and not screen._history._refresh.isEnabled()
              and not screen._history._open.isEnabled()
              and not screen._history._jobs.isEnabled())
        check("starting an actual job clears all previously loaded result associations",
              screen._history.loaded_job_id == ""
              and screen._last_job_dir == ""
              and screen._gallery._tabs.count() == 1
              and bar._source is None and bar._dialog is None
              and not bar._button.isEnabled())
        # Change the future UI choice, without changing the actual worker input.
        screen._sources._mode.setCurrentIndex(screen._sources._mode.findData("all"))
        check("future source selection refresh cannot re-enable busy history controls",
              screen._sources.mode == "all" and screen._worker._sources == ("sampler.b",)
              and not screen._history._refresh.isEnabled()
              and not screen._btn_run.isEnabled())
        _wait(written.is_set)
        result = actual_results[0]
        params = json.loads((result.job_dir / "params.json").read_text(encoding="utf-8"))
        inventory = json.loads((result.job_dir / "features/_schema.json").read_text())
        check("the real persisted job used the selected source snapshot",
              params["sources"] == ["sampler.b"]
              and {row["sourceId"] for row in inventory["tables"].values()} == {"sampler.b"}
              and actual_calls[0]["params"]["sources"] == ["sampler.b"],
              {"job": result.job_id, "params_sources": params["sources"]})
        check("written output does not release busy controls before QThread cleanup",
              screen._thread is not None and not screen._history._refresh.isEnabled()
              and not screen._btn_run.isEnabled())
        screen.set_package(str(second))
        check("package change clears history, figures and comparison while resetting sources",
              screen._history.package == str(second.resolve())
              and screen._history.loaded_job_id == ""
              and screen._gallery._tabs.count() == 1
              and bar._source is None and bar._dialog is None
              and screen._sources.mode == "all" and screen._sources.selected_ids == ()
              and not screen._history._refresh.isEnabled())
        release.set()
        _wait(lambda: screen._thread is None)
        check("late source-filtered completion stays unbound to the current package",
              screen._last_job_dir == "" and screen._history.loaded_job_id == ""
              and screen._gallery._tabs.count() == 1
              and bar._source is None and not bar._button.isEnabled()
              and screen._history._refresh.isEnabled()
              and screen._btn_run.isEnabled()
              and "previous package" in screen._log.toPlainText())
        check("real worker completed without a failure dialog",
              not warnings and len(actual_calls) == 1, warnings)
        screen.set_package(str(first))
        _select(screen._history, result.job_id)
        QTest.mouseClick(screen._history._open, Qt.MouseButton.LeftButton)
        check("returning to the original package reopens the actual late result",
              screen._history.loaded_job_id == result.job_id
              and bar._source is not None and bar._source.params["sources"] == ["sampler.b"]
              and bar._button.isEnabled())
        QTest.mouseClick(bar._button, Qt.MouseButton.LeftButton)
        comparison = bar._dialog
        assert comparison is not None
        # Select the existing comparison target through the owner's dialog seam;
        # both originals are still read and verified by its unchanged loader.
        comparison._read_other(a.job_dir)
        differences = {row.pointer: (row.other_json, row.loaded_json)
                       for row in comparison._rows}
        check("comparison reads the current producer's exact source parameters",
              differences.get("/sources/0") == ('"sampler.a"', '"sampler.b"')
              and comparison._source.job_id == result.job_id
              and not comparison._error.text(), differences)
        _select(screen._history, a.job_id)
        QTest.mouseClick(screen._history._open, Qt.MouseButton.LeftButton)
        check("opening another retained job clears the previous comparison dialog",
              bar._dialog is None and bar._source.job_id == a.job_id
              and bar._source.params["sources"] == ["sampler.a"]
              and screen._history.loaded_job_id == a.job_id)
        tabs = screen._gallery._tabs
        paths = [tabs.tabToolTip(i) for i in range(1, tabs.count())]
        expected = sorted(p.relative_to(a.job_dir / "figures").as_posix()
                          for p in (a.job_dir / "figures/numeric").rglob("*.png"))
        check("reopened nested gallery identifies exactly the selected-source figures",
              paths == expected and len(paths) == 2, paths)
        pixels = []
        for index, relative in enumerate(paths, 1):
            label = tabs.widget(index).findChild(QLabel)
            assert label is not None and not label.pixmap().isNull()
            pixels.append(label.pixmap().toImage() ==
                          QPixmap(str(a.job_dir / "figures" / relative)).toImage())
        check("both reopened image widgets retain the exact actual saved pixels", all(pixels))
        check("gallery navigation preserves the independent future source choice",
              screen._sources.mode == "all" and screen._sources.selected_ids == ())
        qapp.processEvents()
        assert screen.grab().save(str(evidence / "composed-history-gallery.png"))
        QTest.mouseClick(bar._button, Qt.MouseButton.LeftButton)
        check("the replacement inspector opens only its own parameter source",
              bar._dialog is not None and bar._dialog._source.job_id == a.job_id)
        retained = {str(p): _files(p) for p in (first, second)}
        screen.set_package(str(second))
        check("another package switch clears the current comparison and gallery together",
              bar._dialog is None and bar._source is None
              and screen._history.loaded_job_id == ""
              and screen._gallery._tabs.count() == 1
              and screen._sources.mode == "all" and screen._sources.selected_ids == ())
        check("all saved jobs and raw bytes remain unchanged through history and comparison",
              retained == {str(p): _files(p) for p in (first, second)}
              and raw_before == {str(p): retained_files(p) for p in (first, second)}
              and seeds == {str(a.job_dir): _files(a.job_dir), str(b.job_dir): _files(b.job_dir)})
        check("receiving view actions never start a second analysis job",
              len(actual_calls) == 1 and screen._thread is None)
    finally:
        release.set()
        if screen is not None and screen._thread is not None:
            screen._cancel_job()
            _wait(lambda: screen._thread is None, 120_000)
        if timer is not None:
            timer.stop()
        if screen is not None:
            _close(qapp, screen)
        (evidence / "receipt.json").write_text(
            json.dumps({"checks": checks, "passed": sum(row["passed"] for row in checks),
                        "failed": sum(not row["passed"] for row in checks),
                        "worker_calls": actual_calls,
                        "methodology": "Real numeric MCAP jobs and QThread; receiver holds only "
                                       "the return of an already-persisted real feature job. "
                                       "Native Qt event loop, unchanged source chooser and "
                                       "history Open buttons, unchanged comparison read action."},
                       indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
        )
