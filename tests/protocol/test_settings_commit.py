# SPDX-License-Identifier: GPL-3.0-only
"""Settings rejected by the durable writer must not enter later saves."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from capture_session.settings_store import SETTINGS_SCHEMA_VERSION, SettingsStore


def _store(path: Path) -> SettingsStore:
    store = SettingsStore(path)
    store.update(
        {
            "theme": "light",
            "recent_projects": ["older", "oldest"],
            "window_geometry": {"monitor-a": {"geometry_b64": "old"}},
            "future_settings": {"nested": ["preserved"]},
        }
    )
    return store


def _change(store: SettingsStore, operation: str) -> None:
    if operation == "set":
        store.set("theme", "dark")
    elif operation == "update":
        store.update({"theme": "dark", "new_setting": "reviewed"})
    elif operation == "recent":
        store.push_recent_project("new-project", max_items=2)
    elif operation == "geometry":
        store.set_geometry_for("monitor-b", {"geometry_b64": "new"})
    else:
        raise AssertionError(f"unknown test operation: {operation}")


@pytest.mark.parametrize("operation", ["set", "update", "recent", "geometry"])
def test_failed_change_cannot_leak_into_an_unrelated_save(
    tmp_path: Path, operation: str
) -> None:
    path = tmp_path / "settings.json"
    store = _store(path)
    before = store.data()
    original_bytes = path.read_bytes()

    with patch("capture_session.settings_store.os.replace", side_effect=OSError("refused")):
        with pytest.raises(OSError, match="refused"):
            _change(store, operation)

    rejected_memory = store.data()
    rejected_bytes = path.read_bytes()
    temporary_files = list(tmp_path.glob("settings.json.*.tmp"))
    store.set("log_level", "debug")
    expected = {**before, "log_level": "debug"}

    assert rejected_memory == before
    assert rejected_bytes == original_bytes
    assert temporary_files == []
    assert store.data() == expected
    assert json.loads(path.read_text(encoding="utf-8")) == expected
    assert SettingsStore(path).data() == expected

    _change(store, operation)
    assert store.data() != expected
    assert SettingsStore(path).data() == store.data()


@pytest.mark.parametrize("operation", ["set", "update", "geometry"])
def test_unserializable_change_does_not_poison_a_later_save(
    tmp_path: Path, operation: str
) -> None:
    path = tmp_path / "settings.json"
    store = _store(path)
    before = store.data()
    original_bytes = path.read_bytes()
    invalid = object()

    with pytest.raises(TypeError):
        if operation == "set":
            store.set("invalid", invalid)
        elif operation == "update":
            store.update({"theme": "dark", "invalid": invalid})
        else:
            store.set_geometry_for("monitor-b", {"invalid": invalid})

    rejected_memory = store.data()
    rejected_bytes = path.read_bytes()
    later_error = None
    try:
        store.set("log_level", "debug")
    except TypeError as exc:
        later_error = str(exc)

    assert rejected_memory == before
    assert rejected_bytes == original_bytes
    assert later_error is None
    assert SettingsStore(path).data() == {**before, "log_level": "debug"}
    assert list(tmp_path.glob("settings.json.*.tmp")) == []


def test_failed_immediate_change_preserves_previously_staged_settings(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = _store(path)
    original_bytes = path.read_bytes()
    store.set("theme", "dark", save=False)
    store.update({"preview_grid_columns": 3}, save=False)
    store.set_geometry_for("monitor-b", {"geometry_b64": "staged"}, save=False)
    staged = store.data()
    assert path.read_bytes() == original_bytes

    with patch("capture_session.settings_store.os.replace", side_effect=OSError("refused")):
        with pytest.raises(OSError, match="refused"):
            store.update({"theme": "light", "rejected": True})

    rejected_memory = store.data()
    rejected_bytes = path.read_bytes()
    store.save()
    assert rejected_memory == staged
    assert rejected_bytes == original_bytes
    assert SettingsStore(path).data() == staged


def test_explicit_save_failure_keeps_staged_values_and_schema_until_retry(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = _store(path)
    original_bytes = path.read_bytes()
    store.set("theme", "dark", save=False)
    store.set("settings_schema_version", "future-version", save=False)
    staged = store.data()

    with patch("capture_session.settings_store.os.replace", side_effect=OSError("refused")):
        with pytest.raises(OSError, match="refused"):
            store.save()

    rejected_memory = store.data()
    rejected_bytes = path.read_bytes()
    store.save()
    assert rejected_memory == staged
    assert rejected_bytes == original_bytes
    assert SettingsStore(path).data() == {
        **staged,
        "settings_schema_version": SETTINGS_SCHEMA_VERSION,
    }


def test_first_write_failure_preserves_defaults_until_explicit_retry(tmp_path: Path) -> None:
    path = tmp_path / "new" / "settings.json"
    store = SettingsStore(path)
    before = store.data()

    with patch("capture_session.settings_store.os.replace", side_effect=OSError("refused")):
        with pytest.raises(OSError, match="refused"):
            store.set("theme", "dark")

    rejected_memory = store.data()
    absent_after_failure = not path.exists()
    temporary_files = list(path.parent.glob("settings.json.*.tmp"))
    store.set("theme", "dark")
    assert rejected_memory == before
    assert absent_after_failure
    assert temporary_files == []
    assert SettingsStore(path).get("theme") == "dark"


def test_explicit_invalid_staging_can_be_corrected_and_saved(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = _store(path)
    original_bytes = path.read_bytes()
    invalid: dict[str, Any] = {"value": object()}
    store.set("draft", invalid, save=False)

    with pytest.raises(TypeError):
        store.save()
    assert path.read_bytes() == original_bytes
    assert "draft" in store.data()
    store.set("draft", {"value": "corrected"}, save=False)
    store.save()
    assert SettingsStore(path).get("draft") == {"value": "corrected"}
