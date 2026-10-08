# SPDX-License-Identifier: GPL-3.0-only
"""Wire framing must be independent of read boundaries and preserve valid input."""

from __future__ import annotations

import struct

import pytest
from capture_protocol.constants import FRAME_HEADER_SIZE, FRAME_MAGIC, MAX_PAYLOAD_LEN
from capture_protocol.framing import Frame, FrameDecoder, FrameError, encode_frame


@pytest.mark.parametrize(
    ("magic", "payload_len", "error"),
    [(0, 0, "bad magic"), (FRAME_MAGIC, MAX_PAYLOAD_LEN + 1, "exceeds max")],
    ids=["bad-magic", "oversized-payload"],
)
def test_invalid_header_rejection_at_every_read_boundary(
    magic: int, payload_len: int, error: str
) -> None:
    header = struct.pack("<IIII", magic, payload_len, 2, 17)
    for split in range(FRAME_HEADER_SIZE):
        decoder = FrameDecoder()
        assert decoder.feed(header[:split]) == []
        with pytest.raises(FrameError, match=error):
            decoder.feed(header[split:])


def test_valid_stream_at_every_read_boundary() -> None:
    expected = [Frame(1, 7, b""), Frame(201, 0, b"event"), Frame(2, 8, b"reply")]
    wire = b"".join(encode_frame(f.message_type, f.payload, f.correlation_id) for f in expected)
    for split in range(len(wire) + 1):
        decoder = FrameDecoder()
        received = decoder.feed(wire[:split]) + decoder.feed(wire[split:])
        assert received == expected
        assert decoder.feed(b"") == []


def test_partial_payload_then_complete_and_partial_next_header() -> None:
    first = encode_frame(1, b"payload", 1)
    second = encode_frame(2, b"next", 2)
    decoder = FrameDecoder()
    assert decoder.feed(first[:-1]) == []
    assert decoder.feed(b"") == []
    assert decoder.feed(first[-1:] + second[:5]) == [Frame(1, 1, b"payload")]
    assert decoder.feed(second[5:]) == [Frame(2, 2, b"next")]
    assert decoder.feed(b"") == []


@pytest.mark.parametrize("payload_len", [0, MAX_PAYLOAD_LEN + 1])
def test_valid_prefix_does_not_mask_invalid_next_header(payload_len: int) -> None:
    magic = 0 if payload_len == 0 else FRAME_MAGIC
    broken = struct.pack("<IIII", magic, payload_len, 2, 9)
    decoder = FrameDecoder()
    assert decoder.feed(encode_frame(1, b"valid", 8) + broken[:7]) == [Frame(1, 8, b"valid")]
    with pytest.raises(FrameError):
        decoder.feed(broken[7:])


def test_invalid_frame_is_not_skipped_to_find_later_valid_data() -> None:
    decoder = FrameDecoder()
    broken = struct.pack("<IIII", 0, 0, 2, 9)
    with pytest.raises(FrameError, match="bad magic"):
        decoder.feed(broken + encode_frame(1, b"later", 10))
    # No automatic resynchronization after corruption; an explicit reset is required.
    with pytest.raises(FrameError, match="bad magic"):
        decoder.feed(b"")
    decoder.reset()
    assert decoder.feed(encode_frame(1, b"new stream", 11)) == [Frame(1, 11, b"new stream")]


def test_maximum_legal_payload_header_is_incomplete_without_body() -> None:
    decoder = FrameDecoder()
    header = struct.pack("<IIII", FRAME_MAGIC, MAX_PAYLOAD_LEN, 1, 1)
    assert decoder.feed(header) == []
    assert decoder.feed(b"partial") == []
    decoder.reset()
    assert decoder.feed(encode_frame(1, b"replacement", 2)) == [Frame(1, 2, b"replacement")]
