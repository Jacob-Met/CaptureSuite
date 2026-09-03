# SPDX-License-Identifier: GPL-3.0-only
"""Simulated worker that advertises camera/EMG/IMU/radar (+ custom) sources.

Milestone 1 exit: advertise arbitrary source/stream types over the handshake.
No acquisition yet — that is Milestone 2.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from capture_protocol.codec import parse_payload, serialize_message
from capture_protocol.constants import (
    OP_ARM,
    OP_PREVIEW,
    OP_RECOVER,
    PROTOCOL_MAJOR,
    PROTOCOL_MINOR,
)
from capture_protocol.framing import Frame, encode_frame
from capture_protocol.generated.capture.v1 import (
    common_pb2,
    preview_pb2,
    source_pb2,
    worker_pb2,
)
from capture_protocol.generated.capture.v1.common_pb2 import MessageType
from capture_protocol.handshake import build_worker_hello, negotiate_hello


def _device(
    vendor: str,
    model: str,
    serial: str,
    firmware: str = "sim-1.0",
) -> source_pb2.PhysicalDevice:
    d = source_pb2.PhysicalDevice()
    d.vendor = vendor
    d.model = model
    d.serial = serial
    d.stable_device_key = f"{vendor}:{model}:{serial}"
    d.firmware = firmware
    d.driver_sdk_version = "simulator/0.1"
    d.connection_path = f"sim://{serial}"
    return d


def _stream(
    stream_id: str,
    source_id: str,
    stream_class: source_pb2.StreamClass,
    modality: str,
    data_schema_id: str,
    rate_hz: float,
    *,
    sensor_id: str = "",
    units: str = "",
    quantity: str = "",
) -> source_pb2.StreamDescriptor:
    s = source_pb2.StreamDescriptor()
    s.stream_id = stream_id
    s.source_id = source_id
    s.sensor_id = sensor_id
    s.stream_class = stream_class
    s.modality = modality
    s.quantity = quantity
    s.units = units
    s.nominal_rate_hz = rate_hz
    s.timestamp_source = source_pb2.TIMESTAMP_SOURCE_SESSION_MAPPED
    s.data_schema_id = data_schema_id
    s.data_schema_version = "1"
    return s


def build_simulator_manifest(
    *,
    include_custom: bool = True,
    radar_count: int = 2,
) -> source_pb2.SourceManifest:
    """Build a SourceManifest with the four V1 families (+ optional custom)."""
    manifest = source_pb2.SourceManifest()
    manifest.plugin_id = "sim.multimodal"
    manifest.plugin_version = "0.1.0"
    manifest.component.major = 0
    manifest.component.minor = 1
    manifest.component.patch = 0
    manifest.supported_operations = OP_ARM | OP_PREVIEW | OP_RECOVER
    manifest.capabilities["families"] = "camera,emg,imu,radar,custom"
    manifest.capabilities["multi_radar"] = str(radar_count)

    # Camera
    cam = source_pb2.SourceInstance()
    cam.source_id = "sim.camera.sagittal"
    cam.source_type = "sim.camera"
    cam.alias = "Camera_Sagittal"
    cam.logical_role = "sagittal"
    cam.enabled = True
    cam.plugin_id = manifest.plugin_id
    cam.plugin_version = manifest.plugin_version
    cam.lifecycle_state = source_pb2.SOURCE_LIFECYCLE_DISCOVERED
    cam.physical_devices.append(
        _device("CaptureSuite Sim", "Virtual1080p", "CAM-001")
    )
    cam.physical_device_ids.append(cam.physical_devices[0].stable_device_key)
    cam.streams.append(
        _stream(
            "sim.camera.sagittal.video",
            cam.source_id,
            source_pb2.STREAM_CLASS_FRAME,
            "video",
            "video.segment_index/1",
            60.0,
            quantity="frame",
        )
    )
    manifest.sources.append(cam)

    # EMG
    emg = source_pb2.SourceInstance()
    emg.source_id = "sim.emg.main"
    emg.source_type = "sim.emg"
    emg.alias = "Sim_EMG_Main"
    emg.logical_role = "emg_main"
    emg.enabled = True
    emg.plugin_id = manifest.plugin_id
    emg.plugin_version = manifest.plugin_version
    emg.lifecycle_state = source_pb2.SOURCE_LIFECYCLE_DISCOVERED
    emg.physical_devices.append(
        _device("CaptureSuite Sim", "EmgArraySim", "TRIG-SIM-01")
    )
    emg.physical_device_ids.append(emg.physical_devices[0].stable_device_key)
    emg_names = [
        "L_Biceps",
        "R_Biceps",
        "L_Triceps",
        "R_Triceps",
        "L_Tibialis",
        "R_Tibialis",
        "L_Gastroc",
        "R_Gastroc",
    ]
    for i, name in enumerate(emg_names):
        sensor = source_pb2.SensorInstance()
        sensor.sensor_id = f"sim.emg.ch{i+1}"
        sensor.parent_source_id = emg.source_id
        sensor.alias = name
        sensor.logical_slot_id = f"slot.emg.{i+1}"
        sensor.physical.CopyFrom(
            _device("CaptureSuite Sim", "EmgSensorSim", f"S-{2000+i}")
        )
        emg.sensors.append(sensor)
    emg.streams.append(
        _stream(
            "sim.emg.main.batch",
            emg.source_id,
            source_pb2.STREAM_CLASS_SAMPLED,
            "emg",
            "emg.batch/1",
            2000.0,
            units="mV",
            quantity="voltage",
        )
    )
    manifest.sources.append(emg)

    # IMU
    imu = source_pb2.SourceInstance()
    imu.source_id = "sim.imu.upper"
    imu.source_type = "sim.imu"
    imu.alias = "Sim_IMU_UpperBody"
    imu.logical_role = "upper_body"
    imu.enabled = True
    imu.plugin_id = manifest.plugin_id
    imu.plugin_version = manifest.plugin_version
    imu.lifecycle_state = source_pb2.SOURCE_LIFECYCLE_DISCOVERED
    imu.physical_devices.append(
        _device("CaptureSuite Sim", "ImuHubSim", "XS-SIM-01")
    )
    imu.physical_device_ids.append(imu.physical_devices[0].stable_device_key)
    for i, name in enumerate(
        ["Pelvis", "Sternum", "R_UpperArm", "R_Forearm", "L_UpperArm", "L_Forearm", "Head"]
    ):
        sensor = source_pb2.SensorInstance()
        sensor.sensor_id = f"sim.imu.s{i+1}"
        sensor.parent_source_id = imu.source_id
        sensor.alias = name
        sensor.logical_slot_id = f"slot.imu.{name.lower()}"
        sensor.physical.CopyFrom(
            _device("CaptureSuite Sim", "ImuSensorSim", f"MTW-{100+i}")
        )
        imu.sensors.append(sensor)
    imu.streams.append(
        _stream(
            "sim.imu.upper.frame",
            imu.source_id,
            source_pb2.STREAM_CLASS_STRUCTURED,
            "imu",
            "imu.frame/1",
            100.0,
            quantity="inertial",
        )
    )
    manifest.sources.append(imu)

    # Multi-radar
    for idx in range(radar_count):
        rad = source_pb2.SourceInstance()
        rad.source_id = f"sim.radar.{idx+1}"
        rad.source_type = "sim.radar"
        side = ["Front_Left", "Front_Right", "Rear_Left", "Rear_Right"][idx % 4]
        rad.alias = f"Radar_{side}"
        rad.logical_role = f"radar_{side.lower()}"
        rad.enabled = True
        rad.plugin_id = manifest.plugin_id
        rad.plugin_version = manifest.plugin_version
        rad.lifecycle_state = source_pb2.SOURCE_LIFECYCLE_DISCOVERED
        rad.physical_devices.append(
            _device("CaptureSuite Sim", "RadarFmcwSim", f"BGT-SIM-{idx+1:04d}")
        )
        rad.physical_device_ids.append(rad.physical_devices[0].stable_device_key)
        rad.metadata["array_id"] = "sim.radar_array.lab_front"
        rad.streams.append(
            _stream(
                f"sim.radar.{idx+1}.frame",
                rad.source_id,
                source_pb2.STREAM_CLASS_ARRAY_FRAME,
                "radar",
                "radar.frame/1",
                30.0,
                quantity="radar_frame",
            )
        )
        manifest.sources.append(rad)

    if include_custom:
        custom = source_pb2.SourceInstance()
        custom.source_id = "sim.custom.forceplate"
        custom.source_type = "sim.forceplate"
        custom.alias = "ForcePlate_A"
        custom.logical_role = "force_plate"
        custom.enabled = True
        custom.plugin_id = manifest.plugin_id
        custom.plugin_version = manifest.plugin_version
        custom.lifecycle_state = source_pb2.SOURCE_LIFECYCLE_DISCOVERED
        custom.physical_devices.append(
            _device("CaptureSuite Sim", "ForcePlate", "FP-001")
        )
        custom.physical_device_ids.append(custom.physical_devices[0].stable_device_key)
        custom.streams.append(
            _stream(
                "sim.custom.forceplate.samples",
                custom.source_id,
                source_pb2.STREAM_CLASS_SAMPLED,
                "force",
                "generic.numeric_batch/1",
                1000.0,
                units="N",
                quantity="force",
            )
        )
        custom.metadata["note"] = "arbitrary modality — proves plugin-generic core"
        manifest.sources.append(custom)

    return manifest


@dataclass
class SimAdvertiseWorker:
    """In-process worker endpoint for handshake + Identify/Discover."""

    worker_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    instance_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    manifest: source_pb2.SourceManifest = field(default_factory=build_simulator_manifest)
    _handshaken: bool = False
    _accepted: bool = False

    def hello_frame(self, correlation_id: int = 1) -> bytes:
        hello = build_worker_hello(
            plugin_id=self.manifest.plugin_id,
            plugin_version=self.manifest.plugin_version,
            worker_id=self.worker_id,
            supported_operations=self.manifest.supported_operations,
        )
        payload = serialize_message(MessageType.MESSAGE_TYPE_HELLO, hello)
        return encode_frame(MessageType.MESSAGE_TYPE_HELLO, payload, correlation_id)

    def accept_as_daemon(self, hello_payload: bytes) -> common_pb2.HelloAck:
        hello = common_pb2.Hello()
        hello.ParseFromString(hello_payload)
        ack = negotiate_hello(hello, instance_id=self.instance_id)
        self._handshaken = True
        self._accepted = ack.accepted
        return ack

    def handle(self, frame: Frame) -> Frame | None:
        """Handle one inbound framed request; return reply frame or None."""
        if frame.message_type == MessageType.MESSAGE_TYPE_HELLO:
            hello = parse_payload(frame.message_type, frame.payload)
            assert isinstance(hello, common_pb2.Hello)
            # Worker receives HelloAck from daemon; if we are acting as daemon peer:
            return None

        if not self._handshaken and frame.message_type != MessageType.MESSAGE_TYPE_HELLO:
            # Still allow Identify after local mark — tests call mark_handshaken
            pass

        if frame.message_type == MessageType.MESSAGE_TYPE_IDENTIFY:
            reply = worker_pb2.IdentifyReply()
            reply.manifest.CopyFrom(self.manifest)
            return Frame(
                MessageType.MESSAGE_TYPE_IDENTIFY_REPLY,
                frame.correlation_id,
                serialize_message(MessageType.MESSAGE_TYPE_IDENTIFY_REPLY, reply),
            )

        if frame.message_type == MessageType.MESSAGE_TYPE_DISCOVER:
            reply = worker_pb2.DiscoverReply()
            reply.sources.extend(self.manifest.sources)
            return Frame(
                MessageType.MESSAGE_TYPE_DISCOVER_REPLY,
                frame.correlation_id,
                serialize_message(MessageType.MESSAGE_TYPE_DISCOVER_REPLY, reply),
            )

        if frame.message_type == MessageType.MESSAGE_TYPE_GET_STREAM_DESCRIPTORS:
            req = parse_payload(frame.message_type, frame.payload)
            assert isinstance(req, worker_pb2.GetStreamDescriptorsRequest)
            reply = worker_pb2.GetStreamDescriptorsReply()
            for src in self.manifest.sources:
                if src.source_id == req.source_id:
                    reply.streams.extend(src.streams)
                    break
            else:
                reply.error.code = "NOT_FOUND"
                reply.error.message = f"unknown source {req.source_id}"
            return Frame(
                MessageType.MESSAGE_TYPE_GET_STREAM_DESCRIPTORS_REPLY,
                frame.correlation_id,
                serialize_message(
                    MessageType.MESSAGE_TYPE_GET_STREAM_DESCRIPTORS_REPLY, reply
                ),
            )

        if frame.message_type == MessageType.MESSAGE_TYPE_GET_PREVIEW_DESCRIPTOR:
            req = parse_payload(frame.message_type, frame.payload)
            assert isinstance(req, worker_pb2.GetPreviewDescriptorRequest)
            reply = worker_pb2.GetPreviewDescriptorReply()
            src = next((s for s in self.manifest.sources if s.source_id == req.source_id), None)
            if src is None:
                reply.error.code = "NOT_FOUND"
                reply.error.message = f"unknown source {req.source_id}"
            else:
                preview = preview_pb2.PreviewDescriptor()
                preview.source_id = src.source_id
                preview.ring_slot_count = 3
                preview.drop_policy = preview_pb2.PREVIEW_DROP_POLICY_LATEST_WINS
                preview.shm_key = f"capturesuite.preview.{src.source_id}"
                if src.source_type == "sim.camera":
                    preview.kind = preview_pb2.PREVIEW_KIND_IMAGE_THUMBNAIL
                    preview.max_payload_bytes = 256 * 1024
                    preview.max_rate_hz = 15.0
                elif src.source_type == "sim.emg":
                    preview.kind = preview_pb2.PREVIEW_KIND_TRACE_BLOCK
                    preview.max_payload_bytes = 32 * 1024
                    preview.max_rate_hz = 20.0
                elif src.source_type == "sim.imu":
                    preview.kind = preview_pb2.PREVIEW_KIND_TRACE_SINGLE
                    preview.max_payload_bytes = 4 * 1024
                    preview.max_rate_hz = 20.0
                    preview.selected_channel = 0
                elif src.source_type == "sim.radar":
                    preview.kind = preview_pb2.PREVIEW_KIND_VECTOR_PROFILE
                    preview.max_payload_bytes = 1024
                    preview.max_rate_hz = 15.0
                else:
                    preview.kind = preview_pb2.PREVIEW_KIND_SCALAR_SERIES
                    preview.max_payload_bytes = 512
                    preview.max_rate_hz = 10.0
                reply.preview.CopyFrom(preview)
            return Frame(
                MessageType.MESSAGE_TYPE_GET_PREVIEW_DESCRIPTOR_REPLY,
                frame.correlation_id,
                serialize_message(
                    MessageType.MESSAGE_TYPE_GET_PREVIEW_DESCRIPTOR_REPLY, reply
                ),
            )

        return None

    def mark_handshaken(self, accepted: bool = True) -> None:
        self._handshaken = True
        self._accepted = accepted


def run_daemon_worker_handshake(
    worker: SimAdvertiseWorker,
) -> tuple[common_pb2.Hello, common_pb2.HelloAck]:
    """Helper: worker Hello → daemon negotiate → Ack."""
    frame_bytes = worker.hello_frame(correlation_id=1)
    from capture_protocol.framing import decode_frame

    frame, _ = decode_frame(frame_bytes)
    hello = parse_payload(frame.message_type, frame.payload)
    assert isinstance(hello, common_pb2.Hello)
    ack = negotiate_hello(
        hello,
        daemon_major=PROTOCOL_MAJOR,
        daemon_minor=PROTOCOL_MINOR,
        instance_id=worker.instance_id,
    )
    worker.mark_handshaken(ack.accepted)
    return hello, ack
