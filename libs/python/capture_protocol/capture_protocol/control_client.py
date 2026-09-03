# SPDX-License-Identifier: Apache-2.0
"""Named-pipe control client for the capture daemon.

Supports request/reply RPCs and unsolicited status/preview frames via a
background I/O thread (needed once SubscribeStatus is active).

Windows synchronous named pipes cannot ReadFile+WriteFile concurrently on the
same handle, so all pipe I/O is serialized on one thread: outbound frames go
through a write queue, and inbound data is read only after PeekNamedPipe.
"""

from __future__ import annotations

import ctypes
import json
import msvcrt
import os
import queue
import threading
import time
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path
from typing import Any

from capture_protocol.framing import Frame, FrameDecoder, encode_frame
from capture_protocol.generated.capture.v1 import (
    common_pb2,
    control_pb2,
    health_pb2,
    preview_pb2,
)
from capture_protocol.generated.capture.v1.common_pb2 import MessageType
from capture_protocol.handshake import build_ui_hello

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.PeekNamedPipe.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
]
_kernel32.PeekNamedPipe.restype = wintypes.BOOL


def _peek_available(fd: int) -> int:
    handle = msvcrt.get_osfhandle(fd)
    avail = wintypes.DWORD(0)
    ok = _kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(avail), None)
    if not ok:
        raise OSError(ctypes.get_last_error(), "PeekNamedPipe failed")
    return int(avail.value)


class ControlClientError(RuntimeError):
    pass


EventHandler = Callable[[int, bytes], None]


