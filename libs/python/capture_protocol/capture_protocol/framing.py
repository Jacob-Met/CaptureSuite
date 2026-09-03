# SPDX-License-Identifier: Apache-2.0
"""CSP1 length-prefixed protobuf framing."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from capture_protocol.constants import (
    FRAME_HEADER_SIZE,
    FRAME_MAGIC,
    FRAME_MAGIC_BYTES,
    MAX_PAYLOAD_LEN,
)

_HEADER_STRUCT = struct.Struct("<IIII")  # magic, payload_len, message_type, correlation_id


class FrameError(ValueError):
    """Invalid frame on the wire."""


@dataclass(frozen=True, slots=True)
class Frame:
    message_type: int
    correlation_id: int
    payload: bytes

    @property
    def is_event(self) -> bool:
        return self.correlation_id == 0


def encode_frame(message_type: int, payload: bytes, correlation_id: int = 0) -> bytes:
    if len(payload) > MAX_PAYLOAD_LEN:
        raise FrameError(f"payload_len {len(payload)} exceeds max {MAX_PAYLOAD_LEN}")
    header = _HEADER_STRUCT.pack(FRAME_MAGIC, len(payload), message_type, correlation_id)
    return header + payload


def decode_frame(buffer: bytes | bytearray | memoryview) -> tuple[Frame, int]:
    """Decode one frame from the start of buffer.

    Returns (frame, bytes_consumed).
    Raises FrameError on bad magic or oversized length.
    Raises ValueError if buffer is incomplete (need more data).
    """
    view = memoryview(buffer)
    if len(view) < FRAME_HEADER_SIZE:
        raise ValueError("incomplete header")
    magic, payload_len, message_type, correlation_id = _HEADER_STRUCT.unpack_from(view, 0)
    if magic != FRAME_MAGIC:
        # Helpful diagnostic: show what we got
        got = bytes(view[:4])
        raise FrameError(f"bad magic: expected {FRAME_MAGIC_BYTES!r}, got {got!r}")
    if payload_len > MAX_PAYLOAD_LEN:
        raise FrameError(f"payload_len {payload_len} exceeds max {MAX_PAYLOAD_LEN}")
    total = FRAME_HEADER_SIZE + payload_len
    if len(view) < total:
        raise ValueError("incomplete payload")
    payload = bytes(view[FRAME_HEADER_SIZE:total])
    return Frame(message_type, correlation_id, payload), total


class FrameDecoder:
    """Incremental byte-stream decoder for named-pipe / socket reads."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[Frame]:
        self._buf.extend(data)
        frames: list[Frame] = []
        while True:
            try:
                frame, consumed = decode_frame(self._buf)
            except ValueError:
                break
            frames.append(frame)
            del self._buf[:consumed]
        return frames

    def reset(self) -> None:
        self._buf.clear()
