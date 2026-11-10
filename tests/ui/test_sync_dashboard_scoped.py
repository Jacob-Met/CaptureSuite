# SPDX-License-Identifier: GPL-3.0-only
"""Actual Qt lanes preserve recorded clocks, absence and scientific identity."""

import pytest

pytest.importorskip("PySide6")
pg = pytest.importorskip("pyqtgraph")
from capture_desktop.widgets_analysis_plots import SyncDashboardView  # noqa: E402
from PySide6.QtWidgets import QLabel  # noqa: E402


def document():
    return {
        "schemaId": "capture.sync_dashboard_series/2",
        "window": {"startSessionNs": 31000000000, "endSessionNs": 36000000000},
        "series": [
            {
                "label": "Delayed forearm / channel one",
                "ylabel": "mV",
                "t_ns": [32000000000, 33000000000, 35000000000, 36000000000],
                "y": [1, 2, 4, 5],
                "gaps": [{"startSessionNs": 33500000000, "endSessionNs": 34500000000}],
            },
            {
                "label": "Healthy force",
                "ylabel": "N",
                "t_ns": [31000000000, 33000000000, 35000000000, 36000000000],
                "y": [10, 20, 30, 40],
                "gaps": [],
            },
        ],
    }


def test_native_lane_clock_gap_and_labels(qapp, qtbot):
    view = SyncDashboardView()
    qtbot.addWidget(view)
    assert view.load_document(document())
    first, second = view._linked
    assert [list(line.getData()[0]) for line in first.listDataItems()] == [[32, 33], [35, 36]]
    assert list(second.listDataItems()[0].getData()[0]) == [31, 33, 35, 36]
    def regions(p):
        return [x for x in p.items() if isinstance(x, pg.LinearRegionItem)]
    assert len(regions(first)) == 1
    assert regions(first)[0].getRegion() == (33.5, 34.5)
    assert regions(second) == []
    assert first.getAxis("left").labelText == "mV"
    assert second.getAxis("left").labelText == "N"
    assert any(x.text() == "Delayed forearm / channel one" for x in view.findChildren(QLabel))
    assert first.viewRange()[0] == [31, 36]
    view.close()


def test_legacy_gap_scope_never_guessed(qapp, qtbot):
    doc = document()
    doc["schemaId"] = "capture.sync_dashboard_series/1"
    doc["gaps"] = doc["series"][0].pop("gaps")
    doc["series"][1].pop("gaps")
    view = SyncDashboardView()
    qtbot.addWidget(view)
    assert view.load_document(doc)
    assert "lane-specific gap evidence" in view._placeholder.text()
    assert all(line.opts["pen"] is None for plot in view._linked for line in plot.listDataItems())
    view.close()


def test_null_break_and_no_samples(qapp, qtbot):
    doc = document()
    doc["series"][0]["y"] = [1, None, 4, 5]
    view = SyncDashboardView()
    qtbot.addWidget(view)
    assert view.load_document(doc)
    assert [list(x.getData()[0]) for x in view._linked[0].listDataItems()] == [[32], [35, 36]]
    assert not view.load_document({"series": [{"t_ns": [], "y": []}]})
    view.close()
