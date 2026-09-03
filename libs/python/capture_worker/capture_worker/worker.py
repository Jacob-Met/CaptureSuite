# SPDX-License-Identifier: Apache-2.0
"""Worker base class: Hello → Identify → Discover → config → Start/Stop loop."""

from __future__ import annotations

import json
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from capture_protocol.constants import OP_ARM, OP_PREVIEW, PROTOCOL_MAJOR, PROTOCOL_MINOR
from capture_protocol.framing import Frame
from capture_protocol.generated.capture.v1 import (
    common_pb2,
    health_pb2,
    preview_pb2,
    source_pb2,
    worker_pb2,
)
from capture_protocol.generated.capture.v1.common_pb2 import MessageType
from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
from capture_protocol.handshake import build_worker_hello
from google.protobuf.message import Message

from capture_worker.preview import build_preview_descriptor
from capture_worker.transport import MemoryTransport, Transport, WorkerPipeTransport
from capture_worker.writer import McapSegmentWriter, SealedSegment


def session_time_ns() -> int:
    """Host wall-clock nanoseconds (session mapping applied by the daemon)."""
    return time.time_ns()


def _as_source_instance(
    item: source_pb2.SourceInstance | Mapping[str, Any],
) -> source_pb2.SourceInstance:
    if isinstance(item, source_pb2.SourceInstance):
        return item
    src = source_pb2.SourceInstance()
    # Mapping form used by lightweight plugins / tests.
    src.source_id = str(item.get("source_id", ""))
    src.source_type = str(item.get("source_type", ""))
    src.alias = str(item.get("alias", ""))
    src.plugin_id = str(item.get("plugin_id", ""))
    src.plugin_version = str(item.get("plugin_version", ""))
    src.enabled = bool(item.get("enabled", True))
    src.logical_role = str(item.get("logical_role", ""))
    if "lifecycle_state" in item:
        src.lifecycle_state = int(item["lifecycle_state"])
    else:
        src.lifecycle_state = source_pb2.SOURCE_LIFECYCLE_DISCOVERED
    for key, value in (item.get("metadata") or {}).items():
        src.metadata[str(key)] = str(value)
    for stream in item.get("streams") or []:
        if isinstance(stream, source_pb2.StreamDescriptor):
            src.streams.append(stream)
            continue
        sd = source_pb2.StreamDescriptor()
        sd.stream_id = str(stream.get("stream_id", ""))
        sd.source_id = str(stream.get("source_id", src.source_id))
        sd.stream_class = int(stream.get("stream_class", source_pb2.STREAM_CLASS_SAMPLED))
        sd.modality = str(stream.get("modality", "numeric"))
        sd.units = str(stream.get("units", "a.u."))
        sd.quantity = str(stream.get("quantity", ""))
        sd.nominal_rate_hz = float(stream.get("nominal_rate_hz", 0.0))
        sd.timestamp_source = int(
            stream.get("timestamp_source", source_pb2.TIMESTAMP_SOURCE_HOST_ARRIVAL)
        )
        sd.data_schema_id = str(stream.get("data_schema_id", "generic.numeric_batch/1"))
        sd.data_schema_version = str(stream.get("data_schema_version", "1"))
        src.streams.append(sd)
    for device in item.get("physical_devices") or []:
        if isinstance(device, source_pb2.PhysicalDevice):
            src.physical_devices.append(device)
            continue
        d = source_pb2.PhysicalDevice()
        d.vendor = str(device.get("vendor", ""))
        d.model = str(device.get("model", ""))
        d.serial = str(device.get("serial", ""))
        d.stable_device_key = str(device.get("stable_device_key", ""))
        src.physical_devices.append(d)
        if d.stable_device_key:
            src.physical_device_ids.append(d.stable_device_key)
    return src


