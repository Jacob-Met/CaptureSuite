# SPDX-License-Identifier: GPL-3.0-only
"""Anatomical / spatial mapping editor (Analysis Mappings panel)."""

from __future__ import annotations

import json
import uuid

from capture_session.registry import PRESET_TYPES
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .persistence import DesktopPersistence


class AnatomicalMappingPanel(QWidget):
    """Save anatomical_mapping / spatial_layout presets used by EMG/IMU/radar cards."""

    def __init__(
        self,
        persistence: DesktopPersistence | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._persistence = persistence
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        box = QGroupBox("Mappings")
        form = QFormLayout(box)
        self._ptype = QComboBox()
        for ptype in ("anatomical_mapping", "spatial_layout"):
            assert ptype in PRESET_TYPES
            self._ptype.addItem(ptype.replace("_", " "), ptype)
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. upper_limb_emg_v1")
        self._body = QTextEdit()
        self._body.setFont(theme.mono(9))
        self._body.setPlaceholderText(
            '{\n  "channels": {"ch0": "biceps_L", "ch1": "triceps_L"},\n'
            '  "segments": {"pelvis": "landmark_23"}\n}'
        )
        self._body.setMaximumHeight(120)
        form.addRow("Type", self._ptype)
        form.addRow("Name", self._name)
        form.addRow("JSON", self._body)
        row = QHBoxLayout()
        save = QPushButton("Save mapping preset")
        save.clicked.connect(self._save)
        row.addWidget(save)
        row.addStretch(1)
        form.addRow(row)
        root.addWidget(box)
        note = QLabel(
            "Presets feed Focus card muscle/segment labels. Sessions snapshot mappings at record."
        )
        note.setObjectName("Dim")
        note.setWordWrap(True)
        note.setFont(theme.ui(8))
        root.addWidget(note)

    def _save(self) -> None:
        if self._persistence is None:
            QMessageBox.warning(self, "Mappings", "Registry not available.")
            return
        if self._persistence.registry_open.read_only:
            QMessageBox.warning(self, "Mappings", "Registry is read-only.")
            return
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Mappings", "Enter a preset name.")
            return
        try:
            content = json.loads(self._body.toPlainText() or "{}")
        except json.JSONDecodeError as exc:
            QMessageBox.warning(self, "Mappings", f"Invalid JSON: {exc}")
            return
        if not isinstance(content, dict):
            QMessageBox.warning(self, "Mappings", "Mapping JSON must be an object.")
            return
        ptype = str(self._ptype.currentData())
        try:
            self._persistence.registry.put_preset(
                preset_id=f"{ptype}-{uuid.uuid4().hex[:12]}",
                preset_type=ptype,
                name=name,
                schema_version="1",
                content_json=json.dumps(content),
                description="Saved from Analysis mappings panel",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Mappings", str(exc))
            return
        QMessageBox.information(self, "Mappings", f"Saved {ptype} preset “{name}”.")
        self._name.clear()


class MappingPresetAccess(QWidget):
    """Keep future-capture preset editing separate from the current analysis job."""

    def __init__(
        self,
        persistence: DesktopPersistence | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._persistence = persistence
        self._dialog: QDialog | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._open = QPushButton("Mapping presets…")
        self._open.setToolTip("Edit anatomical and spatial presets for future captures")
        self._open.clicked.connect(self._show_presets)
        root.addWidget(self._open)

    def _show_presets(self) -> None:
        # Retain an unfinished draft when closing and reopening the editor.
        if self._dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Mapping presets for future captures")
            dialog.resize(560, 460)
            layout = QVBoxLayout(dialog)
            scope = QLabel(
                "These presets label muscles, segments and spatial layouts in Focus. "
                "A recording keeps the mappings captured when it started; editing a preset "
                "does not change this recording or its analysis results."
            )
            scope.setWordWrap(True)
            layout.addWidget(scope)
            panel = AnatomicalMappingPanel(self._persistence, dialog)
            layout.addWidget(panel)
            if self._persistence is None or self._persistence.registry_open.read_only:
                panel.setEnabled(False)
                unavailable = QLabel(
                    "The preset registry is unavailable in this session."
                    if self._persistence is None
                    else "The preset registry is read-only in this session."
                )
                unavailable.setWordWrap(True)
                layout.addWidget(unavailable)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            self._dialog = dialog
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()
