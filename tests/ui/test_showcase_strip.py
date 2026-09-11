# SPDX-License-Identifier: GPL-3.0-only
"""Camera + radar presentation shortcuts stay truthful and fail closed."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from capture_desktop import theme
from capture_desktop.screen_capture import (
    CaptureScreen,
    showcase_camera_source,
    showcase_radar_source,
    showcase_status_text,
)
from capture_desktop.state import CaptureState, SourceRow
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app, setting="dark")
    return app


def _source(
    source_id: str,
    alias: str,
    source_type: str,
    modality: str,
    plugin_id: str,
    *,
    selected: bool = True,
    enabled: bool = True,
) -> SourceRow:
    return SourceRow(
        source_id=source_id,
        alias=alias,
        source_type=source_type,
        modality=modality,
        selected=selected,
        enabled=enabled,
        plugin_id=plugin_id,
    )


def _state(*sources: SourceRow) -> CaptureState:
    state = CaptureState()
    state.sources = list(sources)
    state.selected_ids = {src.source_id for src in sources if src.selected}
    return state


def test_showcase_prefers_selected_hardware_over_sim():
    sim_camera = _source(
        "sim.camera.sagittal", "Camera sim", "sim.camera", "video", "sim.camera"
    )
    hw_camera = _source("camera.usb.1", "MX Brio", "camera", "video", "camera.gstreamer")
    sim_radar = _source("sim.radar.1", "Radar sim", "sim.radar", "radar", "sim.radar")
    hw_radar = _source("radar.ifx.a1", "BGT60TR13C", "radar", "radar", "radar.ifx")
    state = _state(sim_camera, hw_camera, sim_radar, hw_radar)

    assert showcase_camera_source(state) is hw_camera
    assert showcase_radar_source(state) is hw_radar
    status = showcase_status_text(state)
    assert "Camera: hardware" in status
    assert "Radar: hardware" in status
    assert "not hardware sync" in status


def test_showcase_shortcuts_camera_radar_shared_live(qapp):
    camera = _source(
        "sim.camera.sagittal", "Camera sim", "sim.camera", "video", "sim.camera"
    )
    radar = _source("sim.radar.1", "Radar sim", "sim.radar", "radar", "sim.radar")
    state = _state(camera, radar)
    state.rehearsal_active = True
    screen = CaptureScreen(state)
    screen.show()
    qapp.processEvents()
    try:
        screen.refresh()
        assert screen._btn_showcase_camera.isEnabled()
        assert screen._btn_showcase_radar.isEnabled()
        assert screen._btn_showcase_shared.isEnabled()
        assert "rehearsal preview only" in screen._showcase_status.text()
        assert "software-coordinated view" in screen._showcase_status.text()

        screen._btn_showcase_camera.click()
        qapp.processEvents()
        assert state.focus_id == camera.source_id
        assert screen.view_mode() == 1

        screen._btn_showcase_radar.click()
        qapp.processEvents()
        assert state.focus_id == radar.source_id
        assert screen.view_mode() == 1

        screen._btn_showcase_shared.click()
        qapp.processEvents()
        assert screen.view_mode() == 2
    finally:
        screen.close()


def test_showcase_shared_live_disabled_without_selected_radar(qapp):
    camera = _source(
        "sim.camera.sagittal", "Camera sim", "sim.camera", "video", "sim.camera"
    )
    radar = _source(
        "sim.radar.1",
        "Radar sim",
        "sim.radar",
        "radar",
        "sim.radar",
        selected=False,
    )
    state = _state(camera, radar)
    screen = CaptureScreen(state)
    screen.show()
    qapp.processEvents()
    try:
        screen.refresh()
        assert showcase_radar_source(state) is None
        assert screen._btn_showcase_camera.isEnabled()
        assert not screen._btn_showcase_radar.isEnabled()
        assert not screen._btn_showcase_shared.isEnabled()
        assert "Radar: not selected" in screen._showcase_status.text()
        assert "not hardware sync" in screen._showcase_status.text()
    finally:
        screen.close()
