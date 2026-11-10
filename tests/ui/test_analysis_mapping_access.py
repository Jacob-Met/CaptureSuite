# SPDX-License-Identifier: GPL-3.0-only
"""Future-capture presets do not occupy or alter the offline job workspace."""
from __future__ import annotations

import json
from types import SimpleNamespace

from capture_desktop.widgets_mappings import AnatomicalMappingPanel, MappingPresetAccess
from capture_session.registry import AppRegistry
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton


def test_mapping_draft_reopens_and_saves_to_existing_registry(qapp, tmp_path, monkeypatch):
    reg = AppRegistry(tmp_path / "registry.sqlite")
    opened = reg.open()
    persistence = SimpleNamespace(registry=reg, registry_open=opened)
    access = MappingPresetAccess(persistence)
    access.show()
    QTest.mouseClick(access._open, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    dialog = access._dialog
    panel = dialog.findChild(AnatomicalMappingPanel)
    panel._name.setText("Left-arm recording")
    body = '{"channels":{"ch0":"biceps_L"}}'
    panel._body.setPlainText(body)
    dialog.reject()
    access._open.setFocus()
    QTest.keyClick(access._open, Qt.Key.Key_Space)
    qapp.processEvents()
    assert access._dialog is dialog and dialog.isVisible()
    assert panel._name.text() == "Left-arm recording"
    assert panel._body.toPlainText() == body
    assert "does not change this recording" in " ".join(
        label.text() for label in dialog.findChildren(QLabel)
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    save = next(b for b in panel.findChildren(QPushButton) if b.text() == "Save mapping preset")
    QTest.mouseClick(save, Qt.MouseButton.LeftButton)
    presets = reg.list_presets("anatomical_mapping")
    assert len(presets) == 1
    assert json.loads(presets[0]["content_json"]) == json.loads(body)
    assert not panel._name.text()
    dialog.close()
    access.close()
    reg.close()


def test_unavailable_or_readonly_registry_is_explained(qapp):
    for persistence, phrase in (
        (None, "unavailable"),
        (SimpleNamespace(registry_open=SimpleNamespace(read_only=True)), "read-only"),
    ):
        access = MappingPresetAccess(persistence)
        access.show()
        access._open.click()
        qapp.processEvents()
        dialog = access._dialog
        assert not dialog.findChild(AnatomicalMappingPanel).isEnabled()
        assert phrase in " ".join(label.text() for label in dialog.findChildren(QLabel))
        dialog.reject()
        access.close()


def test_analysis_keeps_mapping_editor_out_of_job_setup(qapp):
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState

    screen = AnalysisScreen(CaptureState())
    screen.resize(1280, 800)
    screen.show()
    qapp.processEvents()
    assert isinstance(screen._mappings, MappingPresetAccess)
    assert screen._mappings._dialog is None
    assert not screen.findChildren(AnatomicalMappingPanel)
    assert screen._mappings.height() < 60
    screen.close()