class Worker(ABC):
    """Out-of-process acquisition worker.

    Subclasses implement :meth:`discover`, :meth:`config_schema`, :meth:`start`,
    and :meth:`stop`. While recording they call :meth:`emit_samples` and
    optionally :meth:`emit_preview`.
    """

    plugin_id: str = "unset.plugin"
    plugin_version: str = "0.1.0"
    supported_operations: int = OP_ARM | OP_PREVIEW

    def __init__(
        self,
        plugin_id: str | None = None,
        worker_id: str | None = None,
        transport: Transport | None = None,
    ) -> None:
        if plugin_id is not None:
            self.plugin_id = plugin_id
        self.worker_id = worker_id or self.plugin_id
        self._transport = transport
        self._write_lock = threading.Lock()
        self._preview_latest: bytes | None = None
        self._outbox: list[tuple[int, bytes]] = []
        self._running = False
        self._accepted = False
        self._configs: dict[str, dict[str, Any]] = {}
        self._writers: dict[str, McapSegmentWriter] = {}
        self._session_t0_qpc_ns: dict[str, int] = {}
        self._sample_seq: dict[str, int] = {}
        self._preview_seq: dict[str, int] = {}
        self._sources_cache: list[source_pb2.SourceInstance] = []
        self._running_sources: set[str] = set()

    # --- subclass API -----------------------------------------------------

    @abstractmethod
    def discover(self) -> list[source_pb2.SourceInstance] | list[Mapping[str, Any]]:
        """Return currently visible sources."""

    @abstractmethod
    def config_schema(self, source_id: str) -> dict[str, Any]:
        """JSON Schema (+ ``schema_revision``) for ``source_id``."""

    def start(self, source_id: str, start_req: worker_pb2.StartRequest) -> None:
        """Begin acquisition for ``source_id`` (may spawn threads)."""
        del source_id, start_req

    def stop(self, source_id: str) -> None:
        """Stop acquisition for ``source_id``."""
        del source_id

    def apply_config(
        self, source_id: str, document: dict[str, Any] | str
    ) -> dict[str, Any]:
        """Validate/store config; return effective document (default: echo)."""
        if isinstance(document, str):
            document = json.loads(document) if document else {}
        if not isinstance(document, dict):
            raise TypeError("configuration must be a JSON object")
        self._configs[source_id] = dict(document)
        return dict(document)

    def preview_descriptor(self, source_id: str) -> preview_pb2.PreviewDescriptor:
        src = self._find_source(source_id)
        stream_id = src.streams[0].stream_id if src and src.streams else ""
        channels = ["ch0", "ch1"]
        return build_preview_descriptor(
            source_id=source_id,
            stream_id=stream_id,
            available_channels=channels,
        )

    # --- emit helpers -----------------------------------------------------

    def emit_samples(
        self,
        source_id: str,
        samples: Sequence[float],
        *,
        channel_count: int,
        channel_names: Sequence[str] | None = None,
        device_time_ns: Sequence[int] | None = None,
        session_time_ns: int | None = None,
        stream_id: str | None = None,
        units: str = "a.u.",
        dtype: str = "f64",
    ) -> None:
        """Serialize a ``generic.numeric_batch/1`` and append to the open writer."""
        src = self._find_source(source_id)
        if stream_id is None:
            stream_id = src.streams[0].stream_id if src and src.streams else f"{source_id}.batch"
        names = list(channel_names) if channel_names is not None else [
            f"ch{i}" for i in range(channel_count)
        ]
        batch = numeric_batch_pb2.NumericBatch()
        batch.channel_count = channel_count
        batch.units = units
        batch.dtype = dtype
        batch.channel_names.extend(names)
        batch.samples.extend(float(x) for x in samples)
        if device_time_ns:
            batch.device_time_ns.extend(int(t) for t in device_time_ns)

        now_ns = time.time_ns()
        if session_time_ns is None:
            t0 = self._session_t0_qpc_ns.get(source_id, 0)
            session_time_ns = max(0, now_ns - t0) if t0 else now_ns

        writer = self._writers.get(source_id)
        if writer is not None:
            writer.append(batch.SerializeToString(), log_time_ns=int(session_time_ns))
        self._sample_seq[source_id] = self._sample_seq.get(source_id, 0) + 1

    def emit_preview(self, frame: preview_pb2.PreviewFrame | Message) -> None:
        """Queue a latest-wins preview frame for the main loop to flush."""
        payload = frame.SerializeToString()
        with self._write_lock:
            self._preview_latest = payload

    def emit_health(self, snapshot: health_pb2.HealthSnapshot) -> None:
        with self._write_lock:
            self._outbox.append(
                (MessageType.MESSAGE_TYPE_HEALTH_SNAPSHOT, snapshot.SerializeToString())
            )

    def get_config(self, source_id: str) -> dict[str, Any]:
        return dict(self._configs.get(source_id, {}))

    # --- run / handshake --------------------------------------------------

    def run(
        self,
        *,
        pipe_name: str | None = None,
        transport: Transport | None = None,
    ) -> int:
        """Connect, Hello, then serve RPCs until the pipe closes or Shutdown."""
        if transport is not None:
            self._transport = transport
        elif pipe_name:
            pipe = WorkerPipeTransport(pipe_name)
            pipe.connect()
            self._transport = pipe
        if self._transport is None:
            raise RuntimeError("run() requires pipe_name or transport")

        try:
            if not self._handshake():
                return 1
            self._running = True
            while self._running:
                self._flush_outbox()
                frame = self._transport.poll_frame()
                if frame is None:
                    time.sleep(0.002)
                    continue
                if not self._dispatch(frame):
                    break
            return 0
        finally:
            self._running = False
            try:
                self._transport.close()
            except OSError:
                pass

    def handle_frame(self, frame: Frame) -> Frame | None:
        """Handle one request and return the reply frame (for unit tests)."""
        reply_type, payload, corr = self._handle(frame)
        if reply_type is None:
            return None
        return Frame(reply_type, corr, payload)

    def _handshake(self) -> bool:
        assert self._transport is not None
        hello = build_worker_hello(
            plugin_id=self.plugin_id,
            plugin_version=self.plugin_version,
            worker_id=self.worker_id,
            supported_operations=self.supported_operations,
            max_daemon_minor=999,
        )
        hello.protocol.major = PROTOCOL_MAJOR
        hello.protocol.minor = PROTOCOL_MINOR
        self._send(MessageType.MESSAGE_TYPE_HELLO, hello.SerializeToString(), 0)
        ack_frame = self._transport.read_frame(30.0)
        if ack_frame is None or ack_frame.message_type != MessageType.MESSAGE_TYPE_HELLO_ACK:
            return False
        ack = common_pb2.HelloAck()
        ack.ParseFromString(ack_frame.payload)
        self._accepted = bool(ack.accepted)
        return self._accepted

    def _dispatch(self, frame: Frame) -> bool:
        reply_type, payload, corr = self._handle(frame)
        if reply_type == MessageType.MESSAGE_TYPE_SHUTDOWN_REPLY:
            self._send(reply_type, payload, corr)
            return False
        if reply_type is not None:
            self._send(reply_type, payload, corr)
        return True

    def _handle(self, frame: Frame) -> tuple[int | None, bytes, int]:
        corr = frame.correlation_id
        t = frame.message_type

        if t == MessageType.MESSAGE_TYPE_IDENTIFY:
            reply = worker_pb2.IdentifyReply()
            reply.manifest.CopyFrom(self._build_manifest())
            return MessageType.MESSAGE_TYPE_IDENTIFY_REPLY, reply.SerializeToString(), corr

        if t == MessageType.MESSAGE_TYPE_DISCOVER:
            reply = worker_pb2.DiscoverReply()
            reply.sources.extend(self._refresh_sources())
            return MessageType.MESSAGE_TYPE_DISCOVER_REPLY, reply.SerializeToString(), corr

        if t == MessageType.MESSAGE_TYPE_CONNECT:
            req = worker_pb2.ConnectRequest()
            req.ParseFromString(frame.payload)
            reply = worker_pb2.ConnectReply()
            src = self._find_source(req.source_id)
            if src is None:
                reply.error.code = "NOT_FOUND"
                reply.error.message = f"unknown source {req.source_id}"
            else:
                reply.source.CopyFrom(src)
            return MessageType.MESSAGE_TYPE_CONNECT_REPLY, reply.SerializeToString(), corr

        if t == MessageType.MESSAGE_TYPE_GET_CONFIG_SCHEMA:
            req = worker_pb2.GetConfigSchemaRequest()
            req.ParseFromString(frame.payload)
            reply = worker_pb2.GetConfigSchemaReply()
            try:
                schema = self.config_schema(req.source_id)
                reply.schema_json = json.dumps(schema)
                reply.schema_revision = str(schema.get("schema_revision", ""))
                current = self.get_config(req.source_id)
                reply.current_json = json.dumps(current)
                reply.effective_json = reply.current_json
            except Exception as exc:  # noqa: BLE001 — surface to daemon
                reply.error.code = "SCHEMA_ERROR"
                reply.error.message = str(exc)
            return (
                MessageType.MESSAGE_TYPE_GET_CONFIG_SCHEMA_REPLY,
                reply.SerializeToString(),
                corr,
            )

        if t == MessageType.MESSAGE_TYPE_APPLY_CONFIG:
            req = worker_pb2.ApplyConfigRequest()
            req.ParseFromString(frame.payload)
            reply = worker_pb2.ApplyConfigReply()
            try:
                raw = req.configuration.decode("utf-8") if req.configuration else "{}"
                document = json.loads(raw) if raw else {}
                if not isinstance(document, dict):
                    raise ValueError("configuration must be a JSON object")
                effective = self.apply_config(req.source_id, document)
                reply.requested_json = json.dumps(document)
                reply.effective_json = json.dumps(effective)
                schema = self.config_schema(req.source_id)
                reply.schema_revision = str(schema.get("schema_revision", ""))
                src = self._find_source(req.source_id)
                if src is not None:
                    reply.source.CopyFrom(src)
            except Exception as exc:  # noqa: BLE001
                reply.error.code = "APPLY_FAILED"
                reply.error.message = str(exc)
            return MessageType.MESSAGE_TYPE_APPLY_CONFIG_REPLY, reply.SerializeToString(), corr

        if t == MessageType.MESSAGE_TYPE_GET_PREVIEW_DESCRIPTOR:
            req = worker_pb2.GetPreviewDescriptorRequest()
            req.ParseFromString(frame.payload)
            reply = worker_pb2.GetPreviewDescriptorReply()
            try:
                reply.preview.CopyFrom(self.preview_descriptor(req.source_id))
            except Exception as exc:  # noqa: BLE001
                reply.error.code = "PREVIEW_ERROR"
                reply.error.message = str(exc)
            return (
                MessageType.MESSAGE_TYPE_GET_PREVIEW_DESCRIPTOR_REPLY,
                reply.SerializeToString(),
                corr,
            )

        if t == MessageType.MESSAGE_TYPE_GET_STREAM_DESCRIPTORS:
            req = worker_pb2.GetStreamDescriptorsRequest()
            req.ParseFromString(frame.payload)
            reply = worker_pb2.GetStreamDescriptorsReply()
            src = self._find_source(req.source_id)
            if src is None:
                reply.error.code = "NOT_FOUND"
                reply.error.message = f"unknown source {req.source_id}"
            else:
                reply.streams.extend(src.streams)
            return (
                MessageType.MESSAGE_TYPE_GET_STREAM_DESCRIPTORS_REPLY,
                reply.SerializeToString(),
                corr,
            )

        if t == MessageType.MESSAGE_TYPE_START:
            req = worker_pb2.StartRequest()
            req.ParseFromString(frame.payload)
            reply = worker_pb2.StartReply()
            try:
                self._prepare_writer(req)
                self._running_sources.add(req.source_id)
                self.start(req.source_id, req)
                reply.first_datum_session_time_ns = 0
            except Exception as exc:  # noqa: BLE001
                self._running_sources.discard(req.source_id)
                reply.error.code = "START_FAILED"
                reply.error.message = str(exc)
            return MessageType.MESSAGE_TYPE_START_REPLY, reply.SerializeToString(), corr

        if t == MessageType.MESSAGE_TYPE_STOP:
            req = worker_pb2.StopRequest()
            req.ParseFromString(frame.payload)
            reply = worker_pb2.StopReply()
            try:
                self._running_sources.discard(req.source_id)
                self.stop(req.source_id)
                self._seal_writer(req.source_id)
            except Exception as exc:  # noqa: BLE001
                reply.error.code = "STOP_FAILED"
                reply.error.message = str(exc)
            self._flush_outbox()
            return MessageType.MESSAGE_TYPE_STOP_REPLY, reply.SerializeToString(), corr

        if t == MessageType.MESSAGE_TYPE_SHUTDOWN:
            for source_id in list(self._writers):
                try:
                    self.stop(source_id)
                except Exception:  # noqa: BLE001
                    pass
                self._seal_writer(source_id)
            reply = worker_pb2.ShutdownReply()
            self._running = False
            return MessageType.MESSAGE_TYPE_SHUTDOWN_REPLY, reply.SerializeToString(), corr

        if t == MessageType.MESSAGE_TYPE_SEGMENT_SEALED_ACK:
            return None, b"", corr

        return None, b"", corr

    def _build_manifest(self) -> source_pb2.SourceManifest:
        manifest = source_pb2.SourceManifest()
        manifest.plugin_id = self.plugin_id
        manifest.plugin_version = self.plugin_version
        manifest.component.major = 0
        manifest.component.minor = 1
        manifest.component.patch = 0
        manifest.supported_operations = self.supported_operations
        manifest.capabilities["isolation"] = "shared"
        manifest.capabilities["families"] = "numeric"
        manifest.capabilities["hardware"] = "0"
        manifest.sources.extend(self._refresh_sources())
        return manifest

    def _refresh_sources(self) -> list[source_pb2.SourceInstance]:
        raw = self.discover()
        sources = [_as_source_instance(item) for item in raw]
        for src in sources:
            if not src.plugin_id:
                src.plugin_id = self.plugin_id
            if not src.plugin_version:
                src.plugin_version = self.plugin_version
        self._sources_cache = sources
        return sources

    def _find_source(self, source_id: str) -> source_pb2.SourceInstance | None:
        for src in self._sources_cache:
            if src.source_id == source_id:
                return src
        for src in self._refresh_sources():
            if src.source_id == source_id:
                return src
        return None

    def _prepare_writer(self, req: worker_pb2.StartRequest) -> None:
        self._session_t0_qpc_ns[req.source_id] = int(req.session_t0_qpc_ns)
        package = req.session_package_path
        if not package:
            return
        src = self._find_source(req.source_id)
        stream_id = src.streams[0].stream_id if src and src.streams else f"{req.source_id}.batch"
        schema_id = (
            src.streams[0].data_schema_id
            if src and src.streams
            else "generic.numeric_batch/1"
        )

        def on_sealed(sealed: SealedSegment) -> None:
            msg = worker_pb2.SegmentSealed()
            msg.source_id = sealed.source_id
            msg.stream_id = sealed.stream_id
            msg.path = sealed.path
            msg.size_bytes = sealed.size_bytes
            msg.hash_blake3_hex = sealed.hash_blake3_hex
            msg.start_session_time_ns = sealed.start_session_time_ns
            msg.end_session_time_ns = sealed.end_session_time_ns
            msg.actual_count = sealed.actual_count
            msg.segment_index = sealed.segment_index
            with self._write_lock:
                self._outbox.append(
                    (MessageType.MESSAGE_TYPE_SEGMENT_SEALED, msg.SerializeToString())
                )

        writer = McapSegmentWriter(
            package_root=Path(package),
            source_id=req.source_id,
            stream_id=stream_id,
            schema_name="capture.v1.data.NumericBatch",
            data_schema_id=schema_id,
            on_sealed=on_sealed,
        )
        writer.open()
        self._writers[req.source_id] = writer

    def _seal_writer(self, source_id: str) -> None:
        writer = self._writers.pop(source_id, None)
        if writer is not None:
            writer.close()

    def _send(self, message_type: int, payload: bytes, correlation_id: int) -> None:
        assert self._transport is not None
        with self._write_lock:
            self._transport.write_frame(message_type, payload, correlation_id)

    def _flush_outbox(self) -> None:
        assert self._transport is not None
        with self._write_lock:
            pending = self._outbox
            self._outbox = []
            preview = self._preview_latest
            self._preview_latest = None
        for message_type, payload in pending:
            self._transport.write_frame(message_type, payload, 0)
        if preview is not None:
            self._transport.write_frame(MessageType.MESSAGE_TYPE_PREVIEW_FRAME, preview, 0)


