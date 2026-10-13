# SPDX-License-Identifier: GPL-3.0-only
"""A failed migration must leave its database ready for an explicit retry."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from capture_session import registry as registry_module
from capture_session.registry import AppRegistry


def _schema_names(path: Path) -> set[str]:
    with sqlite3.connect(path) as con:
        return {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
            )
        }


def _expect_open_failure(path: Path, error: type[Exception], message: str) -> None:
    registry = AppRegistry(path)
    try:
        with pytest.raises(error, match=message):
            registry.open()
    finally:
        registry.close()


@pytest.mark.parametrize("existing_empty_file", [False, True])
def test_failed_first_migration_rolls_back_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_empty_file: bool
) -> None:
    path = tmp_path / "registry.sqlite"
    if existing_empty_file:
        sqlite3.connect(path).close()
    original = registry_module._MIGRATIONS[1]
    with monkeypatch.context() as patch:
        patch.setitem(
            registry_module._MIGRATIONS,
            1,
            original + "\nSELECT unavailable_migration_hook();",
        )
        _expect_open_failure(path, sqlite3.OperationalError, "unavailable_migration_hook")

    assert _schema_names(path) == set()
    with AppRegistry(path) as registry:
        assert registry.schema_version == 1
        registry.touch_session(package_path="retained", session_id="session-1", state="idle")
    with AppRegistry(path) as registry:
        assert registry.recent_sessions()[0]["session_id"] == "session-1"


def test_failed_version_receipt_rolls_back_schema_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "registry.sqlite"
    reject_receipt = """
        CREATE TRIGGER reject_version_receipt
        BEFORE INSERT ON schema_migrations
        BEGIN
            SELECT RAISE(ABORT, 'version receipt rejected');
        END;
    """
    with monkeypatch.context() as patch:
        patch.setitem(
            registry_module._MIGRATIONS,
            1,
            registry_module._MIGRATIONS[1] + reject_receipt,
        )
        _expect_open_failure(path, sqlite3.IntegrityError, "version receipt rejected")

    assert _schema_names(path) == set()
    with AppRegistry(path) as registry:
        assert not registry.read_only
        assert registry.schema_version == 1


def test_failed_later_migration_keeps_prior_versions_and_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "registry.sqlite"
    with AppRegistry(path) as registry:
        registry.put_preset(
            preset_id="retained-preset",
            preset_type="hotkey",
            name="Retained name",
            schema_version="1.0.0",
            content_json='{"key":"F8"}',
        )

    second = """
        CREATE TABLE migration_v2 (note TEXT NOT NULL);
        INSERT INTO migration_v2(note) VALUES ('version two committed');
    """
    third = """
        UPDATE migration_v2 SET note='version three committed';
        UPDATE presets SET name='Updated name' WHERE preset_id='retained-preset';
        CREATE TABLE migration_v3 (note TEXT NOT NULL);
        INSERT INTO migration_v3(note) VALUES ('version three committed');
    """
    monkeypatch.setattr(registry_module, "REGISTRY_SCHEMA_VERSION", 3)
    monkeypatch.setitem(registry_module._MIGRATIONS, 2, second)
    monkeypatch.setitem(
        registry_module._MIGRATIONS, 3, third + "\nSELECT unavailable_migration_hook();"
    )
    _expect_open_failure(path, sqlite3.OperationalError, "unavailable_migration_hook")

    with sqlite3.connect(path) as con:
        assert con.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall() == [
            (1,),
            (2,),
        ]
        assert con.execute("SELECT note FROM migration_v2").fetchall() == [
            ("version two committed",)
        ]
        assert con.execute(
            "SELECT name, content_json FROM presets WHERE preset_id='retained-preset'"
        ).fetchone() == ("Retained name", '{"key":"F8"}')
    assert "migration_v3" not in _schema_names(path)

    monkeypatch.setitem(registry_module._MIGRATIONS, 3, third)
    with AppRegistry(path) as registry:
        assert registry.schema_version == 3
        assert registry.get_preset("retained-preset")["name"] == "Updated name"
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall() == [
            (1,),
            (2,),
            (3,),
        ]
        assert con.execute("SELECT note FROM migration_v2").fetchall() == [
            ("version three committed",)
        ]
        assert con.execute("SELECT note FROM migration_v3").fetchall() == [
            ("version three committed",)
        ]
    with AppRegistry(path) as registry:
        assert registry.schema_version == 3
