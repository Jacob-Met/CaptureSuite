# SPDX-License-Identifier: Apache-2.0
"""CaptureSuite wire protocol helpers and generated protobuf bindings."""

from capture_protocol.constants import PROTOCOL_MAJOR, PROTOCOL_MINOR
from capture_protocol.framing import Frame, FrameError, decode_frame, encode_frame
from capture_protocol.handshake import (
    HandshakeError,
    build_daemon_hello_ack,
    build_ui_hello,
    build_worker_hello,
    negotiate_hello,
)

__all__ = [
    "PROTOCOL_MAJOR",
    "PROTOCOL_MINOR",
    "Frame",
    "FrameError",
    "encode_frame",
    "decode_frame",
    "HandshakeError",
    "build_worker_hello",
    "build_ui_hello",
    "build_daemon_hello_ack",
    "negotiate_hello",
]

__version__ = "0.1.0"
