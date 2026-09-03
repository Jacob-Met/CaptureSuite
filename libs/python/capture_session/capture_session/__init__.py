# SPDX-License-Identifier: GPL-3.0-only
"""Session package helpers and desktop-owned appdata (settings/registry)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capture_session.app_paths import appdata_root, registry_path, settings_path
from capture_session.package_reader import ReviewSummary, load_review_summary
from capture_session.registry import AppRegistry
from capture_session.settings_store import SettingsStore

__version__ = "0.1.0"

__all__ = [
    "SessionPackageError",
    "load_manifest",
    "load_integrity",
    "list_mcap_segments",
    "assert_package_durable",
    "load_review_summary",
    "ReviewSummary",
    "appdata_root",
    "settings_path",
    "registry_path",
    "SettingsStore",
    "AppRegistry",
]


class SessionPackageError(RuntimeError):
    pass


def load_manifest(package_root: str | Path) -> dict[str, Any]:
    path = Path(package_root) / "manifest.json"
    if not path.is_file():
        raise SessionPackageError(f"missing manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_integrity(package_root: str | Path) -> dict[str, Any]:
    path = Path(package_root) / "integrity.json"
    if not path.is_file():
        raise SessionPackageError(f"missing integrity: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_mcap_segments(package_root: str | Path) -> list[Path]:
    root = Path(package_root) / "sources"
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.mcap") if p.is_file())


def assert_package_durable(package_root: str | Path) -> dict[str, Any]:
    """Basic durability checks used by kill tests."""
    manifest = load_manifest(package_root)
    state = manifest.get("state", "")
    if state not in ("finalized", "finalized_recovered", "recording", "preparing"):
        raise SessionPackageError(f"unexpected state: {state}")
    segments = list_mcap_segments(package_root)
    if state.startswith("finalized") and not segments:
        raise SessionPackageError("finalized package has no mcap segments")
    integrity = None
    integrity_path = Path(package_root) / "integrity.json"
    if integrity_path.is_file():
        integrity = load_integrity(package_root)
    return {
        "manifest": manifest,
        "integrity": integrity,
        "segments": [str(p) for p in segments],
    }
