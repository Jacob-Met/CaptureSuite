# SPDX-License-Identifier: GPL-3.0-only
"""Generic JSON Schema form for the Setup tab (CONFIGURATION_UI.md)."""

from __future__ import annotations

import json
from typing import Any

from capture_protocol.config_schema import (
    dirty_summary,
    group_order,
    iter_fields,
    merge_current,
    validate_document,
)
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import theme


class SchemaForm(QWidget):
    """Renders the supported JSON Schema subset into editable controls."""

    dirty_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._schema: dict[str, Any] = {}
        self._baseline: dict[str, Any] = {}
        self._widgets: dict[str, QWidget] = {}
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(10)
        self._host = QWidget()
        self._host_layout = QVBoxLayout(self._host)
        self._host_layout.setContentsMargins(0, 0, 0, 0)
        self._host_layout.setSpacing(10)
        self._root.addWidget(self._host)
        self._empty = QLabel("Select a source to load its configuration schema.")
        self._empty.setObjectName("Dim")
        self._empty.setWordWrap(True)
        self._root.addWidget(self._empty)
        self._disabled_reason: str | None = None

    def clear(self) -> None:
        self._schema = {}
        self._baseline = {}
        self._widgets.clear()
        while self._host_layout.count():
            item = self._host_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._host.hide()
        self._empty.show()
        self.dirty_changed.emit(False)

    def load(
        self,
        schema: dict[str, Any],
        current: dict[str, Any] | None = None,
        *,
        disabled_reason: str | None = None,
    ) -> None:
        self.clear()
        self._schema = schema
        self._baseline = merge_current(schema, current)
        self._disabled_reason = disabled_reason
        self._empty.hide()
        self._host.show()

        fields = iter_fields(schema)
        if not fields:
            note = QLabel("This source publishes an empty configuration schema.")
            note.setObjectName("Dim")
            self._host_layout.addWidget(note)
            return

        if disabled_reason:
            banner = QLabel(disabled_reason)
            banner.setObjectName("Dim")
            banner.setWordWrap(True)
            banner.setStyleSheet(f"color: {theme.ORANGE.name()};")
            self._host_layout.addWidget(banner)

        by_group: dict[str, list] = {}
        for f in fields:
            by_group.setdefault(f.group, []).append(f)

        for group_name in group_order(fields):
            group_fields = by_group[group_name]
            box = QGroupBox(group_name)
            form = QFormLayout(box)
            form.setContentsMargins(10, 14, 10, 10)
            form.setSpacing(8)

            advanced = [f for f in group_fields if f.advanced]
            common = [f for f in group_fields if not f.advanced]

            for f in common:
                form.addRow(self._label_for(f), self._make_control(f))

            if advanced:
                adv = QGroupBox("Advanced")
                adv.setCheckable(True)
                adv.setChecked(False)
                adv_form = QFormLayout(adv)
                for f in advanced:
                    adv_form.addRow(self._label_for(f), self._make_control(f))
                form.addRow(adv)

            self._host_layout.addWidget(box)

        self._host_layout.addStretch(1)
        self._apply_enabled(disabled_reason is None)
        self.dirty_changed.emit(False)

    def _label_for(self, field) -> QLabel:
        title = str(field.prop.get("title") or field.name)
        units = field.prop.get("x-capture-units")
        if units:
            title = f"{title} ({units})"
        label = QLabel(title)
        desc = field.prop.get("description")
        if desc:
            label.setToolTip(str(desc))
        return label

    def _make_control(self, field) -> QWidget:
        prop = field.prop
        typ = prop.get("type")
        read_only = bool(prop.get("readOnly"))
        value = self._baseline.get(field.name, prop.get("default"))
        widget: QWidget

        if "enum" in prop and isinstance(prop["enum"], list):
            combo = QComboBox()
            labels = prop.get("x-capture-enum-labels") or {}
            if not isinstance(labels, dict):
                labels = {}
            for item in prop["enum"]:
                key = str(item)
                combo.addItem(str(labels.get(key, key)), item)
            idx = combo.findData(value)
            if idx < 0 and value is not None:
                # Coerce numeric enum match through string keys.
                for i in range(combo.count()):
                    if combo.itemData(i) == value or str(combo.itemData(i)) == str(
                        value
                    ):
                        idx = i
                        break
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(self._emit_dirty)
            widget = combo
        elif typ == "boolean":
            box = QCheckBox()
            box.setChecked(bool(value))
            box.toggled.connect(self._emit_dirty)
            widget = box
        elif typ == "integer":
            spin = QSpinBox()
            spin.setRange(
                int(prop.get("minimum", -2_147_483_648)),
                int(prop.get("maximum", 2_147_483_647)),
            )
            spin.setValue(int(value if value is not None else 0))
            spin.valueChanged.connect(self._emit_dirty)
            widget = spin
        elif typ == "number":
            spin = QDoubleSpinBox()
            spin.setDecimals(4)
            spin.setRange(
                float(prop.get("minimum", -1e12)),
                float(prop.get("maximum", 1e12)),
            )
            step = prop.get("multipleOf")
            if step:
                try:
                    spin.setSingleStep(float(step))
                except (TypeError, ValueError):
                    pass
            spin.setValue(float(value if value is not None else 0.0))
            spin.valueChanged.connect(self._emit_dirty)
            widget = spin
        elif typ == "array":
            line = QLineEdit()
            if isinstance(value, list):
                line.setText(json.dumps(value))
            elif value is not None:
                line.setText(str(value))
            line.setPlaceholderText("JSON array")
            line.textChanged.connect(self._emit_dirty)
            widget = line
        else:
            line = QLineEdit()
            line.setText("" if value is None else str(value))
            line.textChanged.connect(self._emit_dirty)
            widget = line

        widget.setEnabled(not read_only)
        if read_only:
            widget.setToolTip("Reported by the device (read-only)")
        self._widgets[field.name] = widget
        return widget

    def set_editable(self, enabled: bool) -> None:
        for name, widget in self._widgets.items():
            prop = (self._schema.get("properties") or {}).get(name) or {}
            if prop.get("readOnly"):
                widget.setEnabled(False)
            else:
                widget.setEnabled(enabled)

    def _apply_enabled(self, enabled: bool) -> None:
        self.set_editable(enabled)

    def _emit_dirty(self, *_args: object) -> None:
        self.dirty_changed.emit(self.is_dirty())

    def values(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        props = self._schema.get("properties") or {}
        for name, widget in self._widgets.items():
            prop = props.get(name) or {}
            if prop.get("readOnly"):
                continue
            if isinstance(widget, QCheckBox):
                out[name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                out[name] = widget.currentData()
            elif isinstance(widget, QSpinBox):
                out[name] = int(widget.value())
            elif isinstance(widget, QDoubleSpinBox):
                out[name] = float(widget.value())
            elif isinstance(widget, QLineEdit):
                text = widget.text()
                if prop.get("type") == "array":
                    try:
                        out[name] = json.loads(text) if text.strip() else []
                    except json.JSONDecodeError:
                        out[name] = text
                else:
                    out[name] = text
        return out

    def is_dirty(self) -> bool:
        if not self._schema:
            return False
        return self.values() != {
            k: v
            for k, v in self._baseline.items()
            if not ((self._schema.get("properties") or {}).get(k) or {}).get(
                "readOnly"
            )
        }

    def validate(self) -> tuple[bool, list[str]]:
        result = validate_document(self._schema, self.values())
        return result.ok, result.errors

    def change_summary(self) -> tuple[list[str], bool]:
        return dirty_summary(self._schema, self._baseline, self.values())

    def set_values(self, document: dict[str, Any], *, as_baseline: bool = False) -> None:
        """Push values into controls. If as_baseline, the form becomes clean."""
        for name, widget in self._widgets.items():
            if name not in document:
                continue
            value = document[name]
            widget.blockSignals(True)
            try:
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QComboBox):
                    idx = widget.findData(value)
                    if idx < 0:
                        for i in range(widget.count()):
                            if str(widget.itemData(i)) == str(value):
                                idx = i
                                break
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(value))
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value))
                elif isinstance(widget, QLineEdit):
                    if isinstance(value, list):
                        widget.setText(json.dumps(value))
                    else:
                        widget.setText("" if value is None else str(value))
            finally:
                widget.blockSignals(False)
        if as_baseline:
            self._baseline = merge_current(self._schema, document)
            self.dirty_changed.emit(False)
        else:
            self.dirty_changed.emit(self.is_dirty())

    def mark_clean(self, effective: dict[str, Any] | None = None) -> None:
        if effective is not None:
            self.set_values(effective, as_baseline=True)
        else:
            self._baseline = self.values()
            self.dirty_changed.emit(False)

    def highlight_coerced(self, fields: list[str] | None) -> None:
        """Visually mark fields the device coerced on the last Apply."""
        coerced = set(fields or [])
        for name, widget in self._widgets.items():
            if name in coerced:
                widget.setStyleSheet(
                    f"border: 1px solid {theme.ACCENT.name()};"
                    f"background: {theme.PANEL_ALT.name()};"
                )
                tip = widget.toolTip() or ""
                note = "Device coerced this value to the effective setting."
                widget.setToolTip(f"{tip}\n{note}".strip() if tip else note)
            else:
                widget.setStyleSheet("")

    @property
    def schema(self) -> dict[str, Any]:
        return self._schema
