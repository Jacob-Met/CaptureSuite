# SPDX-License-Identifier: GPL-3.0-only
"""Radar array editor — save software-coordinated multi-radar presets."""

from __future__ import annotations

import json
import uuid

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .persistence import DesktopPersistence
from .state import SourceRow


class RadarArrayEditorDialog(QDialog):
    def __init__(
        self,
        persistence: DesktopPersistence,
        radars: list[SourceRow],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._persistence = persistence
        self._radars = radars
        self.setWindowTitle("Radar array")
        self.setMinimumWidth(480)
        self.setFont(theme.ui(9))

        root = QVBoxLayout(self)
        names = ", ".join(r.alias for r in radars)
        intro = QLabel(
            f"Software-coordinated array ({len(radars)} radars): {names}.\n"
            "Not hardware sync — device-native timestamps only; host arrival may lag."
        )
        intro.setWordWrap(True)
        intro.setObjectName("Dim")
        root.addWidget(intro)

        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. bench_dual_fmcw")
        form.addRow("Preset name", self._name)
        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _save(self) -> None:
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Radar array", "Enter a preset name.")
            return
        content = {
            "coordination": "software",
            "hardware_sync_validated": False,
            "members": [
                {
                    "source_id": r.source_id,
                    "alias": r.alias,
                    "modality": r.modality,
                    "serial": r.serial,
                }
                for r in self._radars
            ],
        }
        try:
            self._persistence.registry.put_preset(
                preset_id=f"radar_array-{uuid.uuid4().hex[:12]}",
                preset_type="radar_array",
                name=name,
                schema_version="1",
                content_json=json.dumps(content),
                description="Software-coordinated radar array (sim/replay or bench)",
                compatibility_json=json.dumps(
                    {"member_count": len(self._radars), "coordination": "software"}
                ),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Radar array", str(exc))
            return
        self.accept()