def read_instance_file() -> dict[str, Any]:
    path = Path(os.environ["LOCALAPPDATA"]) / "CaptureSuite" / "instance.json"
    if not path.is_file():
        raise ControlClientError(f"daemon instance file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


class ControlClient:
    def __init__(self, pipe_name: str | None = None, *, timeout_s: float = 10.0) -> None:
        if pipe_name is None:
            pipe_name = str(read_instance_file()["control_pipe"])
        self.pipe_name = pipe_name
        self.timeout_s = timeout_s
        self._fh: Any = None
        self._fd: int | None = None
        self._decoder = FrameDecoder()
        self._corr = 1
        self.instance_id = ""
        self._lock = threading.Lock()
        self._pending: dict[int, queue.Queue[Frame]] = {}
        self._write_queue: queue.Queue[bytes] = queue.Queue()
        self._io_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._event_handlers: list[EventHandler] = []
        self._event_queue: queue.Queue[tuple[int, bytes]] = queue.Queue(maxsize=256)

    def on_event(self, handler: EventHandler) -> None:
        self._event_handlers.append(handler)

    def poll_event(self, timeout_s: float = 0.0) -> tuple[int, bytes] | None:
        try:
            return self._event_queue.get(timeout=timeout_s)
        except queue.Empty:
            return None

    def connect(self) -> common_pb2.HelloAck:
        deadline = time.time() + self.timeout_s
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                self._fh = open(self.pipe_name, "r+b", buffering=0)  # noqa: SIM115
                self._fd = self._fh.fileno()
                break
            except OSError as exc:
                last_err = exc
                time.sleep(0.05)
        if self._fh is None or self._fd is None:
            raise ControlClientError(f"failed to open pipe {self.pipe_name}: {last_err}")

        self._stop.clear()
        self._io_thread = threading.Thread(target=self._io_loop, name="control-io", daemon=True)
        self._io_thread.start()

        hello = build_ui_hello()
        ack_frame = self.request(MessageType.MESSAGE_TYPE_HELLO, hello)
        ack = common_pb2.HelloAck()
        ack.ParseFromString(ack_frame.payload)
        if not ack.accepted:
            raise ControlClientError(
                f"handshake rejected: {ack.error.code}: {ack.error.message}"
            )
        self.instance_id = ack.instance_id
        return ack

    def close(self) -> None:
        self._stop.set()
        # Wake the I/O loop if it is waiting on the write queue.
        try:
            self._write_queue.put_nowait(b"")
        except queue.Full:
            pass
        self._fd = None
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None
        if self._io_thread is not None:
            self._io_thread.join(timeout=2.0)
            self._io_thread = None

    def __enter__(self) -> ControlClient:
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _io_loop(self) -> None:
        """Serialize all pipe reads/writes on one thread (Windows duplex constraint)."""
        while not self._stop.is_set():
            fd = self._fd
            if fd is None:
                break

            # Drain outbound frames first so RPCs are never blocked behind a read.
            try:
                while True:
                    data = self._write_queue.get_nowait()
                    if not data:
                        continue
                    view = memoryview(data)
                    while view:
                        written = os.write(fd, view)
                        view = view[written:]
            except queue.Empty:
                pass
            except OSError:
                break

            try:
                avail = _peek_available(fd)
            except OSError:
                break
            if avail > 0:
                try:
                    chunk = os.read(fd, min(avail, 65536))
                except OSError:
                    break
                if not chunk:
                    break
                for frame in self._decoder.feed(chunk):
                    if frame.correlation_id == 0:
                        self._dispatch_event(frame)
                        continue
                    with self._lock:
                        q = self._pending.get(frame.correlation_id)
                    if q is not None:
                        q.put(frame)
            else:
                # Wait briefly for either inbound data or a new write.
                try:
                    data = self._write_queue.get(timeout=0.01)
                except queue.Empty:
                    continue
                if data:
                    try:
                        view = memoryview(data)
                        while view:
                            written = os.write(fd, view)
                            view = view[written:]
                    except OSError:
                        break

    def _dispatch_event(self, frame: Frame) -> None:
        for handler in list(self._event_handlers):
            try:
                handler(frame.message_type, frame.payload)
            except Exception:  # noqa: BLE001 — UI handlers must not kill reader
                pass
        try:
            self._event_queue.put_nowait((frame.message_type, frame.payload))
        except queue.Full:
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._event_queue.put_nowait((frame.message_type, frame.payload))
            except queue.Full:
                pass

    def request(self, message_type: int, msg: Any) -> Frame:
        if self._fd is None:
            raise ControlClientError("not connected")
        with self._lock:
            corr = self._corr
            self._corr += 1
            q: queue.Queue[Frame] = queue.Queue(maxsize=1)
            self._pending[corr] = q
        payload = msg.SerializeToString() if msg is not None else b""
        try:
            self._write_queue.put(encode_frame(int(message_type), payload, corr))
            return q.get(timeout=self.timeout_s)
        except queue.Empty as exc:
            raise ControlClientError("request timed out") from exc
        finally:
            with self._lock:
                self._pending.pop(corr, None)

    def _rpc(self, req_type: int, reply_type: int, req: Any, reply_cls: type) -> Any:
        frame = self.request(req_type, req)
        if frame.message_type != int(reply_type):
            raise ControlClientError(
                f"unexpected reply type {frame.message_type}, want {int(reply_type)}"
            )
        reply = reply_cls()
        reply.ParseFromString(frame.payload)
        return reply

    def list_sources(self) -> control_pb2.ListSourcesReply:
        return self._rpc(
            MessageType.MESSAGE_TYPE_LIST_SOURCES,
            MessageType.MESSAGE_TYPE_LIST_SOURCES_REPLY,
            control_pb2.ListSourcesRequest(),
            control_pb2.ListSourcesReply,
        )

    def rescan_sources(self) -> control_pb2.RescanSourcesReply:
        # Enumerate can take ~20s when USB boards are recovering.
        old = self.timeout_s
        self.timeout_s = max(old, 60.0)
        try:
            return self._rpc(
                MessageType.MESSAGE_TYPE_RESCAN_SOURCES,
                MessageType.MESSAGE_TYPE_RESCAN_SOURCES_REPLY,
                control_pb2.RescanSourcesRequest(),
                control_pb2.RescanSourcesReply,
            )
        finally:
            self.timeout_s = old

    def create_session(
        self, session_id: str, package_parent_path: str = ""
    ) -> control_pb2.CreateSessionReply:
        req = control_pb2.CreateSessionRequest()
        req.identity.session_id = session_id
        if package_parent_path:
            req.package_parent_path = package_parent_path
        return self._rpc(
            MessageType.MESSAGE_TYPE_CREATE_SESSION,
            MessageType.MESSAGE_TYPE_CREATE_SESSION_REPLY,
            req,
            control_pb2.CreateSessionReply,
        )

    def open_session(self, package_path: str) -> control_pb2.OpenSessionReply:
        req = control_pb2.OpenSessionRequest()
        req.package_path = package_path
        return self._rpc(
            MessageType.MESSAGE_TYPE_OPEN_SESSION,
            MessageType.MESSAGE_TYPE_OPEN_SESSION_REPLY,
            req,
            control_pb2.OpenSessionReply,
        )

    def select_sources(self, source_ids: list[str]) -> control_pb2.SelectSourcesReply:
        req = control_pb2.SelectSourcesRequest()
        req.source_ids.extend(source_ids)
        return self._rpc(
            MessageType.MESSAGE_TYPE_SELECT_SOURCES,
            MessageType.MESSAGE_TYPE_SELECT_SOURCES_REPLY,
            req,
            control_pb2.SelectSourcesReply,
        )

    def start_selected(self) -> control_pb2.StartSelectedReply:
        return self._rpc_long(
            MessageType.MESSAGE_TYPE_START_SELECTED,
            MessageType.MESSAGE_TYPE_START_SELECTED_REPLY,
            control_pb2.StartSelectedRequest(),
            control_pb2.StartSelectedReply,
            timeout_s=60.0,
        )

    def start_all_ready(self) -> control_pb2.StartAllReadyReply:
        return self._rpc_long(
            MessageType.MESSAGE_TYPE_START_ALL_READY,
            MessageType.MESSAGE_TYPE_START_ALL_READY_REPLY,
            control_pb2.StartAllReadyRequest(),
            control_pb2.StartAllReadyReply,
            timeout_s=60.0,
        )

    def acknowledge_alert(self, alert_id: str) -> control_pb2.AcknowledgeAlertReply:
        req = control_pb2.AcknowledgeAlertRequest()
        req.alert_id = alert_id
        return self._rpc(
            MessageType.MESSAGE_TYPE_ACKNOWLEDGE_ALERT,
            MessageType.MESSAGE_TYPE_ACKNOWLEDGE_ALERT_REPLY,
            req,
            control_pb2.AcknowledgeAlertReply,
        )

    def stop_rehearsal(self) -> control_pb2.StopRehearsalReply:
        return self._rpc(
            MessageType.MESSAGE_TYPE_STOP_REHEARSAL,
            MessageType.MESSAGE_TYPE_STOP_REHEARSAL_REPLY,
            control_pb2.StopRehearsalRequest(),
            control_pb2.StopRehearsalReply,
        )

    def request_stop(self) -> control_pb2.RequestStopReply:
        return self._rpc(
            MessageType.MESSAGE_TYPE_REQUEST_STOP,
            MessageType.MESSAGE_TYPE_REQUEST_STOP_REPLY,
            control_pb2.RequestStopRequest(),
            control_pb2.RequestStopReply,
        )

    def stop_session(self, token: str) -> control_pb2.StopSessionReply:
        req = control_pb2.StopSessionRequest()
        req.confirmation_token = token
        return self._rpc(
            MessageType.MESSAGE_TYPE_STOP_SESSION,
            MessageType.MESSAGE_TYPE_STOP_SESSION_REPLY,
            req,
            control_pb2.StopSessionReply,
        )

    def create_checkpoint(
        self, name: str = "", created_via: str = "ui"
    ) -> control_pb2.CreateCheckpointReply:
        req = control_pb2.CreateCheckpointRequest()
        req.name = name
        req.created_via = created_via
        return self._rpc(
            MessageType.MESSAGE_TYPE_CREATE_CHECKPOINT,
            MessageType.MESSAGE_TYPE_CREATE_CHECKPOINT_REPLY,
            req,
            control_pb2.CreateCheckpointReply,
        )

    def update_checkpoint(
        self, checkpoint_id: str, *, name: str | None = None, notes: str | None = None
    ) -> control_pb2.UpdateCheckpointReply:
        req = control_pb2.UpdateCheckpointRequest()
        req.checkpoint_id = checkpoint_id
        if name is not None:
            req.name = name
        if notes is not None:
            req.notes = notes
        return self._rpc(
            MessageType.MESSAGE_TYPE_UPDATE_CHECKPOINT,
            MessageType.MESSAGE_TYPE_UPDATE_CHECKPOINT_REPLY,
            req,
            control_pb2.UpdateCheckpointReply,
        )

    def annotate(self, text: str, created_via: str = "ui") -> control_pb2.AnnotateReply:
        req = control_pb2.AnnotateRequest()
        req.text = text
        req.created_via = created_via
        return self._rpc(
            MessageType.MESSAGE_TYPE_ANNOTATE,
            MessageType.MESSAGE_TYPE_ANNOTATE_REPLY,
            req,
            control_pb2.AnnotateReply,
        )

    def add_sync_anchor(
        self, mechanism: str, created_via: str = "ui"
    ) -> control_pb2.AddSyncAnchorReply:
        req = control_pb2.AddSyncAnchorRequest()
        req.mechanism = mechanism
        req.created_via = created_via
        return self._rpc(
            MessageType.MESSAGE_TYPE_ADD_SYNC_ANCHOR,
            MessageType.MESSAGE_TYPE_ADD_SYNC_ANCHOR_REPLY,
            req,
            control_pb2.AddSyncAnchorReply,
        )

    def get_recording_stats(self) -> control_pb2.GetRecordingStatsReply:
        return self._rpc(
            MessageType.MESSAGE_TYPE_GET_RECORDING_STATS,
            MessageType.MESSAGE_TYPE_GET_RECORDING_STATS_REPLY,
            control_pb2.GetRecordingStatsRequest(),
            control_pb2.GetRecordingStatsReply,
        )

    def inject_fault(
        self, source_id: str, fault_type: str, drop_count: int = 0
    ) -> control_pb2.InjectFaultReply:
        req = control_pb2.InjectFaultRequest()
        req.source_id = source_id
        req.fault_type = fault_type
        req.drop_count = drop_count
        return self._rpc(
            MessageType.MESSAGE_TYPE_INJECT_FAULT,
            MessageType.MESSAGE_TYPE_INJECT_FAULT_REPLY,
            req,
            control_pb2.InjectFaultReply,
        )

    def subscribe_status(
        self,
        *,
        include_preview: bool = True,
        health_interval_ms: int = 1000,
        preview_rate_limit_hz: float = 0.0,
    ) -> control_pb2.SubscribeStatusReply:
        req = control_pb2.SubscribeStatusRequest()
        req.include_preview = include_preview
        req.health_interval_ms = health_interval_ms
        req.preview_rate_limit_hz = preview_rate_limit_hz
        return self._rpc(
            MessageType.MESSAGE_TYPE_SUBSCRIBE_STATUS,
            MessageType.MESSAGE_TYPE_SUBSCRIBE_STATUS_REPLY,
            req,
            control_pb2.SubscribeStatusReply,
        )

    def _rpc_long(
        self, req_type: int, reply_type: int, req: Any, reply_cls: type,
        *, timeout_s: float = 45.0,
    ) -> Any:
        old = self.timeout_s
        self.timeout_s = max(old, timeout_s)
        try:
            return self._rpc(req_type, reply_type, req, reply_cls)
        finally:
            self.timeout_s = old

    def get_config_schema(self, source_id: str) -> Any:
        from capture_protocol.generated.capture.v1 import worker_pb2

        req = worker_pb2.GetConfigSchemaRequest()
        req.source_id = source_id
        # First schema fetch may cold-spawn a camera/radar worker.
        return self._rpc_long(
            MessageType.MESSAGE_TYPE_GET_CONFIG_SCHEMA,
            MessageType.MESSAGE_TYPE_GET_CONFIG_SCHEMA_REPLY,
            req,
            worker_pb2.GetConfigSchemaReply,
        )

    def apply_config(
        self, source_id: str, configuration: dict[str, Any] | str | bytes
    ) -> Any:
        import json

        from capture_protocol.generated.capture.v1 import worker_pb2

        if isinstance(configuration, dict):
            payload = json.dumps(configuration).encode("utf-8")
        elif isinstance(configuration, str):
            payload = configuration.encode("utf-8")
        else:
            payload = configuration
        req = worker_pb2.ApplyConfigRequest()
        req.source_id = source_id
        req.configuration = payload
        req.content_type = "application/json"
        return self._rpc_long(
            MessageType.MESSAGE_TYPE_APPLY_CONFIG,
            MessageType.MESSAGE_TYPE_APPLY_CONFIG_REPLY,
            req,
            worker_pb2.ApplyConfigReply,
        )

    def list_preview_descriptors(
        self, source_ids: list[str] | None = None
    ) -> control_pb2.ListPreviewDescriptorsReply:
        req = control_pb2.ListPreviewDescriptorsRequest()
        if source_ids:
            req.source_ids.extend(source_ids)
        return self._rpc(
            MessageType.MESSAGE_TYPE_LIST_PREVIEW_DESCRIPTORS,
            MessageType.MESSAGE_TYPE_LIST_PREVIEW_DESCRIPTORS_REPLY,
            req,
            control_pb2.ListPreviewDescriptorsReply,
        )

    def set_preview_config(
        self,
        source_id: str,
        *,
        enabled: bool | None = None,
        selected_channel: int | None = None,
    ) -> control_pb2.SetPreviewConfigReply:
        req = control_pb2.SetPreviewConfigRequest()
        req.source_id = source_id
        if enabled is not None:
            req.enabled = enabled
        if selected_channel is not None:
            req.selected_channel = selected_channel
        return self._rpc(
            MessageType.MESSAGE_TYPE_SET_PREVIEW_CONFIG,
            MessageType.MESSAGE_TYPE_SET_PREVIEW_CONFIG_REPLY,
            req,
            control_pb2.SetPreviewConfigReply,
        )

    def get_session_view(self) -> control_pb2.GetSessionViewReply:
        return self._rpc(
            MessageType.MESSAGE_TYPE_GET_SESSION_VIEW,
            MessageType.MESSAGE_TYPE_GET_SESSION_VIEW_REPLY,
            control_pb2.GetSessionViewRequest(),
            control_pb2.GetSessionViewReply,
        )

    def run_preflight(
        self, source_ids: list[str] | None = None
    ) -> control_pb2.RunPreflightReply:
        req = control_pb2.RunPreflightRequest()
        if source_ids:
            req.source_ids.extend(source_ids)
        return self._rpc(
            MessageType.MESSAGE_TYPE_RUN_PREFLIGHT,
            MessageType.MESSAGE_TYPE_RUN_PREFLIGHT_REPLY,
            req,
            control_pb2.RunPreflightReply,
        )

    def start_rehearsal(
        self, source_ids: list[str] | None = None
    ) -> control_pb2.StartRehearsalReply:
        req = control_pb2.StartRehearsalRequest()
        if source_ids:
            req.source_ids.extend(source_ids)
        return self._rpc_long(
            MessageType.MESSAGE_TYPE_START_REHEARSAL,
            MessageType.MESSAGE_TYPE_START_REHEARSAL_REPLY,
            req,
            control_pb2.StartRehearsalReply,
            timeout_s=60.0,
        )


def parse_preview_frame(payload: bytes) -> preview_pb2.PreviewFrame:
    msg = preview_pb2.PreviewFrame()
    msg.ParseFromString(payload)
    return msg


def parse_health_snapshot(payload: bytes) -> health_pb2.HealthSnapshot:
    msg = health_pb2.HealthSnapshot()
    msg.ParseFromString(payload)
    return msg


def parse_disk_status(payload: bytes) -> health_pb2.DiskStatus:
    msg = health_pb2.DiskStatus()
    msg.ParseFromString(payload)
    return msg
