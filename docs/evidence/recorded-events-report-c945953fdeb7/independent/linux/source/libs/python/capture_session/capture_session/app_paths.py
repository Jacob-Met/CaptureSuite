# SPDX-License-Identifier: GPL-3.0-only
"""Machine-local CaptureSuite appdata paths (desktop-owned)."""

from __future__ import annotations

import os
from pathlib import Path


def appdata_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "CaptureSuite"
    return Path.home() / ".capturesuite"


def settings_path() -> Path:
    return appdata_root() / "settings.json"


def registry_path() -> Path:
    return appdata_root() / "registry.sqlite"


def logs_dir() -> Path:
    return appdata_root() / "logs"
