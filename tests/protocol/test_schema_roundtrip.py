# SPDX-License-Identifier: GPL-3.0-only
"""Protobuf message round-trips for core session/protocol types."""

from __future__ import annotations

from capture_protocol.generated.capture.v1 import (
    arrays_pb2,
    common_pb2,
    events_pb2,
    health_pb2,
    source_pb2,
    storage_pb2,
)
from capture_protocol.generated.capture.v1.data import emg_batch_pb2, imu_frame_pb2
from google.protobuf.json_format import MessageToDict, ParseDict


def _round_trip(msg) -> None:
    raw = msg.SerializeToString()
    clone = type(msg)()
    clone.ParseFromString(raw)
    assert clone.SerializeToString() == raw
    as_dict = MessageToDict(msg, preserving_proto_field_name=True)
    again = type(msg)()
    ParseDict(as_dict, again, ignore_unknown_fields=False)
    assert again.SerializeToString() == raw


def test_timing_header_round_trip() -> None:
    h = common_pb2.TimingHeader(
        sequence_number=10,
        device_index=10,
        device_timestamp=12345,
        device_timestamp_unit="ticks",
        host_arrival_ns=1000,
        session_time_ns=900,
        timestamp_uncertainty_ns=500_000,
        clock_mapping_id="map-1",
        quality_flags=common_pb2.QUALITY_FLAG_CLOCK_UNMAPPED,
    )
    _round_trip(h)


def test_checkpoint_preserves_original_and_effective() -> None:
    cp = events_pb2.Checkpoint(
        checkpoint_id="cp-1",
        original_timestamp_ns=1_000_000_000,
        effective_timestamp_ns=1_000_000_000,
        name="Baseline",
        created_via="hotkey",
    )
    _round_trip(cp)


def test_gap_event_taxonomy() -> None:
    gap = health_pb2.GapEvent(
        source_id="sim.radar.1",
        stream_id="sim.radar.1.frame",
        cause=health_pb2.GAP_CAUSE_DISCONNECT,
        start_session_time_ns=5_000_000_000,
        estimated_lost_count=30,
        closed=False,
    )
    _round_trip(gap)


def test_radar_array_software_coordinated_only_default() -> None:
    arr = arrays_pb2.RadarArray()
    arr.array.array_id = "lab_front"
    arr.array.name = "Lab_Front"
    arr.array.array_type = "radar"
    arr.array.timing_mode = arrays_pb2.TIMING_MODE_SOFTWARE_COORDINATED
    member = arr.array.members.add()
    member.source_id = "sim.radar.1"
    member.alias = "Radar_Front_Left"
    member.enabled = True
    _round_trip(arr)


def test_session_manifest_round_trip() -> None:
    m = storage_pb2.SessionManifest(
        session_schema_version="1.0.0",
        session_id="sess-1",
        state="preparing",
        t0_qpc_ticks=0,
        qpc_frequency=10_000_000,
        t0_wall_utc="2026-08-08T00:00:00Z",
        t0_uncertainty_ns=1000,
        app_version="0.1.0",
        daemon_version="0.1.0",
    )
    m.identity.session_id = "sess-1"
    m.identity.project.name = "Demo"
    m.source_ids.append("sim.emg.main")
    _round_trip(m)


def test_emg_batch_embeds_timing_header() -> None:
    batch = emg_batch_pb2.EmgBatch()
    batch.timing.sequence_number = 1
    batch.timing.session_time_ns = 0
    batch.first_sample_index = 0
    batch.sample_count = 4
    batch.channel_ids.extend(["ch1", "ch2"])
    batch.samples_f32_le = b"\x00" * 32
    _round_trip(batch)


def test_imu_frame_embeds_timing_header() -> None:
    frame = imu_frame_pb2.ImuFrame()
    frame.timing.sequence_number = 2
    frame.frame_index = 2
    sensor = frame.sensors.add()
    sensor.sensor_id = "pelvis"
    sensor.qw = 1.0
    _round_trip(frame)


def test_stream_descriptor_classes() -> None:
    for stream_class in (
        source_pb2.STREAM_CLASS_SAMPLED,
        source_pb2.STREAM_CLASS_FRAME,
        source_pb2.STREAM_CLASS_ARRAY_FRAME,
        source_pb2.STREAM_CLASS_STRUCTURED,
        source_pb2.STREAM_CLASS_EVENT,
        source_pb2.STREAM_CLASS_BLOB,
    ):
        s = source_pb2.StreamDescriptor(
            stream_id="x",
            source_id="y",
            stream_class=stream_class,
            data_schema_id="test/1",
            data_schema_version="1",
        )
        _round_trip(s)
