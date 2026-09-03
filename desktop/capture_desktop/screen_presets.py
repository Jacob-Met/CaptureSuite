# SPDX-License-Identifier: GPL-3.0-only
"""Preset library browser — registry.sqlite presets (all ten types)."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from capture_session.registry import PRESET_TYPES

from . import theme
from .persistence import DesktopPersistence


class PresetLibraryDialog(QDialog):
    def __init__(
        self,
        persistence: DesktopPersistence,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._persistence = persistence
        self.setWindowTitle("Preset library")
        self.setMinimumSize(640, 420)
        self.setFont(theme.ui(9))

        root = QVBoxLayout(self)
        intro = QLabel(
            "Lab presets live in registry.sqlite. Sessions store full preset snapshots — "
            "this library is for reuse across setups."
        )
        intro.setWordWrap(True)
        intro.setObjectName("Dim")
        root.addWidget(intro)

        filt = QHBoxLayout()
        filt.addWidget(QLabel("Type"))
        self._type = QComboBox()
        self._type.addItem("All types", "")
        for ptype in sorted(PRESET_TYPES):
            self._type.addItem(ptype.replace("_", " "), ptype)
        self._type.currentIndexChanged.connect(self._reload)
        filt.addWidget(self._type, 1)
        root.addLayout(filt)

        body = QHBoxLayout()
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._show_detail)
        body.addWidget(self._list, 1)
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setFont(theme.mono(9))
        body.addWidget(self._detail, 2)
        root.addLayout(body, 1)

        actions = QHBoxLayout()
        self._btn_delete = QPushButton("Delete")
        self._btn_delete.clicked.connect(self._delete_selected)
        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.clicked.connect(self._reload)
        actions.addWidget(self._btn_delete)
        actions.addWidget(self._btn_refresh)
        actions.addStretch(1)
        root.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if persistence.registry_open.read_only:
            self._btn_delete.setEnabled(False)
            ro = QLabel("Registry is read-only — presets cannot be deleted.")
            ro.setObjectName("Dim")
            ro.setWordWrap(True)
            root.addWidget(ro)

        self._rows: list[dict] = []
        self._reload()

    def _reload(self) -> None:
        ptype = str(self._type.currentData() or "") or None
        try:
            self._rows = self._persistence.registry.list_presets(ptype)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Preset library", str(exc))
            self._rows = []
        self._list.clear()
        for row in self._rows:
            label = f"[{row.get('preset_type')}] {row.get('name')}  (v{row.get('schema_version')})"
            item = QListWidgetItem(label)
            item.setData(256, row.get("preset_id"))
            self._list.addItem(item)
        self._detail.clear()

    def _show_detail(self, current: QListWidgetItem | None, _previous) -> None:
        if current is None:
            self._detail.clear()
            return
        pid = current.data(256)
        row = next((r for r in self._rows if r.get("preset_id") == pid), None)
        if row is None:
            return
        try:
            content = json.loads(row.get("content_json") or "{}")
        except json.JSONDecodeError:
            content = {"error": "invalid JSON"}
        doc = {
            "preset_id": row.get("preset_id"),
            "preset_type": row.get("preset_type"),
            "name": row.get("name"),
            "schema_version": row.get("schema_version"),
            "description": row.get("description"),
            "compatibility": row.get("compatibility_json"),
            "content": content,
        }
        self._detail.setPlainText(json.dumps(doc, indent=2))

    def _delete_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        pid = item.data(256)
        row = next((r for r in self._rows if r.get("preset_id") == pid), None)
        if row is None:
            return
        if row.get("builtin"):
            QMessageBox.information(self, "Preset library", "Built-in presets cannot be deleted.")
            return
        confirm = QMessageBox.question(
            self,
            "Delete preset",
            f"Delete preset “{row.get('name')}”?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._persistence.registry.delete_preset(str(pid))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Delete preset", str(exc))
            return
        self._reload()
