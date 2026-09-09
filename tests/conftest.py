# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for path in (
    REPO / "libs" / "python" / "capture_protocol",
    REPO / "libs" / "python" / "capture_session",
    REPO / "workers" / "python_host",
    REPO / "desktop",
):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


@pytest.fixture(scope="session", autouse=True)
def isolated_application_state(tmp_path_factory):
    """Never let a test UI or child daemon use the operator's actual saved state."""
    root = tmp_path_factory.mktemp("capture-app-state")
    with pytest.MonkeyPatch.context() as patch:
        for key, suffix in [
            ("LOCALAPPDATA", "local"),
            ("APPDATA", "roaming"),
            ("XDG_CONFIG_HOME", "config"),
            ("XDG_DATA_HOME", "data"),
            ("XDG_CACHE_HOME", "cache"),
        ]:
            folder = root / suffix
            folder.mkdir()
            patch.setenv(key, str(folder))
        patch.setenv("CAPTURE_TEST_STATE", str(root))
        yield root


@pytest.fixture(scope="session")
def qapp(isolated_application_state):
    """Keep one QApplication alive through all UI modules and delete widgets first."""
    pytest.importorskip("PySide6")
    from capture_desktop import theme
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app, setting="dark")
    yield app
    for widget in app.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
