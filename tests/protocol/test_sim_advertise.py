# SPDX-License-Identifier: GPL-3.0-only
"""Milestone 1 exit: simulated worker advertises arbitrary source/stream types."""

from __future__ import annotations

from capture_protocol.codec import parse_payload, serialize_message
from capture_protocol.framing import decode_frame
from capture_protocol.generated.capture.v1 import source_pb2, worker_pb2
from capture_protocol.generated.capture.v1.common_pb2 import MessageType
from capture_sim.advertise import (
    SimAdvertiseWorker,
    build_simulator_manifest,
    run_daemon_worker_handshake,
)


def test_manifest_includes_four_v1_families_and_custom() -> None:
    manifest = build_simulator_manifest(radar_count=4, include_custom=True)
    types = {s.source_type for s in manifest.sources}
    assert "sim.camera" in types
    assert "sim.emg" in types
    assert "sim.imu" in types
    assert "sim.radar" in types
    assert "sim.forceplate" in types
    radars = [s for s in manifest.sources if s.source_type == "sim.radar"]
    assert len(radars) == 4
    assert all(s.physical_devices[0].stable_device_key for s in manifest.sources)


def test_streams_carry_versioned_data_schema_ids() -> None:
    manifest = build_simulator_manifest()
    schema_ids = {
        stream.data_schema_id
        for src in manifest.sources
        for stream in src.streams
    }
    assert "emg.batch/1" in schema_ids
    assert "imu.frame/1" in schema_ids
    assert "radar.frame/1" in schema_ids
    assert "video.segment_index/1" in schema_ids


def test_custom_force_uses_generic_numeric_batch() -> None:
    manifest = build_simulator_manifest(include_custom=True)
    force = next(s for s in manifest.sources if s.source_type == "sim.forceplate")
    assert force.streams[0].data_schema_id == "generic.numeric_batch/1"


def test_hardware_identity_not_replaced_by_alias() -> None:
    manifest = build_simulator_manifest()
    emg = next(s for s in manifest.sources if s.source_type == "sim.emg")
    assert emg.alias == "Sim_EMG_Main"
    assert emg.physical_devices[0].vendor == "CaptureSuite Sim"
    assert emg.physical_devices[0].serial == "TRIG-SIM-01"
    assert "Sim_EMG_Main" not in emg.physical_devices[0].stable_device_key
    imu = next(s for s in manifest.sources if s.source_type == "sim.imu")
    assert imu.alias == "Sim_IMU_UpperBody"
    assert imu.physical_devices[0].vendor == "CaptureSuite Sim"


def test_handshake_then_identify_advertise() -> None:
    worker = SimAdvertiseWorker()
    hello, ack = run_daemon_worker_handshake(worker)
    assert hello.plugin_id == "sim.multimodal"
    assert ack.accepted

    from capture_protocol.framing import Frame

    req = worker_pb2.IdentifyRequest()
    reply = worker.handle(
        Frame(
            MessageType.MESSAGE_TYPE_IDENTIFY,
            9,
            serialize_message(MessageType.MESSAGE_TYPE_IDENTIFY, req),
        )
    )
    assert reply is not None
    assert reply.message_type == MessageType.MESSAGE_TYPE_IDENTIFY_REPLY
    identify = parse_payload(reply.message_type, reply.payload)
    assert isinstance(identify, worker_pb2.IdentifyReply)
    assert len(identify.manifest.sources) >= 5
    modalities = {st.modality for s in identify.manifest.sources for st in s.streams}
    assert {"video", "emg", "imu", "radar", "force"} <= modalities


def test_discover_and_stream_descriptors() -> None:
    worker = SimAdvertiseWorker()
    worker.mark_handshaken()
    from capture_protocol.framing import Frame

    discover = worker.handle(
        Frame(
            MessageType.MESSAGE_TYPE_DISCOVER,
            2,
            serialize_message(
                MessageType.MESSAGE_TYPE_DISCOVER, worker_pb2.DiscoverRequest()
            ),
        )
    )
    assert discover is not None
    disc = parse_payload(discover.message_type, discover.payload)
    assert isinstance(disc, worker_pb2.DiscoverReply)
    assert len(disc.sources) == len(worker.manifest.sources)

    emg_id = next(s.source_id for s in disc.sources if s.source_type == "sim.emg")
    req = worker_pb2.GetStreamDescriptorsRequest(source_id=emg_id)
    streams_frame = worker.handle(
        Frame(
            MessageType.MESSAGE_TYPE_GET_STREAM_DESCRIPTORS,
            3,
            serialize_message(MessageType.MESSAGE_TYPE_GET_STREAM_DESCRIPTORS, req),
        )
    )
    assert streams_frame is not None
    streams = parse_payload(streams_frame.message_type, streams_frame.payload)
    assert isinstance(streams, worker_pb2.GetStreamDescriptorsReply)
    assert streams.streams[0].stream_class == source_pb2.STREAM_CLASS_SAMPLED
    assert streams.streams[0].data_schema_id == "emg.batch/1"


def test_preview_descriptor_kinds_match_ui_contract() -> None:
    worker = SimAdvertiseWorker()
    worker.mark_handshaken()
    from capture_protocol.framing import Frame
    from capture_protocol.generated.capture.v1 import preview_pb2

    expected = {
        "sim.camera": preview_pb2.PREVIEW_KIND_IMAGE_THUMBNAIL,
        "sim.emg": preview_pb2.PREVIEW_KIND_TRACE_BLOCK,
        "sim.imu": preview_pb2.PREVIEW_KIND_TRACE_SINGLE,
        "sim.radar": preview_pb2.PREVIEW_KIND_VECTOR_PROFILE,
    }
    for src in worker.manifest.sources:
        if src.source_type not in expected:
            continue
        req = worker_pb2.GetPreviewDescriptorRequest(source_id=src.source_id)
        reply = worker.handle(
            Frame(
                MessageType.MESSAGE_TYPE_GET_PREVIEW_DESCRIPTOR,
                4,
                serialize_message(MessageType.MESSAGE_TYPE_GET_PREVIEW_DESCRIPTOR, req),
            )
        )
        assert reply is not None
        msg = parse_payload(reply.message_type, reply.payload)
        assert msg.preview.kind == expected[src.source_type]
        assert msg.preview.ring_slot_count == 3


def test_hello_frame_bytes_round_trip() -> None:
    worker = SimAdvertiseWorker()
    raw = worker.hello_frame(correlation_id=1)
    frame, consumed = decode_frame(raw)
    assert consumed == len(raw)
    assert frame.message_type == MessageType.MESSAGE_TYPE_HELLO
    hello = parse_payload(frame.message_type, frame.payload)
    assert hello.role == "worker"
