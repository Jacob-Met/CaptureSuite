# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for the Python worker SDK (no daemon required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from capture_protocol.framing import Frame, decode_frame, encode_frame
from capture_protocol.generated.capture.v1 import common_pb2, worker_pb2
from capture_protocol.generated.capture.v1.common_pb2 import MessageType
from capture_protocol.handshake import build_worker_hello, negotiate_hello
from capture_worker.preview import build_trace_preview
from capture_worker.transport import MemoryTransport
from capture_worker.worker import run_handshake_for_tests
from capture_worker.writer import McapSegmentWriter
from example_sine import SineWorker


def test_sine_worker_discovers_numeric_batch_source() -> None:
    worker = SineWorker()
    sources = worker.discover()
    assert len(sources) == 1
    src = sources[0]
    assert src.source_id == "example.sine.main"
    assert src.plugin_id == "example.sine"
    assert src.streams[0].data_schema_id == "generic.numeric_batch/1"
    assert src.physical_devices[0].vendor == "CaptureSuite Example"


def test_sine_config_schema_and_apply() -> None:
    worker = SineWorker()
    schema = worker.config_schema("example.sine.main")
    assert schema["schema_revision"] == "example.sine/1"
    effective = worker.apply_config("example.sine.main", {"rate_hz": 50, "channels": 4})
    assert effective["rate_hz"] == 50
    assert effective["channels"] == 4


def test_hello_ack_path_with_memory_transport() -> None:
    worker = SineWorker(plugin_id="example.sine", worker_id="sine-hello")
    hello, ack = run_handshake_for_tests(worker, instance_id="daemon-test")
    assert hello.role == "worker"
    assert hello.plugin_id == "example.sine"
    assert hello.worker_id == "sine-hello"
    assert ack.accepted


def test_identify_discover_via_handle_frame() -> None:
    worker = SineWorker(plugin_id="example.sine", worker_id="sine-id")
    identify = worker.handle_frame(Frame(MessageType.MESSAGE_TYPE_IDENTIFY, 7, b""))
    assert identify is not None
    reply = worker_pb2.IdentifyReply()
    reply.ParseFromString(identify.payload)
    assert reply.manifest.plugin_id == "example.sine"
    assert len(reply.manifest.sources) == 1

    discover = worker.handle_frame(Frame(MessageType.MESSAGE_TYPE_DISCOVER, 8, b""))
    assert discover is not None
    disc = worker_pb2.DiscoverReply()
    disc.ParseFromString(discover.payload)
    assert disc.sources[0].source_id == "example.sine.main"

    schema_req = worker_pb2.GetConfigSchemaRequest(source_id="example.sine.main")
    schema_frame = worker.handle_frame(
        Frame(
            MessageType.MESSAGE_TYPE_GET_CONFIG_SCHEMA,
            9,
            schema_req.SerializeToString(),
        )
    )
    assert schema_frame is not None
    schema_reply = worker_pb2.GetConfigSchemaReply()
    schema_reply.ParseFromString(schema_frame.payload)
    assert json.loads(schema_reply.schema_json)["schema_revision"] == "example.sine/1"


def test_framed_hello_round_trip_bytes() -> None:
    worker = SineWorker(plugin_id="example.sine", worker_id="w")
    transport = MemoryTransport()
    worker._transport = transport  # noqa: SLF001

    hello = build_worker_hello(
        plugin_id=worker.plugin_id,
        plugin_version=worker.plugin_version,
        worker_id=worker.worker_id,
        supported_operations=worker.supported_operations,
    )
    raw = encode_frame(
        MessageType.MESSAGE_TYPE_HELLO, hello.SerializeToString(), correlation_id=0
    )
    frame, consumed = decode_frame(raw)
    assert consumed == len(raw)
    parsed = common_pb2.Hello()
    parsed.ParseFromString(frame.payload)
    ack = negotiate_hello(parsed, instance_id="x")
    assert ack.accepted
    transport.push_inbound(MessageType.MESSAGE_TYPE_HELLO_ACK, ack.SerializeToString())
    assert worker._handshake()  # noqa: SLF001


def test_preview_helper_builds_trace() -> None:
    frame = build_trace_preview(
        source_id="example.sine.main",
        stream_id="example.sine.main.batch",
        channel_names=["ch0", "ch1"],
        samples=[0.1, -0.2],
        points_per_channel=1,
        session_time_ns=123,
        sequence=1,
    )
    assert frame.source_id == "example.sine.main"
    assert frame.trace.channel_count == 2
    assert list(frame.trace.samples) == pytest.approx([0.1, -0.2])


def test_mcap_segment_writer(tmp_path: Path) -> None:
    writer = McapSegmentWriter(
        package_root=tmp_path,
        source_id="example.sine.main",
        stream_id="example.sine.main.batch",
        schema_name="capture.v1.data.NumericBatch",
        data_schema_id="generic.numeric_batch/1",
    )
    writer.open()
    writer.append(b"{}", log_time_ns=1)
    sealed = writer.close()
    assert sealed is not None
    assert sealed.absolute_path.is_file()
    assert sealed.actual_count >= 1
