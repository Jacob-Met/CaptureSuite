# SPDX-License-Identifier: GPL-3.0-only
"""Retained protocol errors must not retain a borrow of the input buffer."""

from __future__ import annotations

import struct
import traceback

import pytest
from capture_protocol.constants import FRAME_MAGIC, MAX_PAYLOAD_LEN
from capture_protocol.framing import Frame, FrameDecoder, FrameError, decode_frame, encode_frame


def invalid_header(kind: str) -> bytes:
    magic = 0 if kind == "magic" else FRAME_MAGIC
    size = 0 if kind == "magic" else MAX_PAYLOAD_LEN + 1
    return struct.pack("<IIII", magic, size, 1, 37)


@pytest.mark.parametrize("kind", ["magic", "length"])
def test_reset_inside_protocol_error_handler(kind: str) -> None:
    decoder = FrameDecoder()
    try:
        decoder.feed(invalid_header(kind))
    except FrameError:
        # The active traceback is still alive here. Reset is the documented
        # explicit recovery boundary, not a request to wait for garbage collection.
        decoder.reset()
        assert decoder.feed(encode_frame(2, b"fresh", 41)) == [Frame(2, 41, b"fresh")]
    else:
        pytest.fail("invalid complete header was accepted")


@pytest.mark.parametrize("kind", ["magic", "length"])
def test_saved_protocol_error_allows_reset_and_preserves_diagnostics(kind: str) -> None:
    decoder = FrameDecoder()
    retained: list[FrameError] = []
    try:
        decoder.feed(invalid_header(kind))
    except FrameError as error:
        retained.append(error)
    assert len(retained) == 1
    decoder.reset()
    assert decoder.feed(encode_frame(201, b"event", 0)) == [Frame(201, 0, b"event")]
    rendered = "".join(traceback.format_exception(retained[0]))
    assert "FrameError" in rendered
    assert ("bad magic" if kind == "magic" else "exceeds max") in rendered


@pytest.mark.parametrize(
    "wire",
    [
        b"CSP",
        encode_frame(1, b"partial", 1)[:-1],
        invalid_header("magic"),
        invalid_header("length"),
    ],
    ids=["partial-header", "partial-payload", "bad-magic", "oversized-length"],
)
def test_retained_decode_error_does_not_export_the_callers_bytearray(wire: bytes) -> None:
    buffer = bytearray(wire)
    retained: list[ValueError] = []
    try:
        decode_frame(buffer)
    except ValueError as error:
        retained.append(error)
    assert len(retained) == 1
    buffer.clear()
    buffer.extend(encode_frame(2, b"replacement", 4))
    frame, consumed = decode_frame(buffer)
    assert frame == Frame(2, 4, b"replacement")
    assert consumed == len(buffer)


@pytest.mark.parametrize("wire", [encode_frame(1, b"owned", 5), invalid_header("magic")])
def test_decoder_releases_only_its_own_memoryview(wire: bytes) -> None:
    buffer = bytearray(wire)
    caller_view = memoryview(buffer)
    retained: list[ValueError] = []
    try:
        decode_frame(caller_view)
    except ValueError as error:
        retained.append(error)
    # The caller still owns this view, including when the parser failed.
    assert caller_view.tobytes() == wire
    caller_view.release()
    buffer.clear()
    assert buffer == b""


def test_returned_payload_is_owned_after_input_buffer_changes() -> None:
    buffer = bytearray(encode_frame(7, b"original", 9))
    frame, consumed = decode_frame(buffer)
    assert consumed == len(buffer)
    buffer.clear()
    buffer.extend(b"unrelated")
    assert frame == Frame(7, 9, b"original")
