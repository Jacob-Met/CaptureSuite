# SPDX-License-Identifier: GPL-3.0-only
"""The maintained Analysis screen without Windows capture-transport imports."""

from __future__ import annotations

import sys

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QVBoxLayout, QWidget

from . import theme
from .persistence import DesktopPersistence
from .screen_analysis import AnalysisScreen
from .state import CaptureState
from .widgets_session_header import SessionHeader

OFFLINE_COMMANDS = ("qc", "all", "features", "plots")


class OfflineWindow(QMainWindow):
    """Use the same session scope, analysis workers and saved-result views as capture."""

    def __init__(self, package: str = "") -> None:
        super().__init__()
        self.setWindowTitle("CaptureSuite — Offline analysis")
        self.setMinimumSize(1100, 700)
        self.resize(1440, 900)
        self.persistence = DesktopPersistence()
        self.state = CaptureState()
        root = QWidget()
        root.setObjectName("Root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._session_header = SessionHeader()
        layout.addWidget(self._session_header)
        self.analysis = AnalysisScreen(
            self.state,
            self.persistence,
            commands=OFFLINE_COMMANDS,
        )
        layout.addWidget(self.analysis, 1)
        self.setCentralWidget(root)
        self.analysis.package_loaded.connect(self._package_loaded)
        self._session_header.scope_changed.connect(self.analysis.set_scope)

        file_menu = self.menuBar().addMenu("&File")
        open_session = file_menu.addAction("Open recorded session…")
        open_session.setShortcut(QKeySequence.StandardKey.Open)
        open_session.triggered.connect(self.analysis._browse)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("Quit")
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        if package:
            self.analysis.set_package(package)

    def _package_loaded(self, summary) -> None:
        if summary is None:
            self._session_header.clear()
        else:
            self._session_header.refresh_sealed(summary, selection=self.analysis.scope)

    def closeEvent(self, event) -> None:
        if self.analysis._thread is not None:
            QMessageBox.information(
                self,
                "Analysis is running",
                "Wait for analysis to finish, or use Cancel before closing.",
            )
            event.ignore()
            return
        self.persistence.close()
        super().closeEvent(event)


def run_offline(package: str = "") -> int:
    from capture_session.settings_store import SettingsStore

    app = QApplication.instance() or QApplication(sys.argv)
    settings = SettingsStore()
    settings.load()
    theme.apply_theme(app, setting=str(settings.get("theme") or "system"))
    window = OfflineWindow(package)
    window.show()
    return app.exec()
