# SPDX-License-Identifier: GPL-3.0-only
"""Setup tab: source list + generic schema-driven configuration form."""

from __future__ import annotations

import json
from typing import Any

from capture_protocol.generated.capture.v1 import control_pb2
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .schema_form import SchemaForm
from .screen_capture import panel
from .state import CaptureState, SourceRow


class SetupScreen(QWidget):
    source_selected = Signal(str)
    apply_requested = Signal(str, object)  # source_id, document dict
    refresh_requested = Signal(str)

    def __init__(self, state: CaptureState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._current_source_id = ""
        self._schema_revision = ""

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        rail, rail_body = panel("Sources")
        rail.setFixedWidth(260)
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_list_changed)
        rail_body.addWidget(self._list, 1)
        root.addWidget(rail)

        center, center_body = panel()
        self._title = QLabel("Configuration")
        self._title.setObjectName("PanelTitle")
        self._title.setFont(theme.ui(11, bold=True))
        self._meta = QLabel("")
        self._meta.setObjectName("Dim")
        self._meta.setWordWrap(True)
        header = QVBoxLayout()
        header.setSpacing(2)
        header.addWidget(self._title)
        header.addWidget(self._meta)
        center_body.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.form = SchemaForm()
        scroll.setWidget(self.form)
        center_body.addWidget(scroll, 1)

        self._dirty = QLabel("")
        self._dirty.setObjectName("Dim")
        self._dirty.setWordWrap(True)
        center_body.addWidget(self._dirty)

        buttons = QHBoxLayout()
        self.btn_reload = QPushButton("Reload schema")
        self.btn_reload.clicked.connect(self._on_reload)
        self.btn_save_preset = QPushButton("Save preset")
        self.btn_save_preset.clicked.connect(self._on_save_preset)
        self.btn_load_preset = QPushButton("Load preset")
        self.btn_load_preset.clicked.connect(self._on_load_preset)
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setObjectName("Primary")
        self.btn_apply.clicked.connect(self._on_apply)
        self.btn_apply.setEnabled(False)
        buttons.addWidget(self.btn_reload)
        buttons.addWidget(self.btn_save_preset)
        buttons.addWidget(self.btn_load_preset)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_apply)
        center_body.addLayout(buttons)
        root.addWidget(center, 1)

        self.form.dirty_changed.connect(self._on_dirty)
        self._preset_save_handler = None
        self._preset_load_handler = None

    def set_preset_handlers(self, save_handler, load_handler) -> None:
        self._preset_save_handler = save_handler
        self._preset_load_handler = load_handler

    def rebuild_sources(self) -> None:
        current = self._current_source_id
        locked = self._config_locked()
        self._list.blockSignals(True)
        self._list.clear()
        for src in self.state.sources:
            snap = self.state.health.get(src.source_id)
            level = "ok"
            if snap is not None and snap.HasField("last_error") and snap.last_error.message:
                level = "fail"
            elif self.state.has_open_gap(src.source_id):
                level = "warn"
            color = {
                "ok": theme.GREEN.name(),
                "warn": theme.ORANGE.name(),
                "fail": theme.RED.name(),
            }[level]
            item = QListWidgetItem(f"● {src.alias}\n{src.source_id}")
            item.setData(Qt.ItemDataRole.UserRole, src.source_id)
            tip = src.source_type
            if locked:
                tip += "\nConfiguration locked while recording."
            if snap is not None and snap.HasField("last_error") and snap.last_error.message:
                tip += f"\n{snap.last_error.message}"
            item.setToolTip(tip)
            item.setForeground(QColor(color))
            self._list.addItem(item)
            if src.source_id == current:
                self._list.setCurrentItem(item)
        self._list.blockSignals(False)
        if self._list.currentItem() is None and self._list.count() > 0:
            self._list.setCurrentRow(0)
        self.set_locked(locked)

    def current_source_id(self) -> str:
        return self._current_source_id

    def show_schema(
        self,
        source_id: str,
        schema: dict[str, Any],
        current: dict[str, Any] | None,
        *,
        schema_revision: str = "",
        error: str | None = None,
    ) -> None:
        self._current_source_id = source_id
        self._schema_revision = schema_revision or str(
            schema.get("schema_revision") or ""
        )
        src = self._find(source_id)
        title = schema.get("title") or (src.alias if src else source_id)
        self._title.setText(str(title))
        bits = [source_id]
        if self._schema_revision:
            bits.append(f"revision {self._schema_revision}")
        if src:
            bits.append(src.source_type)
        self._meta.setText(" · ".join(bits))

        disabled = None
        if error:
            disabled = error
        elif self._config_locked():
            disabled = "Configuration is locked while the session is recording."

        if error and not schema:
            self.form.clear()
            self._dirty.setText(error)
            self.btn_apply.setEnabled(False)
            return

        self.form.load(schema, current, disabled_reason=disabled)
        self._on_dirty(self.form.is_dirty())

    def set_locked(self, locked: bool, reason: str = "") -> None:
        """Disable editing when session state forbids ApplyConfig."""
        if not self.form.schema:
            return
        msg = reason or (
            "Configuration is locked while the session is recording."
            if locked
            else ""
        )
        self.form.set_editable(not locked)
        self.btn_apply.setEnabled(self.form.is_dirty() and not locked)
        if locked:
            self._dirty.setText(msg)

    def set_applying(self, applying: bool) -> None:
        """Immediate Apply click feedback while the RPC is in flight."""
        if applying:
            self._dirty.setText("Applying…")
            self.btn_apply.setEnabled(False)
            self.btn_apply.setText("Applying…")
        else:
            self.btn_apply.setText("Apply")
            self.btn_apply.setEnabled(self.form.is_dirty() and not self._config_locked())

    def apply_result(
        self,
        *,
        effective: dict[str, Any] | None,
        coerced: list[str] | None = None,
        error: str | None = None,
        schema_revision: str = "",
    ) -> None:
        if error:
            QMessageBox.warning(self, "Apply configuration", error)
            return
        if schema_revision and schema_revision != self._schema_revision:
            QMessageBox.information(
                self,
                "Schema changed",
                "The device published a new schema revision. Reloading.",
            )
            self.refresh_requested.emit(self._current_source_id)
            return
        self.form.mark_clean(effective)
        self.form.highlight_coerced(coerced)
        note = "Applied."
        if coerced:
            note = f"Applied (coerced: {', '.join(coerced)})."
        self._dirty.setText(note)
        self.btn_apply.setEnabled(False)

    def _config_locked(self) -> bool:
        return self.state.session_state in (
            control_pb2.SESSION_STATE_RECORDING,
            control_pb2.SESSION_STATE_ARMING,
        )

    def _find(self, source_id: str) -> SourceRow | None:
        for src in self.state.sources:
            if src.source_id == source_id:
                return src
        return None

    def _on_list_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        source_id = current.data(Qt.ItemDataRole.UserRole)
        if not source_id:
            return
        self._current_source_id = str(source_id)
        self.source_selected.emit(self._current_source_id)

    def _on_reload(self) -> None:
        if self._current_source_id:
            self.refresh_requested.emit(self._current_source_id)

    def _on_dirty(self, dirty: bool) -> None:
        locked = self._config_locked()
        self.btn_apply.setEnabled(dirty and not locked and bool(self._current_source_id))
        if locked:
            self._dirty.setText("Configuration is locked while recording.")
            return
        if not dirty:
            if not self._dirty.text().startswith("Applied"):
                self._dirty.setText("")
            return
        changed, restart = self.form.change_summary()
        parts = []
        if changed:
            parts.append("Will change: " + ", ".join(changed))
        if restart:
            parts.append("Applying will restart the device stream.")
        self._dirty.setText(" ".join(parts))

    def _on_apply(self) -> None:
        if not self._current_source_id:
            return
        ok, errors = self.form.validate()
        if not ok:
            QMessageBox.warning(
                self, "Invalid configuration", "\n".join(errors) or "Invalid values"
            )
            return
        changed, restart = self.form.change_summary()
        if restart:
            answer = QMessageBox.question(
                self,
                "Restart required",
                "One or more fields require a stream restart.\n\nApply anyway?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        if not changed:
            return
        self.apply_requested.emit(self._current_source_id, self.form.values())

    def _on_save_preset(self) -> None:
        if self._preset_save_handler is None or not self._current_source_id:
            return
        self._preset_save_handler(self._current_source_id, self.form)

    def _on_load_preset(self) -> None:
        if self._preset_load_handler is None or not self._current_source_id:
            return
        self._preset_load_handler(self._current_source_id, self.form)

    def schema_revision(self) -> str:
        return self._schema_revision

    def form_document(self) -> dict[str, Any]:
        return self.form.values()


def parse_json_object(raw: str | bytes | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return doc if isinstance(doc, dict) else {}
