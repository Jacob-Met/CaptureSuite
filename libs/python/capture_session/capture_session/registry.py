# SPDX-License-Identifier: GPL-3.0-only
"""Non-authoritative application registry (SETTINGS_REGISTRY.md)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from capture_session.app_paths import registry_path

# Bump when adding a migration; never remove old migrations.
REGISTRY_SCHEMA_VERSION = 1

PRESET_TYPES = frozenset(
    {
        "device",
        "naming",
        "anatomical_mapping",
        "spatial_layout",
        "radar_array",
        "capture",
        "checkpoint_protocol",
        "hotkey",
        "workspace",
        "export",
    }
)

_MIGRATIONS: dict[int, str] = {
    1: """
    CREATE TABLE schema_migrations (
      version      INTEGER PRIMARY KEY,
      applied_utc  TEXT NOT NULL
    );

    CREATE TABLE devices (
      stable_device_key TEXT PRIMARY KEY,
      plugin_id         TEXT NOT NULL,
      vendor            TEXT,
      model             TEXT,
      serial            TEXT,
      friendly_name     TEXT,
      alias             TEXT,
      role              TEXT,
      first_seen_utc    TEXT NOT NULL,
      last_seen_utc     TEXT NOT NULL,
      last_source_id    TEXT,
      notes             TEXT
    );
    CREATE INDEX devices_by_plugin ON devices(plugin_id);

    CREATE TABLE presets (
      preset_id          TEXT PRIMARY KEY,
      preset_type        TEXT NOT NULL,
      name               TEXT NOT NULL,
      schema_version     TEXT NOT NULL,
      preset_version     INTEGER NOT NULL DEFAULT 1,
      description        TEXT,
      compatibility_json TEXT NOT NULL DEFAULT '{}',
      content_json       TEXT NOT NULL,
      created_utc        TEXT NOT NULL,
      updated_utc        TEXT NOT NULL,
      builtin            INTEGER NOT NULL DEFAULT 0
    );
    CREATE UNIQUE INDEX presets_type_name ON presets(preset_type, name);

    CREATE TABLE recent_sessions (
      package_path     TEXT PRIMARY KEY,
      session_id       TEXT NOT NULL,
      project          TEXT,
      participant      TEXT,
      visit            TEXT,
      state            TEXT NOT NULL,
      duration_ns      INTEGER,
      created_utc      TEXT NOT NULL,
      finalized_utc    TEXT,
      last_opened_utc  TEXT NOT NULL
    );

    CREATE TABLE plugin_states (
      plugin_id      TEXT PRIMARY KEY,
      plugin_version TEXT,
      enabled        INTEGER NOT NULL DEFAULT 1,
      last_seen_utc  TEXT,
      last_error     TEXT
    );
    """,
}


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RegistryOpenResult:
    read_only: bool
    schema_version: int
    message: str = ""


class AppRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or registry_path()
        self._con: sqlite3.Connection | None = None
        self.read_only = False
        self.schema_version = 0
        self.open_message = ""

    def open(self) -> RegistryOpenResult:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.path)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA foreign_keys=ON")
        self._con.execute("PRAGMA synchronous=NORMAL")

        current = self._current_version()
        if current > REGISTRY_SCHEMA_VERSION:
            self.read_only = True
            self.schema_version = current
            self.open_message = (
                f"registry schema {current} is newer than this build "
                f"({REGISTRY_SCHEMA_VERSION}); opened read-only"
            )
            return RegistryOpenResult(True, current, self.open_message)

        if current < REGISTRY_SCHEMA_VERSION:
            self._migrate(current)
            current = REGISTRY_SCHEMA_VERSION

        self.read_only = False
        self.schema_version = current
        return RegistryOpenResult(False, current)

    def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None

    def __enter__(self) -> AppRegistry:
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _require(self) -> sqlite3.Connection:
        if self._con is None:
            raise RuntimeError("registry not open")
        return self._con

    def _current_version(self) -> int:
        con = self._require()
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if row is None:
            return 0
        ver = con.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
        return int(ver[0]) if ver else 0

    def _migrate(self, from_version: int) -> None:
        if self.read_only:
            raise RuntimeError("cannot migrate a read-only registry")
        con = self._require()
        for version in range(from_version + 1, REGISTRY_SCHEMA_VERSION + 1):
            sql = _MIGRATIONS[version]
            with con:
                con.executescript(sql)
                con.execute(
                    "INSERT INTO schema_migrations(version, applied_utc) VALUES (?, ?)",
                    (version, _utc_now()),
                )

    def touch_session(
        self,
        *,
        package_path: str,
        session_id: str,
        state: str,
        project: str | None = None,
        participant: str | None = None,
        visit: str | None = None,
        duration_ns: int | None = None,
        created_utc: str | None = None,
        finalized_utc: str | None = None,
    ) -> None:
        if self.read_only:
            return
        con = self._require()
        now = _utc_now()
        with con:
            con.execute(
                """
                INSERT INTO recent_sessions(
                  package_path, session_id, project, participant, visit, state,
                  duration_ns, created_utc, finalized_utc, last_opened_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(package_path) DO UPDATE SET
                  session_id=excluded.session_id,
                  project=excluded.project,
                  participant=excluded.participant,
                  visit=excluded.visit,
                  state=excluded.state,
                  duration_ns=COALESCE(excluded.duration_ns, recent_sessions.duration_ns),
                  finalized_utc=COALESCE(excluded.finalized_utc, recent_sessions.finalized_utc),
                  last_opened_utc=excluded.last_opened_utc
                """,
                (
                    package_path,
                    session_id,
                    project,
                    participant,
                    visit,
                    state,
                    duration_ns,
                    created_utc or now,
                    finalized_utc,
                    now,
                ),
            )

    def recent_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        con = self._require()
        rows = con.execute(
            """
            SELECT package_path, session_id, project, participant, visit, state,
                   duration_ns, created_utc, finalized_utc, last_opened_utc
            FROM recent_sessions
            ORDER BY last_opened_utc DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def upsert_device(
        self,
        *,
        stable_device_key: str,
        plugin_id: str,
        vendor: str | None = None,
        model: str | None = None,
        serial: str | None = None,
        friendly_name: str | None = None,
        alias: str | None = None,
        role: str | None = None,
        last_source_id: str | None = None,
    ) -> None:
        if self.read_only:
            return
        con = self._require()
        now = _utc_now()
        with con:
            existing = con.execute(
                "SELECT first_seen_utc FROM devices WHERE stable_device_key=?",
                (stable_device_key,),
            ).fetchone()
            if existing is None:
                con.execute(
                    """
                    INSERT INTO devices(
                      stable_device_key, plugin_id, vendor, model, serial,
                      friendly_name, alias, role, first_seen_utc, last_seen_utc,
                      last_source_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stable_device_key,
                        plugin_id,
                        vendor,
                        model,
                        serial,
                        friendly_name,
                        alias,
                        role,
                        now,
                        now,
                        last_source_id,
                    ),
                )
            else:
                con.execute(
                    """
                    UPDATE devices SET
                      plugin_id=?, vendor=?, model=?, serial=?,
                      friendly_name=COALESCE(?, friendly_name),
                      alias=COALESCE(?, alias),
                      role=COALESCE(?, role),
                      last_seen_utc=?,
                      last_source_id=COALESCE(?, last_source_id)
                    WHERE stable_device_key=?
                    """,
                    (
                        plugin_id,
                        vendor,
                        model,
                        serial,
                        friendly_name,
                        alias,
                        role,
                        now,
                        last_source_id,
                        stable_device_key,
                    ),
                )

    def put_preset(
        self,
        *,
        preset_id: str,
        preset_type: str,
        name: str,
        schema_version: str,
        content_json: str,
        description: str | None = None,
        compatibility_json: str = "{}",
        preset_version: int = 1,
        builtin: bool = False,
    ) -> None:
        if preset_type not in PRESET_TYPES:
            raise ValueError(f"unknown preset_type: {preset_type}")
        if self.read_only:
            raise RuntimeError("registry is read-only")
        con = self._require()
        now = _utc_now()
        with con:
            con.execute(
                """
                INSERT INTO presets(
                  preset_id, preset_type, name, schema_version, preset_version,
                  description, compatibility_json, content_json,
                  created_utc, updated_utc, builtin
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(preset_id) DO UPDATE SET
                  preset_type=excluded.preset_type,
                  name=excluded.name,
                  schema_version=excluded.schema_version,
                  preset_version=excluded.preset_version,
                  description=excluded.description,
                  compatibility_json=excluded.compatibility_json,
                  content_json=excluded.content_json,
                  updated_utc=excluded.updated_utc,
                  builtin=excluded.builtin
                """,
                (
                    preset_id,
                    preset_type,
                    name,
                    schema_version,
                    preset_version,
                    description,
                    compatibility_json,
                    content_json,
                    now,
                    now,
                    1 if builtin else 0,
                ),
            )

    def get_preset(self, preset_id: str) -> dict[str, Any] | None:
        con = self._require()
        row = con.execute(
            "SELECT * FROM presets WHERE preset_id=?", (preset_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_presets(self, preset_type: str | None = None) -> list[dict[str, Any]]:
        con = self._require()
        if preset_type is None:
            rows = con.execute(
                "SELECT * FROM presets ORDER BY preset_type, name"
            ).fetchall()
        else:
            if preset_type not in PRESET_TYPES:
                raise ValueError(f"unknown preset_type: {preset_type}")
            rows = con.execute(
                "SELECT * FROM presets WHERE preset_type=? ORDER BY name",
                (preset_type,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_preset(self, preset_id: str) -> bool:
        if self.read_only:
            raise RuntimeError("registry is read-only")
        con = self._require()
        with con:
            cur = con.execute("DELETE FROM presets WHERE preset_id=?", (preset_id,))
        return cur.rowcount > 0
