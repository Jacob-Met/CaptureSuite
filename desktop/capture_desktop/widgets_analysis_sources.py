# SPDX-License-Identifier: GPL-3.0-only
"""Choose the exact recorded source IDs consumed by offline analysis jobs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from capture_session.package_reader import ReviewSummary

SOURCE_COMMANDS = frozenset({"all", "features", "plots", "pose"})


class AnalysisSourcePicker(QWidget):
    """Package-bound selection; an empty explicit subset never means all sources."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._package = ""
        self._available: tuple[str, ...] = ()
        self._selected: tuple[str, ...] = ()
        self._inventory_error: str | None = None
        self._command = "qc"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        row = QHBoxLayout()
        row.addWidget(QLabel("Sources"))
        self._mode = QComboBox()
        self._mode.setAccessibleName("Analysis source mode")
        self._mode.addItem("All recorded sources", "all")
        self._mode.addItem("Selected sources", "selected")
        row.addWidget(self._mode, 1)
        self._choose = QPushButton("Choose…")
        self._choose.setAccessibleName("Choose recorded sources")
        self._choose.clicked.connect(self._choose_sources)
        row.addWidget(self._choose)
        root.addLayout(row)

        self._summary = QLineEdit()
        self._summary.setReadOnly(True)
        self._summary.setFrame(False)
        self._summary.setAccessibleName("Analysis source selection")
        root.addWidget(self._summary)
        self._note = QLabel()
        self._note.setTextFormat(Qt.TextFormat.PlainText)
        self._note.setWordWrap(True)
        self._note.setObjectName("Dim")
        root.addWidget(self._note)
        self._mode.currentIndexChanged.connect(self._mode_changed)
        self.setEnabled(False)
        self._present()

    @property
    def mode(self) -> str:
        return str(self._mode.currentData())

    @property
    def selected_ids(self) -> tuple[str, ...]:
        """Remember an explicit choice even while All recorded sources is active."""
        return self._selected

    def load_package(self, summary: ReviewSummary | None) -> None:
        package = str(Path(summary.package_path).resolve()) if summary is not None else ""
        if package != self._package:
            self._package = package
            self._selected = ()
            with QSignalBlocker(self._mode):
                self._mode.setCurrentIndex(self._mode.findData("all"))
        self.setEnabled(bool(package))
        self.refresh_inventory()

    def refresh_inventory(self) -> None:
        """Refresh on package/chooser/launch events, never on the display timer."""
        self._inventory_error = None
        self._available = ()
        if self._package:
            try:
                from capture_analysis.discover import discover_streams

                self._available = tuple(sorted({
                    ref.source_id for ref in discover_streams(self._package)
                }))
            except (ImportError, OSError, TypeError, ValueError) as exc:
                self._inventory_error = (
                    f"Could not read recorded sources: {exc}. "
                    "Reopen the package after correcting the problem, "
                    "or select All recorded sources."
                )
        # Keep vanished selections visible and invalid instead of widening the job.
        self._present()
        self.changed.emit()

    def set_command(self, command: str) -> None:
        self._command = command
        self._present()

    def error_for(self, command: str) -> str | None:
        if self.mode == "all":
            return None
        if command not in SOURCE_COMMANDS:
            return (
                "This command uses the full package or its input jobs. "
                "Select All recorded sources to run."
            )
        if self._inventory_error:
            return self._inventory_error
        if not self._selected:
            return "Choose at least one source, or select All recorded sources."
        missing = [source for source in self._selected if source not in self._available]
        if missing:
            return (
                f"Selected source IDs are no longer recorded: {', '.join(missing)}. "
                "Choose sources again, or select All recorded sources."
            )
        return None

    def snapshot(self, command: str) -> tuple[str, ...]:
        error = self.error_for(command)
        if error:
            raise ValueError(error)
        return self._selected if self.mode == "selected" else ()

    def _mode_changed(self) -> None:
        self._present()
        self.changed.emit()

    def _present(self) -> None:
        self._choose.setEnabled(bool(self._package) and self.mode == "selected")
        if self.mode == "selected":
            text = ", ".join(source or "(empty source ID)" for source in self._selected)
            self._summary.setText(text or "No sources selected")
            self._summary.setToolTip("\n".join(self._selected))
        else:
            text = (
                "Recorded source inventory unavailable"
                if self._inventory_error
                else f"All {len(self._available)} recorded source IDs"
            )
            self._summary.setText(text)
            self._summary.setToolTip("\n".join(self._available))
        note = self.error_for(self._command) or self._inventory_error or ""
        self._note.setText(note)
        self._note.setVisible(bool(note))

    def _choose_sources(self) -> None:
        self.refresh_inventory()
        package = self._package
        dialog = QDialog(self)
        dialog.setWindowTitle("Choose recorded sources")
        dialog.resize(480, 360)
        root = QVBoxLayout(dialog)
        explanation = QLabel(
            self._inventory_error
            or "Check the source IDs to include. Every recorded stream belonging "
            "to a checked source is included. QC still covers the full package."
        )
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        root.addWidget(explanation)
        rows = QListWidget()
        rows.setAccessibleName("Recorded source IDs")
        for source in sorted(set(self._available) | set(self._selected)):
            label = source or "(empty source ID)"
            if source not in self._available:
                label += " (no longer recorded)"
            item = QListWidgetItem(label, rows)
            item.setData(Qt.ItemDataRole.UserRole, source)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if source in self._selected else Qt.CheckState.Unchecked
            )
        root.addWidget(rows, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Use selection")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        root.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted and package == self._package:
            self._selected = tuple(sorted(
                rows.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(rows.count())
                if rows.item(i).checkState() == Qt.CheckState.Checked
            ))
            self.refresh_inventory()
        dialog.deleteLater()
