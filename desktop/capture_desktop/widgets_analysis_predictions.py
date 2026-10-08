# SPDX-License-Identifier: GPL-3.0-only
"""Explicit evaluation input for the offline Analysis workbench."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme


class EvaluationInput(QGroupBox):
    """Choose a path; the existing evaluator admits its bytes when the job runs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Evaluation input", parent)
        self.setObjectName("EvaluationInput")
        self._package = ""
        self._command = "eval"
        self._revision = 0
        self._busy = False
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self._mode = QComboBox()
        self._mode.setObjectName("EvalInputMode")
        self._mode.setAccessibleName("Evaluation input mode")
        self._mode.addItem("Identity teacher (simulation)", "identity")
        self._mode.addItem("External predictions file", "external")
        root.addWidget(self._mode)

        self._file_row = QWidget()
        file_layout = QHBoxLayout(self._file_row)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(6)
        self._path = QLineEdit()
        self._path.setObjectName("EvalPredictionPath")
        self._path.setAccessibleName("Predictions JSON file")
        self._path.setReadOnly(True)
        self._path.setMinimumWidth(0)
        self._path.setPlaceholderText("No predictions file chosen")
        self._choose_button = QPushButton("Choose…")
        self._choose_button.setObjectName("EvalPredictionChoose")
        self._choose_button.setAccessibleName("Choose predictions JSON file")
        self._choose_button.clicked.connect(self._choose)
        self._clear_button = QPushButton("Clear")
        self._clear_button.setObjectName("EvalPredictionClear")
        self._clear_button.setAccessibleName("Clear predictions file choice")
        self._clear_button.clicked.connect(self._clear)
        file_layout.addWidget(self._path, 1)
        file_layout.addWidget(self._choose_button)
        file_layout.addWidget(self._clear_button)
        root.addWidget(self._file_row)

        self._help = QLabel()
        self._help.setObjectName("Dim")
        self._help.setWordWrap(True)
        self._help.setTextFormat(Qt.TextFormat.PlainText)
        self._help.setFont(theme.ui(8))
        root.addWidget(self._help)
        self._mode.currentIndexChanged.connect(self._mode_changed)
        self._refresh()

    def _mode_changed(self) -> None:
        self._revision += 1
        self._refresh()

    def _refresh(self) -> None:
        external = self._mode.currentData() == "external"
        self._file_row.setVisible(external)
        self._clear_button.setEnabled(bool(self._path.text()))
        self._path.setToolTip(self._path.text())
        self._help.setText(
            "Compares supplied predictions with the selected ML bundle. "
            "Source and window identities are checked before scoring."
            if external
            else "Fixture simulation: compares each teacher value with itself."
        )

    def set_package(self, package: str) -> None:
        identity = str(Path(package).resolve()) if package else ""
        if identity != self._package:
            self._package = identity
            self._revision += 1
            self._path.clear()
            self._refresh()

    def set_command(self, command: str) -> None:
        if command != self._command:
            self._command = command
            self._revision += 1
        self.setVisible(command == "eval")

    def set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self._revision += 1
        self.setEnabled(not busy)

    def _choose(self) -> None:
        if not self.isEnabled() or self._command != "eval":
            return
        if self._mode.currentData() != "external":
            return
        self._revision += 1
        revision = self._revision
        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choose external predictions JSON",
            self._path.text() or self._package,
            "Prediction JSON (*.json);;All files (*)",
        )
        if revision != self._revision or not self.isEnabled() or not filename:
            return
        # Preserve the exact native choice, including significant whitespace.
        self._path.setText(filename)
        self._refresh()

    def _clear(self) -> None:
        self._revision += 1
        self._path.clear()
        self._refresh()
        self._choose_button.setFocus()

    def extra(self) -> dict[str, str]:
        if self._mode.currentData() != "external":
            return {}
        # An empty external path remains explicit even if a caller skips validation.
        return {"prediction_path": self._path.text()}

    def validate(self) -> str | None:
        if self._mode.currentData() != "external":
            return None
        filename = self._path.text()
        if not filename:
            return "Choose a predictions JSON file for external evaluation."
        try:
            if Path(filename).is_file():
                return None
        except (OSError, ValueError):
            pass
        return "The predictions file is unavailable. Choose an existing JSON file and run again."
