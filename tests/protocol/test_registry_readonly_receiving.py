# SPDX-License-Identifier: GPL-3.0-only
"""Receive future registries through real SQLite connections and public readers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from capture_session.registry import REGISTRY_SCHEMA_VERSION, AppRegistry


def _seed(path: Path) -> None:
    with AppRegistry(path) as registry:
        registry.touch_session(
            package_path="sealed.mmsession", session_id="session-17", state="finalized"
        )
        registry.put_preset(
            preset_id="future-preset",
            preset_type="hotkey",
            name="Retained preset",
            schema_version="1.0.0",
            content_json='{"key":"F8"}',
        )


def _advance(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT INTO schema_migrations(version, applied_utc) VALUES (?, ?)",
        (REGISTRY_SCHEMA_VERSION + 7, "2026-10-08T00:00:00Z"),
    )
    connection.commit()


@pytest.mark.parametrize("filename", ["registry.sqlite", "registry #future% 雪.sqlite"])
def test_future_registry_preserves_files_and_public_data(tmp_path: Path, filename: str) -> None:
    path = tmp_path / filename
    _seed(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=DELETE")
        _advance(connection)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    with AppRegistry(path) as registry:
        assert registry.read_only
        assert registry.schema_version == REGISTRY_SCHEMA_VERSION + 7
        assert registry.recent_sessions()[0]["session_id"] == "session-17"
        assert registry.get_preset("future-preset")["content_json"] == '{"key":"F8"}'
        registry.touch_session(package_path="ignored", session_id="ignored", state="idle")
        registry.upsert_device(stable_device_key="ignored", plugin_id="sim.imu")
        with pytest.raises(RuntimeError, match="read-only"):
            registry.delete_preset("future-preset")
        with pytest.raises(RuntimeError, match="read-only"):
            registry.put_preset(
                preset_id="ignored",
                preset_type="hotkey",
                name="Ignored",
                schema_version="1.0.0",
                content_json="{}",
            )
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            registry._require().execute("DELETE FROM presets")  # noqa: SLF001
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


def test_future_wal_registry_reads_committed_tail_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "wal registry #17.sqlite"
    _seed(path)
    writer = sqlite3.connect(path)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("UPDATE presets SET name='Newer committed preset'")
        _advance(writer)
        wal = Path(str(path) + "-wal")
        assert wal.is_file()
        before = (path.read_bytes(), wal.read_bytes())
        with AppRegistry(path) as registry:
            assert registry.read_only
            assert registry.schema_version == REGISTRY_SCHEMA_VERSION + 7
            assert registry.get_preset("future-preset")["name"] == "Newer committed preset"
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                registry._require().execute("DELETE FROM presets")  # noqa: SLF001
        assert (path.read_bytes(), wal.read_bytes()) == before
    finally:
        writer.close()


def test_existing_empty_database_still_migrates_and_accepts_writes(tmp_path: Path) -> None:
    path = tmp_path / "supported #registry%.sqlite"
    sqlite3.connect(path).close()
    with AppRegistry(path) as registry:
        assert not registry.read_only
        assert registry.schema_version == REGISTRY_SCHEMA_VERSION
        registry.touch_session(package_path="new.mmsession", session_id="new-session", state="idle")
    with AppRegistry(path) as registry:
        assert registry.recent_sessions()[0]["session_id"] == "new-session"
