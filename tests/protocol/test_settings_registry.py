# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import json
from pathlib import Path

from capture_session.registry import REGISTRY_SCHEMA_VERSION, AppRegistry
from capture_session.settings_store import SETTINGS_SCHEMA_VERSION, SettingsStore


def test_settings_atomic_roundtrip_preserves_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.load()
    store.set("theme", "dark", save=False)
    store.set("future_flag", True)
    store.save()

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["settings_schema_version"] == SETTINGS_SCHEMA_VERSION
    assert raw["theme"] == "dark"
    assert raw["future_flag"] is True
    assert raw["confirm_stop_always"] is True

    again = SettingsStore(path)
    again.load()
    assert again.get("theme") == "dark"
    assert again.get("future_flag") is True


def test_settings_geometry_per_fingerprint(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    store.set_geometry_for("fp-a", {"geometry_b64": "AAA=", "view_mode": 1})
    store.set_geometry_for("fp-b", {"geometry_b64": "BBB=", "view_mode": 2})
    assert store.geometry_for("fp-a")["view_mode"] == 1
    assert store.geometry_for("fp-b")["geometry_b64"] == "BBB="


def test_registry_migrates_and_tracks_sessions(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    with AppRegistry(path) as reg:
        assert reg.schema_version == REGISTRY_SCHEMA_VERSION
        assert not reg.read_only
        reg.touch_session(
            package_path=str(tmp_path / "a.mmsession"),
            session_id="s1",
            state="preparing",
        )
        reg.upsert_device(
            stable_device_key="cam-1",
            plugin_id="camera.mf",
            friendly_name="Webcam",
            last_source_id="cam.src",
        )
        reg.put_preset(
            preset_id="p1",
            preset_type="hotkey",
            name="Defaults",
            schema_version="1.0.0",
            content_json="{}",
        )

    with AppRegistry(path) as reg:
        recent = reg.recent_sessions()
        assert len(recent) == 1
        assert recent[0]["session_id"] == "s1"
        assert reg.get_preset("p1")["name"] == "Defaults"
        reg.put_preset(
            preset_id="p-device",
            preset_type="device",
            name="EMG high gain",
            schema_version="sim.emg/1",
            content_json='{"schema_revision":"sim.emg/1","configuration":{"gain":2}}',
        )
        devices = reg.list_presets("device")
        assert len(devices) == 1
        assert devices[0]["name"] == "EMG high gain"
        assert reg.delete_preset("p-device")
        assert reg.list_presets("device") == []


def test_registry_newer_schema_opens_readonly(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    with AppRegistry(path) as reg:
        con = reg._require()  # noqa: SLF001
        with con:
            con.execute(
                "INSERT INTO schema_migrations(version, applied_utc) VALUES (?, ?)",
                (REGISTRY_SCHEMA_VERSION + 5, "2026-01-01T00:00:00Z"),
            )

    with AppRegistry(path) as reg:
        assert reg.read_only
        assert reg.schema_version == REGISTRY_SCHEMA_VERSION + 5
        # Writes are no-ops in read-only mode.
        reg.touch_session(
            package_path=str(tmp_path / "x.mmsession"),
            session_id="x",
            state="idle",
        )
        assert reg.recent_sessions() == []
