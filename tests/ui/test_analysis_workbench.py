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


def test_qc_payload_inspection_is_opt_in_and_qc_only(qapp):
    from capture_desktop.widgets_analysis_jobs import AnalysisJobExtras

    extras = AnalysisJobExtras()
    extras.show()
    extras.set_command("qc")
    qapp.processEvents()
    assert extras._payload_box.isVisible()
    assert not extras._box.isVisible()
    assert extras._inspect_payloads.isEnabled()
    assert extras.build_extra("qc") == {}

    extras._inspect_payloads.setChecked(True)
    assert extras.build_extra("qc") == {"inspect_payloads": True}
    extras.set_eval_busy(True)
    assert not extras._inspect_payloads.isEnabled()
    extras.set_eval_busy(False)
    assert extras._inspect_payloads.isEnabled()

    extras.set_command("all")
    qapp.processEvents()
    assert not extras._payload_box.isVisible()
    assert extras.build_extra("all") == {}
    extras.set_command("qc")
    qapp.processEvents()
    assert extras._payload_box.isVisible()
    assert extras.build_extra("qc") == {"inspect_payloads": True}


def test_qc_payload_inspection_reaches_native_job_params(qapp, tmp_path: Path, monkeypatch):
    import capture_analysis
    from capture_desktop.screen_analysis import _AnalysisWorker

    observed = []
    result = object()

    def run_job(package, params, *, progress, cancel):
        observed.append((package, params.command, params.extra))
        return result

    monkeypatch.setattr(capture_analysis, "run", run_job)
    for opt_in, expected in (
        (False, {}),
        (True, {"inspect_payloads": True}),
    ):
        worker = _AnalysisWorker(
            str(tmp_path), "qc", "mask",
            {"inspect_payloads": True} if opt_in else {},
        )
        finished = []
        failed = []
        worker.finished.connect(finished.append)
        worker.failed.connect(failed.append)
        worker.run()
        assert not failed
        assert finished == [result]
        assert observed[-1] == (str(tmp_path), "qc", expected)


def test_qc_payload_toggle_runs_real_analysis_screen(qapp, tmp_path: Path, monkeypatch):
    pytest.importorskip("mcap")
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QMessageBox

    from tests.analysis.test_payload_inspection_qc import SEGMENT, _package, _write_mcap

    def refuse_modal_warning(parent, title, message):
        raise AssertionError(f"Unexpected modal dialog {title}: {message}")

    monkeypatch.setattr(QMessageBox, "warning", refuse_modal_warning)
    package = _package(tmp_path)
    _write_mcap(package, values=[1.0, 2.0, 3.0, 4.0], times=[100, 101])
    raw_before = (package / SEGMENT).read_bytes()

    screen = AnalysisScreen(CaptureState())
    screen.resize(1180, 740)
    screen.show()
    screen.set_package(str(package))
    qapp.processEvents()
    assert screen._summary is not None
    assert screen._btn_run.isEnabled()
    assert screen._extras.build_extra("qc") == {}

    screen._extras._inspect_payloads.setChecked(True)
    screen._btn_run.click()
    assert screen._thread is not None

    for _ in range(600):
        qapp.processEvents()
        if screen._thread is None:
            break
        QTest.qWait(25)

    assert screen._thread is None, screen._log.toPlainText()
    assert "Done status=completed" in screen._log.toPlainText()
    assert "inspect_payloads" in screen._log.toPlainText()

    report_path = Path(screen._last_job_dir) / "reports/qc.json"
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["streams"][0]["payloadInspection"]["status"] == "numeric_samples_checked"
    assert report["streams"][0]["payloadInspection"]["sampleFramesChecked"] == 2
    assert (package / SEGMENT).read_bytes() == raw_before
    assert screen._btn_open_report.isEnabled()
    image_path = tmp_path / "analysis-qc-operator.png"
    assert screen.grab().save(str(image_path))
    assert image_path.stat().st_size > 4_096
    screen.close()


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
    assert doc.get("schemaId") == "capture.sync_dashboard_series/2"
    assert doc.get("series")
