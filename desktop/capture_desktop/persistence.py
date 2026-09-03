# SPDX-License-Identifier: GPL-3.0-only
"""Bridge between Qt UI state and SETTINGS_REGISTRY appdata stores."""

from __future__ import annotations

import base64
import hashlib

from capture_session.registry import AppRegistry
from capture_session.settings_store import SettingsStore
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget


def monitor_fingerprint() -> str:
    screens = QGuiApplication.screens()
    parts = []
    for screen in screens:
        geo = screen.geometry()
        parts.append(
            f"{screen.name()}:{geo.width()}x{geo.height()}@{geo.x()},{geo.y()}"
        )
    raw = "|".join(parts) or "default"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{len(screens)}:{digest}"


class DesktopPersistence:
    def __init__(self) -> None:
        self.settings = SettingsStore()
        self.settings.load()
        self.registry = AppRegistry()
        self.registry_open = self.registry.open()

    def close(self) -> None:
        self.registry.close()

    def restore_window(self, window: QWidget) -> int:
        """Restore geometry; returns saved view_mode (default 0)."""
        entry = self.settings.geometry_for(monitor_fingerprint())
        if not entry:
            window.resize(1440, 900)
            return 0
        geo_b64 = entry.get("geometry_b64")
        if isinstance(geo_b64, str) and geo_b64:
            try:
                raw = base64.b64decode(geo_b64.encode("ascii"))
                window.restoreGeometry(QByteArray(raw))
            except Exception:  # noqa: BLE001
                window.resize(1440, 900)
        else:
            window.resize(1440, 900)
        return int(entry.get("view_mode", 0) or 0)

    def save_window(self, window: QWidget, view_mode: int) -> None:
        geo = bytes(window.saveGeometry())
        self.settings.set_geometry_for(
            monitor_fingerprint(),
            {
                "geometry_b64": base64.b64encode(geo).decode("ascii"),
                "view_mode": int(view_mode),
            },
        )

    def confirm_stop_always(self) -> bool:
        return bool(self.settings.get("confirm_stop_always", True))

    def preview_rate_limit_hz(self) -> float:
        return float(self.settings.get("preview_rate_limit_hz", 15) or 15)

    def preview_kind_styles(self) -> dict[str, str]:
        raw = self.settings.get("preview_kind_styles", {}) or {}
        if not isinstance(raw, dict):
            return {}
        out: dict[str, str] = {}
        for key, value in raw.items():
            if value in ("native", "graph"):
                out[str(key)] = value
        return out

    def set_preview_kind_style(self, kind: str, style: str) -> None:
        if style not in ("native", "graph"):
            return
        styles = self.preview_kind_styles()
        styles[kind] = style
        self.settings.set("preview_kind_styles", styles)

    def record_session(
        self,
        *,
        package_path: str,
        session_id: str,
        state: str,
    ) -> None:
        self.registry.touch_session(
            package_path=package_path,
            session_id=session_id,
            state=state,
        )
        parent = str(__import__("pathlib").Path(package_path).parent)
        self.settings.set("last_session_parent_path", parent)
