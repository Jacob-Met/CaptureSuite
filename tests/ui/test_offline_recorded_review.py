# SPDX-License-Identifier: GPL-3.0-only
"""Recorded-review ownership and capture guards on the real desktop widgets.

The directory chooser is a controlled input in these focused regressions.
Separate native receiving exercises the actual menu, modal chooser and exporter.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
import shiboken6
from capture_desktop.app import MainWindow
from capture_protocol.generated.capture.v1 import control_pb2
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QFileDialog


@pytest.fixture
def desktop(qapp):
    window = MainWindow(auto_connect=False)
    window.show()
    qapp.processEvents()
    yield window
    for viewer in list(getattr(window, "_recorded_review_windows", {}).values()):
        if shiboken6.isValid(viewer):
            viewer.close()
    window.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def _package(tmp_path: Path, name: str, state: str = "finalized") -> Path:
    package = tmp_path / f"{name}.mmsession"
    package.mkdir()
    (package / "manifest.json").write_text(
        json.dumps({"sessionId": name, "state": state}) + "\n", encoding="utf-8"
    )
    return package


def _trigger(window: MainWindow) -> None:
    # Retain the native menu wrappers throughout signal delivery.
    bar = window.menuBar()
    top_actions = bar.actions()
    menus = [action.menu() for action in top_actions]
    actions = [
        action
        for menu in menus
        if menu is not None
        for action in menu.actions()
        if action.text() == "Review recorded package…"
    ]
    assert len(actions) == 1, "File must offer recorded-package review without a daemon"
    actions[0].trigger()


def _choose(window: MainWindow, monkeypatch, value: str) -> None:
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: value)
    _trigger(window)


def test_cancel_keeps_capture_state_and_viewers(desktop, monkeypatch):
    before = deepcopy(desktop.state)
    _choose(desktop, monkeypatch, "")
    assert desktop.state == before
    assert not desktop._recorded_review_windows


@pytest.mark.parametrize("state", ["finalized", "finalized_recovered"])
def test_finalized_view_has_private_identity(desktop, qapp, monkeypatch, tmp_path, state):
    package = _package(tmp_path, "recorded-alpha", state)
    raw_before = (package / "manifest.json").read_bytes()
    desktop.state.session_id = "live-capture"
    desktop.state.package_path = "live-package"
    desktop.state.selected_ids = {"live-source"}
    before = deepcopy(desktop.state)
    _choose(desktop, monkeypatch, str(package))
    qapp.processEvents()
    assert desktop.state == before
    assert len(desktop._recorded_review_windows) == 1
    viewer = next(iter(desktop._recorded_review_windows.values()))
    assert viewer.isVisible() and not viewer.isModal()
    assert viewer.state is not desktop.state
    assert viewer.state.session_id == "recorded-alpha"
    assert Path(viewer.state.package_path) == package.resolve()
    assert viewer.state.review_mode and not viewer.state.connected
    assert viewer.review._card_session.text().startswith("recorded-alpha\n")
    assert viewer.review._recovered_banner.isVisible() == (state == "finalized_recovered")
    assert (package / "manifest.json").read_bytes() == raw_before


@pytest.mark.parametrize("kind", ["missing", "bad-json", "recording", "unspecified"])
def test_bad_package_refuses_before_viewer(desktop, monkeypatch, tmp_path, kind):
    package = tmp_path / "invalid.mmsession"
    if kind != "missing":
        package.mkdir()
        body = "{" if kind == "bad-json" else json.dumps(
            {"sessionId": "bad", "state": "" if kind == "unspecified" else kind}
        )
        (package / "manifest.json").write_text(body, encoding="utf-8")
    before = deepcopy(desktop.state)
    _choose(desktop, monkeypatch, str(package))
    assert not desktop._recorded_review_windows
    assert desktop.state.status_line.startswith("Could not open recorded package:")
    before.status_line = desktop.state.status_line
    assert desktop.state == before


@pytest.mark.parametrize(
    ("phase", "rehearsal"),
    [
        (control_pb2.SESSION_STATE_RECORDING, False),
        (control_pb2.SESSION_STATE_ARMING, False),
        (control_pb2.SESSION_STATE_STOPPING, False),
        (control_pb2.SESSION_STATE_IDLE, True),
    ],
)
def test_capture_phase_blocks_open_and_export(desktop, monkeypatch, phase, rehearsal):
    desktop.state.session_state = phase
    desktop.state.rehearsal_active = rehearsal
    before = deepcopy(desktop.state)
    picked = []
    exported = []
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: picked.append(a))
    monkeypatch.setattr(desktop, "_on_review_export", exported.append)
    _trigger(desktop)
    desktop._export_recorded_package("must-not-export")
    assert not picked and not exported and not desktop._recorded_review_windows
    before.status_line = desktop.state.status_line
    assert desktop.state == before
    assert "Finish recording or rehearsal" in desktop.state.status_line


def test_capture_transition_while_chooser_open_is_rechecked(desktop, monkeypatch, tmp_path):
    package = _package(tmp_path, "recorded")
    def choose(*args, **kwargs):
        desktop.state.session_state = control_pb2.SESSION_STATE_ARMING
        return str(package)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose)
    _trigger(desktop)
    assert not desktop._recorded_review_windows
    assert desktop.state.session_state == control_pb2.SESSION_STATE_ARMING
    assert "Finish recording or rehearsal" in desktop.state.status_line


def test_two_viewers_export_their_own_package_and_close_independently(
    desktop, qapp, monkeypatch, tmp_path
):
    alpha = _package(tmp_path, "alpha")
    beta = _package(tmp_path, "beta")
    before = deepcopy(desktop.state)
    _choose(desktop, monkeypatch, str(alpha))
    _choose(desktop, monkeypatch, str(beta))
    first, second = desktop._recorded_review_windows.values()
    assert first.state is not second.state
    received = []
    monkeypatch.setattr(desktop, "_on_review_export", received.append)
    first.review._btn_export.click()
    second.review._btn_export.click()
    assert received == [str(alpha.resolve()), str(beta.resolve())]
    assert desktop.state == before
    first.close()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    assert not shiboken6.isValid(first)
    assert shiboken6.isValid(second) and second.isVisible()
    assert second.review._card_session.text().startswith("beta\n")
    assert list(desktop._recorded_review_windows.values()) == [second]
