# SPDX-License-Identifier: GPL-3.0-only
"""CSP1 frame encode/decode tests."""

from __future__ import annotations

import pytest
from capture_protocol.constants import FRAME_MAGIC_BYTES, MAX_PAYLOAD_LEN
from capture_protocol.framing import FrameDecoder, FrameError, decode_frame, encode_frame


def test_round_trip_empty_payload() -> None:
    raw = encode_frame(1, b"", correlation_id=42)
    frame, consumed = decode_frame(raw)
    assert consumed == len(raw)
    assert frame.message_type == 1
    assert frame.correlation_id == 42
    assert frame.payload == b""
    assert not frame.is_event


def test_round_trip_payload() -> None:
    payload = b"hello-protocol"
    raw = encode_frame(201, payload, correlation_id=0)
    frame, _ = decode_frame(raw)
    assert frame.is_event
    assert frame.payload == payload
    assert raw[:4] == FRAME_MAGIC_BYTES


def test_bad_magic_raises() -> None:
    raw = encode_frame(1, b"x", 1)
    broken = b"XXXX" + raw[4:]
    with pytest.raises(FrameError, match="bad magic"):
        decode_frame(broken)


def test_oversized_payload_rejected_on_encode() -> None:
    with pytest.raises(FrameError):
        encode_frame(1, b"a" * (MAX_PAYLOAD_LEN + 1), 1)


def test_incomplete_buffer() -> None:
    raw = encode_frame(1, b"abcdef", 7)
    with pytest.raises(ValueError, match="incomplete"):
        decode_frame(raw[:8])
    with pytest.raises(ValueError, match="incomplete"):
        decode_frame(raw[:-1])


def test_incremental_decoder() -> None:
    a = encode_frame(1, b"one", 1)
    b = encode_frame(2, b"two", 2)
    dec = FrameDecoder()
    assert dec.feed(a[:6]) == []
    frames = dec.feed(a[6:] + b)
    assert len(frames) == 2
    assert frames[0].payload == b"one"
    assert frames[1].payload == b"two"
