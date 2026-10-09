# SPDX-License-Identifier: GPL-3.0-only
"""Versioned settings.json with atomic writes (SETTINGS_REGISTRY.md)."""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from capture_session.app_paths import settings_path

SETTINGS_SCHEMA_VERSION = "1.0.0"

DEFAULTS: dict[str, Any] = {
    "settings_schema_version": SETTINGS_SCHEMA_VERSION,
    "theme": "system",
    "window_geometry": None,
    "active_workspace_preset_id": None,
    "active_hotkey_preset_id": None,
    "global_hotkeys_enabled": False,
    "recent_projects": [],
    "last_session_parent_path": None,
    "last_export_path": None,
    "preview_enabled_default": True,
    "preview_rate_limit_hz": 15,
    "preview_grid_columns": 0,
    # Per preview-kind display: "native" (default) or "graph" for ORIENTATION / MATRIX_2D.
    "preview_kind_styles": {},
    "audible_alerts_enabled": True,
    "update_channel": "stable",
    "log_level": "info",
    "confirm_stop_always": True,
}


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class SettingsStore:
    """Load/merge/save settings.json. Unknown keys are preserved on write."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_path()
        self._data: dict[str, Any] = deepcopy(DEFAULTS)
        self._loaded = False

    def load(self) -> dict[str, Any]:
        if self.path.is_file():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("settings.json root must be an object")
            merged = deepcopy(DEFAULTS)
            merged.update(raw)
            # Never let a file drop the schema version below what we understand
            # for *new* keys; unknown keys stay via update above.
            if "settings_schema_version" not in raw:
                merged["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
            self._data = merged
        else:
            self._data = deepcopy(DEFAULTS)
        self._loaded = True
        return self.data()

    def data(self) -> dict[str, Any]:
        if not self._loaded:
            self.load()
        return deepcopy(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        if not self._loaded:
            self.load()
        return deepcopy(self._data.get(key, default))

    def set(self, key: str, value: Any, *, save: bool = True) -> None:
        if not self._loaded:
            self.load()
        self._data[key] = value
        if save:
            self.save()

    def update(self, values: dict[str, Any], *, save: bool = True) -> None:
        if not self._loaded:
            self.load()
        self._data.update(values)
        if save:
            self.save()

    def save(self) -> None:
        if not self._loaded:
            self.load()
        self._data["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
        _atomic_write_json(self.path, self._data)

    def push_recent_project(self, path: str, *, max_items: int = 10) -> None:
        if not self._loaded:
            self.load()
        recent = [p for p in self._data.get("recent_projects", []) if p != path]
        recent.insert(0, path)
        self._data["recent_projects"] = recent[:max_items]
        self.save()

    def geometry_for(self, fingerprint: str) -> dict[str, Any] | None:
        geo = self.get("window_geometry")
        if not isinstance(geo, dict):
            return None
        entry = geo.get(fingerprint)
        return entry if isinstance(entry, dict) else None

    def set_geometry_for(
        self, fingerprint: str, entry: dict[str, Any], *, save: bool = True
    ) -> None:
        if not self._loaded:
            self.load()
        geo = self._data.get("window_geometry")
        if not isinstance(geo, dict):
            geo = {}
        geo = dict(geo)
        geo[fingerprint] = entry
        self._data["window_geometry"] = geo
        if save:
            self.save()
