# SPDX-License-Identifier: GPL-3.0-only
"""Analysis workbench smoke — in-app gallery without os.startfile for plots."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"


def test_analysis_screen_no_plot_startfile(qapp):
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState

    screen = AnalysisScreen(CaptureState())
    assert screen._gallery is not None
    assert screen._inspector is not None
    assert not hasattr(screen, "_open_dashboard")
    # Phase 6 commands present with dependency extras panel.
    labels = [screen._command.itemText(i) for i in range(screen._command.count())]
    assert any("ML bundle" in t for t in labels)
    assert any("Pose" in t for t in labels)
    assert screen._extras is not None
    screen._command.setCurrentIndex(
        next(
            i for i in range(screen._command.count()) if screen._command.itemData(i) == "ml_bundle"
        )
    )
    qapp.processEvents()
    assert screen._command.currentData() == "ml_bundle"
    assert not screen._extras.isHidden()
    screen.show()
    qapp.processEvents()
    assert screen._extras.isVisible()


def test_analysis_job_extras_validate(qapp):
    from capture_desktop.widgets_analysis_jobs import AnalysisJobExtras

    extras = AnalysisJobExtras()
    assert extras.validate_for("kinematics") is not None
    extras._pose_job.setEditText("pose-1")
    assert extras.validate_for("kinematics") is None
    assert extras.build_extra("kinematics")["pose_job_id"] == "pose-1"
    err = extras.validate_for("ml_bundle")
    assert err is not None
    extras._kin_job.setEditText("kin-1")
    extras._feat_job.setEditText("feat-1")
    assert extras.validate_for("ml_bundle") is None


def test_sync_dashboard_view_loads_series_json(qapp, tmp_path: Path):
    pytest.importorskip("pyqtgraph")
    from capture_desktop.widgets_analysis_plots import SyncDashboardView

    doc = {
        "schemaId": "capture.sync_dashboard_series/1",
        "title": "test session",
        "window": {"startSessionNs": 0, "endSessionNs": 1_000_000_000, "label": "full"},
        "gaps": [],
        "series": [
            {
                "label": "EMG",
                "t_ns": [0, 500_000_000, 1_000_000_000],
                "y": [0.0, 1.0, 0.5],
                "color": "#35c46b",
            }
        ],
    }
    path = tmp_path / "sync_dashboard_series.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    view = SyncDashboardView()
    assert view.load_json_path(path)
    view.show()
    qapp.processEvents()


def test_job_writes_sync_series_json(tmp_path: Path) -> None:
    pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    pytest.importorskip("matplotlib")
    pytest.importorskip("mcap")

    from capture_analysis import JobParams, run

    from tests.analysis.test_phase_b_features import _write_emg_imu_package

    package = _write_emg_imu_package(tmp_path / "synth.mmsession")
    result = run(package, JobParams(command="all", overwrite_job_id="wb-sync-json"))
    series = result.job_dir / "figures" / "sync_dashboard_series.json"
    assert series.is_file(), "pipeline must emit sync series JSON for in-app viewer"
    doc = json.loads(series.read_text(encoding="utf-8"))
    assert doc.get("schemaId") == "capture.sync_dashboard_series/1"
    assert doc.get("series")
