# SPDX-License-Identifier: GPL-3.0-only
"""LSL bridge worker unit tests (no live LSL required)."""

from __future__ import annotations

import threading

import pytest
from capture_protocol.generated.capture.v1 import worker_pb2
from lsl_bridge import LslBridgeWorker


def test_lsl_discover_without_pylsl_is_honest(monkeypatch) -> None:
    monkeypatch.setattr("lsl_bridge._try_import_pylsl", lambda: None)
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


def test_stopping_one_source_keeps_another_running(monkeypatch) -> None:
    worker = LslBridgeWorker()
    entered = {name: threading.Event() for name in ("a", "b")}

    def pump(source_id, stop, chunk, timeout):
        entered[source_id].set()
        stop.wait(3.0)

    monkeypatch.setattr(worker, "_pump", pump)
    try:
        worker.start("a", worker_pb2.StartRequest())
        worker.start("b", worker_pb2.StartRequest())
        assert entered["a"].wait(1.0) and entered["b"].wait(1.0)
        worker.stop("a")
        assert worker._threads["b"].is_alive()
        assert not worker._stops["b"].is_set()
        worker.stop("unknown")
        assert worker._threads["b"].is_alive()
        with pytest.raises(RuntimeError, match="already running"):
            worker.start("b", worker_pb2.StartRequest())
    finally:
        worker.stop("a")
        worker.stop("b")
    assert not worker._threads and not worker._stops


def test_stopped_source_event_is_never_reactivated(monkeypatch) -> None:
    worker = LslBridgeWorker()
    entered = threading.Event()

    def pump(source_id, stop, chunk, timeout):
        entered.set()
        stop.wait(3.0)

    monkeypatch.setattr(worker, "_pump", pump)
    worker.start("a", worker_pb2.StartRequest())
    assert entered.wait(1.0)
    previous = worker._stops["a"]
    worker.stop("a")
    try:
        worker.start("a", worker_pb2.StartRequest())
        assert previous.is_set()
        assert worker._stops["a"] is not previous
    finally:
        worker.stop("a")
