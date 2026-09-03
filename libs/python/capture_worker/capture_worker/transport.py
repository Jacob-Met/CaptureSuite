# SPDX-License-Identifier: Apache-2.0
"""Worker-side named-pipe transport (client half).

The daemon creates the pipe and is the server; the worker connects with
``os.open`` / ``open(..., \"r+b\")`` the same way C++ workers and
``capture_protocol.control_client`` do. Framing is CSP1 via
``capture_protocol.framing``.
"""

from __future__ import annotations

import ctypes
import msvcrt
import time
from ctypes import wintypes
from typing import Any, Protocol

from capture_protocol.framing import Frame, FrameDecoder, encode_frame

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


class Transport(Protocol):
    """Minimal framed duplex used by :class:`capture_worker.worker.Worker`."""

    def write_frame(
        self, message_type: int, payload: bytes, correlation_id: int = 0
    ) -> None: ...

    def poll_frame(self) -> Frame | None: ...

    def read_frame(self, timeout_s: float) -> Frame | None: ...

    def close(self) -> None: ...


class WorkerPipeTransport:
    """Connect to a daemon-created worker pipe and exchange CSP1 frames."""

    def __init__(self, pipe_name: str, *, timeout_s: float = 5.0) -> None:
        self.pipe_name = pipe_name
        self.timeout_s = timeout_s
        self._fh: Any = None
        self._fd: int | None = None
        self._decoder = FrameDecoder()
        self._pending: list[Frame] = []

    def connect(self) -> None:
        deadline = time.monotonic() + self.timeout_s
        last_err: Exception | None = None
        while time.monotonic() < deadline:
            try:
                self._fh = open(self.pipe_name, "r+b", buffering=0)  # noqa: SIM115
                self._fd = self._fh.fileno()
                return
            except OSError as exc:
                last_err = exc
                time.sleep(0.02)
        raise OSError(f"failed to connect to worker pipe {self.pipe_name}: {last_err}")

    def close(self) -> None:
        self._fd = None
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None

    def write_frame(
        self, message_type: int, payload: bytes, correlation_id: int = 0
    ) -> None:
        if self._fh is None:
            raise OSError("pipe not connected")
        raw = encode_frame(message_type, payload, correlation_id)
        self._fh.write(raw)
        self._fh.flush()

    def poll_frame(self) -> Frame | None:
        """Non-blocking: return one decoded frame if bytes are available."""
        if self._pending:
            return self._pending.pop(0)
        if self._fd is None or self._fh is None:
            return None
        try:
            available = _peek_available(self._fd)
        except OSError:
            return None
        if available <= 0:
            return None
        chunk = self._fh.read(min(available, 64 * 1024))
        if not chunk:
            return None
        frames = self._decoder.feed(chunk)
        if not frames:
            return None
        self._pending.extend(frames[1:])
        return frames[0]

    def read_frame(self, timeout_s: float) -> Frame | None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            frame = self.poll_frame()
            if frame is not None:
                return frame
            time.sleep(0.002)
        return None


# Back-compat alias used by earlier drafts / external notes.
PipeTransport = WorkerPipeTransport


class MemoryTransport:
    """In-memory duplex for unit tests (no Windows pipe required)."""

    def __init__(self) -> None:
        self.outbound: list[tuple[int, int, bytes]] = []
        self._inbound: list[Frame] = []
        self.closed = False

    def push_inbound(
        self, message_type: int, payload: bytes, correlation_id: int = 0
    ) -> None:
        self._inbound.append(Frame(message_type, correlation_id, payload))

    def write_frame(
        self, message_type: int, payload: bytes, correlation_id: int = 0
    ) -> None:
        if self.closed:
            raise OSError("transport closed")
        self.outbound.append((message_type, correlation_id, payload))

    def poll_frame(self) -> Frame | None:
        if not self._inbound:
            return None
        return self._inbound.pop(0)

    def read_frame(self, timeout_s: float) -> Frame | None:  # noqa: ARG002
        return self.poll_frame()

    def close(self) -> None:
        self.closed = True
