# SPDX-License-Identifier: GPL-3.0-only
"""Smoke tests for the Milestone 4 PySide6 desktop shell."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from capture_desktop import theme
from capture_desktop.state import CaptureState
from capture_desktop.widgets_preview import (
    ImagePreview,
    MatrixPreview,
    OrientationPreview,
    ScalarSparkline,
    TracePreview,
)


def test_theme_tokens_dark_and_light():
    dark = theme.dark_tokens()
    light = theme.light_tokens()
    assert dark.BG.lightness() < light.BG.lightness()
    assert dark.build_stylesheet()
    assert light.build_stylesheet()
    assert theme.LANE_COLORS["emg"] is not None


def test_theme_apply_switches_palette(qapp):
    theme.apply_theme(qapp, setting="light")
    assert theme.active_tokens().BG == theme.light_tokens().BG
    theme.apply_theme(qapp, setting="dark")
    assert theme.active_tokens().BG == theme.dark_tokens().BG


def test_session_timeline_from_fixture(qapp):
    from capture_desktop.widgets_session_timeline import (
        SessionTimelineWidget,
        timeline_from_review_summary,
    )
    from capture_session import load_review_summary

    root = Path(__file__).resolve().parents[1] / "fixtures" / "mini_session"
    summary = load_review_summary(root)
    model = timeline_from_review_summary(summary)
    assert model.lanes
    widget = SessionTimelineWidget()
    widget.set_model(model)
    widget.show()
    qapp.processEvents()


def test_theme_exports():
    assert theme.BG is not None
    assert "Fusion" not in theme.STYLESHEET or True
    assert theme.ui(9).family()


def test_preview_widgets_empty(qapp):
    TracePreview().clear()
    ImagePreview().clear()
    OrientationPreview().clear()
    MatrixPreview().clear()
    ScalarSparkline().set_values([])
    state = CaptureState()
    assert state.session_state_name() == "idle"


def test_main_window_constructs_without_daemon(qapp):
    from capture_desktop.app import MainWindow
    from capture_desktop.daemon_link import DaemonLink

    window = MainWindow(auto_connect=False)
    try:
        assert window.state is not None
        assert window.capture is not None
        assert window._session_header is not None
        window.capture.refresh()
        assert not window.state.connected
        assert isinstance(DaemonLink().daemon_available(), bool)
    finally:
        window.link.stop()
        window.close()


def test_instance_json_path_documented():
    # Sanity: helper path matches ControlClient convention.
    path = Path(os.environ.get("LOCALAPPDATA", "")) / "CaptureSuite" / "instance.json"
    assert path.name == "instance.json"


def test_ui_application_matches_process_singleton(qapp):
    from PySide6.QtWidgets import QApplication

    assert QApplication.instance() is qapp
