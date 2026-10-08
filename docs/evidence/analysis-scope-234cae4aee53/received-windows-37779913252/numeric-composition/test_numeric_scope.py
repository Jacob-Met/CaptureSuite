# SPDX-License-Identifier: GPL-3.0-only
"""Receive the accepted UI against the separately accepted numeric pipeline."""

import json
import time
from pathlib import Path

import pandas as pd
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from tests.analysis.test_numeric_cli_receiving import make_package, retained_files
from tests.ui.test_analysis_scope import _close_widgets, _widgets


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def test_numeric_schema_priority_reaches_exact_ui_time_scope(qapp, tmp_path):
    package = make_package(tmp_path / "numeric scope μ.mmsession")
    before = retained_files(package)
    header, screen = _widgets(qapp, package)
    picker = header._scope_picker
    screen._command.setCurrentIndex(screen._command.findData("all"))
    picker._mode.setCurrentIndex(picker._mode.findData("range"))
    picker._start.setText("1.200000001")
    picker._end.setText("2.400000001")
    selected = screen.scope
    assert selected.start_ns == 1_200_000_001
    assert selected.end_ns == 2_400_000_001
    assert screen._btn_run.isEnabled()
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
        picker._mode.setCurrentIndex(picker._mode.findData("full"))
        deadline = time.monotonic() + 180
        while screen._thread is not None and time.monotonic() < deadline:
            QTest.qWait(20)
        assert screen._thread is None, "numeric analysis worker did not finish"
        assert not dialogs, dialogs
        job = Path(screen._last_job_dir)
        manifest = json.loads((job / "job_manifest.json").read_text())
        params = json.loads((job / "params.json").read_text())
        series = json.loads((job / "figures/sync_dashboard_series.json").read_text())
        schema = json.loads((job / "features/_schema.json").read_text())
        assert manifest["status"] == "completed"
        assert params["startSessionNs"] == selected.start_ns
        assert params["endSessionNs"] == selected.end_ns
        assert manifest["timeRange"]["startSessionNs"] == selected.start_ns
        assert manifest["timeRange"]["endSessionNs"] == selected.end_ns
        assert manifest["sourcesSelected"] == ["sampler.a", "sampler.b"]
        expected_times = list(range(1_250_000_000, 2_400_000_001, 50_000_000))
        assert len(series["series"]) == 3
        assert {item["label"] for item in series["series"]} == {
            "Numeric sampler.a/voltage · input 1",
            "Numeric sampler.a/force · input 1",
            "Numeric sampler.b/temperature · input 1",
        }
        for item in series["series"]:
            assert item["t_ns"] == expected_times
        assert len(schema["tables"]) == 3
        assert {(item["sourceId"], item["streamId"]) for item in schema["tables"].values()} == {
            ("sampler.a", "voltage"),
            ("sampler.a", "force"),
            ("sampler.b", "temperature"),
        }
        for name, descriptor in schema["tables"].items():
            assert name.startswith("features/numeric/")
            frame = pd.read_parquet(job / name)
            assert not frame.empty
            assert frame["t_start_ns"].min() >= selected.start_ns
            if descriptor["streamId"] == "force":
                # Its descriptor says EMG; schema dispatch must retain the
                # actual generic numeric values rather than decode EMG bytes.
                assert frame["input 1_mean"].between(3.0, 3.9).all()
        assert retained_files(package) == before
        (Path(__file__).parent / "numeric-ui-output.json").write_text(
            json.dumps({
                "selected_ns": [selected.start_ns, selected.end_ns],
                "actual_sample_ns": expected_times,
                "series_labels": [item["label"] for item in series["series"]],
                "source_ids": manifest["sourcesSelected"],
                "raw_files_unchanged": len(before),
                "params": params,
                "manifest": manifest,
            }, indent=2) + "\n"
        )
    finally:
        if screen._thread is not None:
            screen._cancel_job()
            while screen._thread is not None:
                QTest.qWait(20)
        timer.stop()
        _close_widgets(qapp, header, screen)
