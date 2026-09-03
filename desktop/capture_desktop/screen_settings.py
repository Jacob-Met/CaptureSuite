# SPDX-License-Identifier: GPL-3.0-only
"""Preferences dialog — core settings from SETTINGS_REGISTRY."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .persistence import DesktopPersistence


class PreferencesDialog(QDialog):
    def __init__(
        self,
        persistence: DesktopPersistence,
        *,
        on_theme_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._persistence = persistence
        self._on_theme_changed = on_theme_changed
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(420)
        self.setFont(theme.ui(9))

        root = QVBoxLayout(self)
        appearance = QGroupBox("Appearance")
        appearance.setFont(theme.ui(9, bold=True))
        form_a = QFormLayout(appearance)
        self._theme = QComboBox()
        self._theme.addItems(["system", "light", "dark"])
        current = str(persistence.settings.get("theme") or "system")
        idx = self._theme.findText(current)
        self._theme.setCurrentIndex(idx if idx >= 0 else 0)
        form_a.addRow("Theme", self._theme)
        root.addWidget(appearance)

        capture = QGroupBox("Capture")
        capture.setFont(theme.ui(9, bold=True))
        form_c = QFormLayout(capture)
        self._preview_hz = QDoubleSpinBox()
        self._preview_hz.setRange(1.0, 60.0)
        self._preview_hz.setSingleStep(1.0)
        self._preview_hz.setValue(float(persistence.preview_rate_limit_hz()))
        form_c.addRow("Preview rate limit (Hz)", self._preview_hz)
        self._grid_cols = QSpinBox()
        self._grid_cols.setRange(0, 8)
        self._grid_cols.setSpecialValueText("auto")
        self._grid_cols.setValue(
            int(persistence.settings.get("preview_grid_columns") or 0)
        )
        form_c.addRow("Preview grid columns", self._grid_cols)
        self._confirm_stop = QCheckBox("Always confirm Stop")
        self._confirm_stop.setChecked(persistence.confirm_stop_always())
        form_c.addRow("", self._confirm_stop)
        root.addWidget(capture)

        alerts = QGroupBox("Alerts")
        alerts.setFont(theme.ui(9, bold=True))
        form_al = QFormLayout(alerts)
        self._audible = QCheckBox("Audible alerts")
        self._audible.setChecked(
            bool(persistence.settings.get("audible_alerts_enabled", True))
        )
        form_al.addRow("", self._audible)
        root.addWidget(alerts)

        advanced = QGroupBox("Advanced")
        advanced.setFont(theme.ui(9, bold=True))
        form_adv = QFormLayout(advanced)
        self._log_level = QComboBox()
        self._log_level.addItems(["info", "debug", "warning", "error"])
        log = str(persistence.settings.get("log_level") or "info")
        li = self._log_level.findText(log)
        self._log_level.setCurrentIndex(li if li >= 0 else 0)
        form_adv.addRow("Log level", self._log_level)
        self._update_channel = QComboBox()
        self._update_channel.addItems(["stable", "beta", "dev"])
        ch = str(persistence.settings.get("update_channel") or "stable")
        ci = self._update_channel.findText(ch)
        self._update_channel.setCurrentIndex(ci if ci >= 0 else 0)
        form_adv.addRow("Update channel", self._update_channel)
        root.addWidget(advanced)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _save(self) -> None:
        store = self._persistence.settings
        prev_theme = str(store.get("theme") or "system")
        store.set("theme", self._theme.currentText())
        store.set("preview_rate_limit_hz", float(self._preview_hz.value()))
        store.set("preview_grid_columns", int(self._grid_cols.value()))
        store.set("confirm_stop_always", self._confirm_stop.isChecked())
        store.set("audible_alerts_enabled", self._audible.isChecked())
        store.set("log_level", self._log_level.currentText())
        store.set("update_channel", self._update_channel.currentText())
        if self._on_theme_changed and self._theme.currentText() != prev_theme:
            self._on_theme_changed()
        self.accept()
