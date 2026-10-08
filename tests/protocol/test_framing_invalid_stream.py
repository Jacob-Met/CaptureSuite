# SPDX-License-Identifier: GPL-3.0-only
"""Invalid stream headers must not be mistaken for incomplete reads."""

from __future__ import annotations

import struct

import pytest
from capture_protocol.constants import FRAME_MAGIC, MAX_PAYLOAD_LEN
from capture_protocol.framing import FrameDecoder, FrameError, decode_frame


@pytest.mark.parametrize(
    ("magic", "payload_len", "error"),
    [
        (0, 0, "bad magic"),
        (FRAME_MAGIC, MAX_PAYLOAD_LEN + 1, "exceeds max"),
    ],
    ids=["bad-magic", "oversized-payload"],
)
def test_incremental_decoder_rejects_invalid_complete_header(
    magic: int, payload_len: int, error: str
) -> None:
    # No body is needed: invalid framing must be rejected as soon as the
    # header completes, rather than buffered indefinitely waiting for a body.
    header = struct.pack("<IIII", magic, payload_len, 1, 42)
    with pytest.raises(FrameError, match=error):
        decode_frame(header)

    decoder = FrameDecoder()
    assert decoder.feed(header[:-1]) == []
    with pytest.raises(FrameError, match=error):
        decoder.feed(header[-1:])
