# SPDX-License-Identifier: GPL-3.0-only
"""Qt bridge over ControlClient — RPCs off the UI thread, events as signals."""

from __future__ import annotations

import queue
import threading
import uuid
from collections.abc import Callable
from typing import Any

from capture_protocol.control_client import (
    ControlClient,
    ControlClientError,
    parse_disk_status,
    parse_health_snapshot,
    parse_preview_frame,
    read_instance_file,
)
from capture_protocol.generated.capture.v1 import health_pb2
from capture_protocol.generated.capture.v1.common_pb2 import MessageType
from PySide6.QtCore import QObject, QTimer, Signal


class DaemonLink(QObject):
    """Owns a ControlClient and surfaces push + RPC results to the UI thread."""

    connected = Signal(str)  # instance_id
    disconnected = Signal(str)  # reason
    error = Signal(str)
    sources_listed = Signal(object)
    session_created = Signal(object)
    sources_selected = Signal(object)
    session_view = Signal(object)
    preview_frame = Signal(object)
    health_snapshot = Signal(object)
    disk_status = Signal(object)
    alert = Signal(object)
    gap_event = Signal(object)
    preflight_done = Signal(object)
    checkpoint_created = Signal(object)
    rpc_done = Signal(str, object)  # tag, result_or_exception

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client: ControlClient | None = None
        # ControlClient already multiplexes RPCs by correlation id; do not
        # serialize here or a slow Apply/Rescan stalls every other click and
        # the 500 ms session-view poll.
        self._inflight = 0
        self._inflight_lock = threading.Lock()
        self._results: queue.Queue[tuple[str, object]] = queue.Queue()
        self._events: queue.Queue[tuple[int, bytes]] = queue.Queue(maxsize=512)

        self._pump = QTimer(self)
        self._pump.setInterval(16)
        self._pump.timeout.connect(self._pump_queues)
        self._pump.start()

        self._view_timer = QTimer(self)
        self._view_timer.setInterval(500)
        self._view_timer.timeout.connect(self.refresh_session_view)

    @property
    def client(self) -> ControlClient | None:
        return self._client

    def is_connected(self) -> bool:
        return self._client is not None

    def daemon_available(self) -> bool:
        try:
            read_instance_file()
            return True
        except (ControlClientError, KeyError, OSError):
            return False

    def start(self) -> None:
        self._run_rpc("connect", self._do_connect)

    def stop(self) -> None:
        self._view_timer.stop()
        client = self._client
        self._client = None
        if client is not None:
            try:
                client.close()
            except OSError:
                pass
        self.disconnected.emit("closed")

    def _do_connect(self) -> str:
        client = ControlClient()
        ack = client.connect()
        client.on_event(self._on_event)
        self._client = client
        return ack.instance_id

    def _on_event(self, message_type: int, payload: bytes) -> None:
        # Control I/O thread — never touch Qt objects here.
        try:
            self._events.put_nowait((message_type, payload))
        except queue.Full:
            try:
                self._events.get_nowait()
            except queue.Empty:
                pass
            try:
                self._events.put_nowait((message_type, payload))
            except queue.Full:
                pass

    def _pump_queues(self) -> None:
        while True:
            try:
                tag, result = self._results.get_nowait()
            except queue.Empty:
                break
            self.rpc_done.emit(tag, result)

        while True:
            try:
                message_type, payload = self._events.get_nowait()
            except queue.Empty:
                break
            try:
                if message_type == int(MessageType.MESSAGE_TYPE_PREVIEW_FRAME):
                    self.preview_frame.emit(parse_preview_frame(payload))
                elif message_type == int(MessageType.MESSAGE_TYPE_HEALTH_SNAPSHOT):
                    self.health_snapshot.emit(parse_health_snapshot(payload))
                elif message_type == int(MessageType.MESSAGE_TYPE_DISK_STATUS):
                    self.disk_status.emit(parse_disk_status(payload))
                elif message_type == int(MessageType.MESSAGE_TYPE_ALERT):
                    msg = health_pb2.Alert()
                    msg.ParseFromString(payload)
                    self.alert.emit(msg)
                elif message_type == int(MessageType.MESSAGE_TYPE_GAP_EVENT):
                    msg = health_pb2.GapEvent()
                    msg.ParseFromString(payload)
                    self.gap_event.emit(msg)
            except Exception:  # noqa: BLE001
                pass

    def _run_rpc(self, tag: str, fn: Callable[[], Any]) -> None:
        heavy = tag != "get_session_view"

        def work() -> None:
            if heavy:
                with self._inflight_lock:
                    self._inflight += 1
            try:
                result = fn()
                self._results.put((tag, result))
            except Exception as exc:  # noqa: BLE001
                self._results.put((tag, exc))
            finally:
                if heavy:
                    with self._inflight_lock:
                        self._inflight = max(0, self._inflight - 1)

        threading.Thread(target=work, name=f"rpc-{tag}", daemon=True).start()

    def _require(self) -> ControlClient:
        if self._client is None:
            raise ControlClientError("not connected")
        return self._client

    def list_sources(self) -> None:
        self._run_rpc("list_sources", lambda: self._require().list_sources())

    def rescan_sources(self) -> None:
        self._run_rpc("rescan_sources", lambda: self._require().rescan_sources())

    def create_session(self, session_id: str | None = None) -> None:
        sid = session_id or f"ui-{uuid.uuid4().hex[:12]}"

        def work() -> Any:
            return self._require().create_session(sid)

        self._run_rpc("create_session", work)

    def open_session(self, package_path: str) -> None:
        self._run_rpc(
            "open_session", lambda: self._require().open_session(package_path)
        )

    def select_sources(self, source_ids: list[str]) -> None:
        self._run_rpc(
            "select_sources", lambda: self._require().select_sources(source_ids)
        )

    def subscribe_status(self, *, preview_rate_limit_hz: float = 15.0) -> None:
        self._run_rpc(
            "subscribe_status",
            lambda: self._require().subscribe_status(
                include_preview=True,
                health_interval_ms=1000,
                preview_rate_limit_hz=preview_rate_limit_hz,
            ),
        )

    def refresh_session_view(self) -> None:
        if self._client is None:
            return
        # Skip polls while a user-facing RPC is in flight so we do not pile up
        # behind Apply/Rescan/Start and delay their replies.
        with self._inflight_lock:
            busy = self._inflight > 0
        if busy:
            return
        self._run_rpc("get_session_view", lambda: self._require().get_session_view())

    def start_selected(self) -> None:
        self._run_rpc("start_selected", lambda: self._require().start_selected())

    def start_all_ready(self) -> None:
        self._run_rpc("start_all_ready", lambda: self._require().start_all_ready())

    def acknowledge_alert(self, alert_id: str) -> None:
        self._run_rpc(
            "acknowledge_alert",
            lambda: self._require().acknowledge_alert(alert_id),
        )

    def stop_rehearsal(self) -> None:
        self._run_rpc("stop_rehearsal", lambda: self._require().stop_rehearsal())

    def get_config_schema(self, source_id: str) -> None:
        self._run_rpc(
            "get_config_schema",
            lambda: self._require().get_config_schema(source_id),
        )

    def apply_config(self, source_id: str, configuration: dict) -> None:
        self._run_rpc(
            "apply_config",
            lambda: self._require().apply_config(source_id, configuration),
        )

    def start_rehearsal(self, source_ids: list[str] | None = None) -> None:
        self._run_rpc(
            "start_rehearsal", lambda: self._require().start_rehearsal(source_ids)
        )

    def run_preflight(self, source_ids: list[str] | None = None) -> None:
        self._run_rpc(
            "run_preflight", lambda: self._require().run_preflight(source_ids)
        )

    def create_checkpoint(self, name: str = "", created_via: str = "ui") -> None:
        self._run_rpc(
            "create_checkpoint",
            lambda: self._require().create_checkpoint(name, created_via=created_via),
        )

    def update_checkpoint(self, checkpoint_id: str, name: str) -> None:
        self._run_rpc(
            "update_checkpoint",
            lambda: self._require().update_checkpoint(checkpoint_id, name=name),
        )

    def annotate(self, text: str) -> None:
        self._run_rpc("annotate", lambda: self._require().annotate(text))

    def add_sync_anchor(self, mechanism: str = "ui") -> None:
        self._run_rpc(
            "add_sync_anchor",
            lambda: self._require().add_sync_anchor(mechanism),
        )

    def stop_recording(self) -> None:
        def work() -> Any:
            client = self._require()
            token_reply = client.request_stop()
            if token_reply.error.code:
                raise ControlClientError(
                    f"{token_reply.error.code}: {token_reply.error.message}"
                )
            return client.stop_session(token_reply.confirmation_token)

        self._run_rpc("stop_session", work)

    def handle_rpc_done(self, tag: str, result: object) -> None:
        if isinstance(result, Exception):
            self.error.emit(f"{tag}: {result}")
            if tag == "connect":
                self.disconnected.emit(str(result))
            return

        if tag == "connect":
            self.connected.emit(str(result))
            self._view_timer.start()
        elif tag == "list_sources":
            self.sources_listed.emit(result)
        elif tag == "rescan_sources":
            self.sources_listed.emit(result)
        elif tag == "create_session":
            self.session_created.emit(result)
        elif tag == "select_sources":
            self.sources_selected.emit(result)
        elif tag == "get_session_view":
            self.session_view.emit(result)
        elif tag == "run_preflight":
            self.preflight_done.emit(result)
        elif tag == "create_checkpoint":
            self.checkpoint_created.emit(result)
