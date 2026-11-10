# SPDX-License-Identifier: GPL-3.0-only
"""The table workspace exports actual saved values through its native controls."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pyarrow.parquet as parquet
from capture_desktop.widgets_feature_tables import FeatureTableView
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
# Reuse the existing real retained-job fixture and its independent value comparator.
spec = importlib.util.spec_from_file_location(
    "feature_export_samples", ROOT / "tests/analysis/test_feature_table_export.py"
)
samples = importlib.util.module_from_spec(spec)
spec.loader.exec_module(samples)


def test_native_selection_order_units_and_written_values(qtbot, tmp_path):
    job, table = samples.make_job(tmp_path)
    before = samples.inventory(job.parents[2])
    view = FeatureTableView()
    qtbot.addWidget(view)
    view.resize(1050, 650)
    view.show()
    view.load_job_dir(job)
    qtbot.waitUntil(lambda: view._preview_ready, timeout=15000)
    assert view._tables.currentText() == "source.synthetic · stream.synthetic"
    assert view._columns.topLevelItem(0).text(1) == "ns"
    assert view._preview.item(0, 0).text() == "9007199254740993"
    assert "warnings" in view._warning.text()
    view._set_checks(Qt.CheckState.Unchecked)
    time = view._columns.topLevelItem(0)
    value = view._columns.topLevelItem(2)
    time.setCheckState(0, Qt.CheckState.Checked)
    value.setCheckState(0, Qt.CheckState.Checked)
    view._columns.setCurrentItem(value)
    QTest.mouseClick(view._up, Qt.MouseButton.LeftButton)
    QTest.mouseClick(view._up, Qt.MouseButton.LeftButton)
    assert view.selected_columns() == ("value", "t_ns")
    view._parent_path.setText(str(tmp_path))
    view._folder_name.setText("selected-columns")
    QTest.mouseClick(view._export, Qt.MouseButton.LeftButton)
    output = tmp_path / "selected-columns"
    qtbot.waitUntil(lambda: (output / "manifest.json").is_file() and not view.busy, timeout=15000)
    samples.assert_values(
        parquet.read_table(output / "table.parquet"), table.select(["value", "t_ns"])
    )
    samples.assert_values(samples.read_csv(output), table.select(["value", "t_ns"]))
    manifest = json.loads((output / "source/job_manifest.json").read_text())
    assert manifest["warnings"] == ["synthetic provisional values"]
    assert samples.inventory(job.parents[2]) == before
    assert "Exported 8 rows and 2 columns" in view._status.text()
    assert view._open.isEnabled()
    view.close()


def test_clearing_during_preview_cannot_reopen_the_old_result(qtbot, tmp_path):
    job, _ = samples.make_job(tmp_path)
    view = FeatureTableView()
    qtbot.addWidget(view)
    view.load_job_dir(job)
    view.clear()
    qtbot.waitUntil(lambda: not view._tasks, timeout=15000)
    assert view._tables.count() == 0
    assert view._columns.topLevelItemCount() == 0
    assert view._preview.rowCount() == 0
    assert not view._export.isEnabled()
    view.close()
