# SPDX-License-Identifier: GPL-3.0-only
"""Plugin compatibility / Hello negotiation tests."""

from __future__ import annotations

from capture_protocol.constants import PROTOCOL_MAJOR, PROTOCOL_MINOR
from capture_protocol.generated.capture.v1 import common_pb2
from capture_protocol.handshake import build_ui_hello, build_worker_hello, negotiate_hello


def test_worker_hello_accepted() -> None:
    hello = build_worker_hello(
        plugin_id="sim.multimodal",
        plugin_version="0.1.0",
        worker_id="w1",
        supported_operations=4 | 16,
    )
    ack = negotiate_hello(hello, instance_id="inst-1")
    assert ack.accepted
    assert ack.negotiated.major == PROTOCOL_MAJOR
    assert ack.instance_id == "inst-1"
    assert not ack.error.code


def test_major_mismatch_rejected() -> None:
    hello = build_worker_hello(
        plugin_id="sim.multimodal",
        plugin_version="0.1.0",
        worker_id="w1",
        supported_operations=0,
    )
    hello.protocol.major = PROTOCOL_MAJOR + 1
    ack = negotiate_hello(hello, instance_id="inst-1")
    assert not ack.accepted
    assert ack.error.code == "PROTOCOL_MISMATCH"


def test_plugin_range_excludes_daemon() -> None:
    hello = build_worker_hello(
        plugin_id="old.plugin",
        plugin_version="0.0.1",
        worker_id="w1",
        supported_operations=0,
        min_daemon_major=2,
        min_daemon_minor=0,
        max_daemon_major=2,
        max_daemon_minor=9,
    )
    ack = negotiate_hello(hello, instance_id="inst-1")
    assert not ack.accepted
    assert ack.error.code == "PLUGIN_INCOMPATIBLE"


def test_worker_missing_plugin_id() -> None:
    hello = build_worker_hello(
        plugin_id="x",
        plugin_version="0.1.0",
        worker_id="w1",
        supported_operations=0,
    )
    hello.plugin_id = ""
    ack = negotiate_hello(hello, instance_id="inst-1")
    assert not ack.accepted
    assert ack.error.code == "INVALID_HELLO"


def test_ui_hello_accepted() -> None:
    hello = build_ui_hello()
    assert hello.role == "ui"
    ack = negotiate_hello(hello, instance_id="inst-1")
    assert ack.accepted
    assert ack.negotiated.minor <= PROTOCOL_MINOR


def test_hello_round_trip_bytes() -> None:
    hello = build_worker_hello(
        plugin_id="sim.multimodal",
        plugin_version="0.1.0",
        worker_id="w1",
        supported_operations=1,
    )
    raw = hello.SerializeToString()
    again = common_pb2.Hello()
    again.ParseFromString(raw)
    assert again.plugin_id == "sim.multimodal"
    assert again.protocol.major == PROTOCOL_MAJOR
