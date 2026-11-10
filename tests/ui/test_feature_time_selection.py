# SPDX-License-Identifier: GPL-3.0-only
"""Operator time controls preserve exact retained data and interval semantics."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pyarrow.parquet as pq
from capture_analysis.feature_table_export import export_feature_table
from capture_desktop.widgets_feature_time import FeatureTimeSelection

from tests.analysis.test_feature_table_export import TABLE, make_job


def test_trial_seconds_reach_exact_retained_export(qapp, tmp_path):
    picker = FeatureTimeSelection()
    picker.set_columns([{"name": "t_ns", "units": "ns"}, {"name": "value", "units": "V"}])
    picker._mode.setCurrentIndex(picker._mode.findData("time"))
    assert picker.selection is None
    picker._start.setText("9007199.254740993")
    picker._end.setText("9007199.254740995")
    assert picker.selection == {
        "time_column": "t_ns", "start_ns": 9007199254740993, "end_ns": 9007199254740995,
    }
    assert "unchanged" in picker._message.text()
    job, _ = make_job(tmp_path)
    output = tmp_path / "trial"
    result = export_feature_table(job, TABLE, output, **picker.selection)
    assert result["selection"]["rows"] == 1
    assert pq.read_table(output / "table.parquet")["t_ns"].to_pylist() == [9007199254740993]
    picker.close()


def test_invalid_trial_and_table_change_cannot_reuse_old_bounds(qapp):
    picker = FeatureTimeSelection()
    picker.set_columns([{"name": "t_mid_ns", "units": "ns"}])
    picker._mode.setCurrentIndex(picker._mode.findData("time"))
    for start, end in [("", "2"), ("2", "2"), ("3", "2"), ("nan", "2"),
                       ("0.0000000001", "2")]:
        picker._start.setText(start)
        picker._end.setText(end)
        assert picker.selection is None
    picker._start.setText("-1.000000001")
    picker._end.setText("0")
    assert picker.selection["start_ns"] == -1000000001
    picker.set_columns([{"name": "t_start_ns", "units": "ns"}])
    assert picker.selection == {}
    picker._mode.setCurrentIndex(picker._mode.findData("time"))
    assert picker.selection is None
    assert not picker._start.text()
    assert not picker._end.text()
    picker.close()


def test_all_rows_and_missing_time_column_remain_explicit(qapp):
    picker = FeatureTimeSelection()
    picker.set_columns([{"name": "amplitude", "units": "mV"}])
    assert picker.selection == {}
    picker._mode.setCurrentIndex(picker._mode.findData("time"))
    assert picker.selection is None
    assert "no retained nanosecond column" in picker._message.text()
    picker._mode.setCurrentIndex(0)
    assert picker.selection == {}
    picker.close()