def next_preview_sequence(worker: Worker, source_id: str) -> int:
    """Increment and return the per-source preview sequence counter."""
    seq = worker._preview_seq.get(source_id, 0) + 1  # noqa: SLF001
    worker._preview_seq[source_id] = seq  # noqa: SLF001
    return seq


def run_handshake_for_tests(
    worker: Worker,
    *,
    instance_id: str = "test-daemon",
) -> tuple[common_pb2.Hello, common_pb2.HelloAck]:
    """Drive Hello → HelloAck against a :class:`MemoryTransport` (unit tests)."""
    from capture_protocol.handshake import negotiate_hello

    transport = MemoryTransport()
    worker._transport = transport  # noqa: SLF001 — test helper
    hello = build_worker_hello(
        plugin_id=worker.plugin_id,
        plugin_version=worker.plugin_version,
        worker_id=worker.worker_id,
        supported_operations=worker.supported_operations,
    )
    transport.push_inbound(
        MessageType.MESSAGE_TYPE_HELLO_ACK,
        negotiate_hello(hello, instance_id=instance_id).SerializeToString(),
    )
    assert worker._handshake()  # noqa: SLF001
    assert transport.outbound
    msg_type, _corr, payload = transport.outbound[0]
    assert msg_type == MessageType.MESSAGE_TYPE_HELLO
    parsed = common_pb2.Hello()
    parsed.ParseFromString(payload)
    ack = common_pb2.HelloAck()
    # Re-negotiate for the return value (same outcome as pushed ack).
    ack.CopyFrom(negotiate_hello(parsed, instance_id=instance_id))
    return parsed, ack
