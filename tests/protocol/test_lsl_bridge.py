# SPDX-License-Identifier: GPL-3.0-only
"""LSL bridge worker unit tests (no live LSL required)."""

from __future__ import annotations

from lsl_bridge import LslBridgeWorker


def test_lsl_discover_without_pylsl_is_honest() -> None:
    worker = LslBridgeWorker()
    sources = worker.discover()
    assert sources
    assert all(s.plugin_id == "lsl.bridge" for s in sources)


def test_lsl_config_roundtrip() -> None:
    worker = LslBridgeWorker()
    schema = worker.config_schema("any")
    assert "name_filter" in schema["properties"]
    eff = worker.apply_config(
        "any", {"name_filter": "EEG", "type_filter": "EEG", "chunk_size": 16}
    )
    assert eff["name_filter"] == "EEG"
    assert eff["chunk_size"] == 16
