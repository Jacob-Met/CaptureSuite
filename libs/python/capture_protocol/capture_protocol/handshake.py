# SPDX-License-Identifier: Apache-2.0
"""Hello / HelloAck negotiation per docs/design/PROTOCOL.md."""

from __future__ import annotations

from capture_protocol.constants import (
    PROTOCOL_MAJOR,
    PROTOCOL_MINOR,
)
from capture_protocol.generated.capture.v1 import common_pb2


class HandshakeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _version(major: int, minor: int, patch: int = 0, git: str = "") -> common_pb2.VersionInfo:
    info = common_pb2.VersionInfo()
    info.major = major
    info.minor = minor
    info.patch = patch
    info.git_describe = git
    return info


def build_worker_hello(
    *,
    plugin_id: str,
    plugin_version: str,
    worker_id: str,
    supported_operations: int,
    min_daemon_major: int = PROTOCOL_MAJOR,
    min_daemon_minor: int = 0,
    max_daemon_major: int = PROTOCOL_MAJOR,
    max_daemon_minor: int = 999,
    component_version: tuple[int, int, int] = (0, 1, 0),
) -> common_pb2.Hello:
    hello = common_pb2.Hello()
    hello.protocol.major = PROTOCOL_MAJOR
    hello.protocol.minor = PROTOCOL_MINOR
    hello.component.CopyFrom(_version(*component_version))
    hello.plugin_id = plugin_id
    hello.plugin_version = plugin_version
    hello.min_daemon_protocol.major = min_daemon_major
    hello.min_daemon_protocol.minor = min_daemon_minor
    hello.max_daemon_protocol.major = max_daemon_major
    hello.max_daemon_protocol.minor = max_daemon_minor
    hello.supported_operations = supported_operations
    hello.worker_id = worker_id
    hello.role = "worker"
    return hello


def build_ui_hello(
    component_version: tuple[int, int, int] = (0, 1, 0),
) -> common_pb2.Hello:
    hello = common_pb2.Hello()
    hello.protocol.major = PROTOCOL_MAJOR
    hello.protocol.minor = PROTOCOL_MINOR
    hello.component.CopyFrom(_version(*component_version))
    hello.role = "ui"
    return hello


def build_daemon_hello_ack(
    *,
    accepted: bool,
    instance_id: str,
    error: common_pb2.ErrorInfo | None = None,
    daemon_version: tuple[int, int, int] = (0, 1, 0),
    negotiated_minor: int = PROTOCOL_MINOR,
) -> common_pb2.HelloAck:
    ack = common_pb2.HelloAck()
    ack.accepted = accepted
    ack.negotiated.major = PROTOCOL_MAJOR
    ack.negotiated.minor = negotiated_minor
    ack.daemon.CopyFrom(_version(*daemon_version))
    ack.instance_id = instance_id
    if error is not None:
        ack.error.CopyFrom(error)
    return ack


def _protocol_in_range(
    daemon_major: int,
    daemon_minor: int,
    min_v: common_pb2.ProtocolVersion,
    max_v: common_pb2.ProtocolVersion,
) -> bool:
    def key(major: int, minor: int) -> tuple[int, int]:
        return (major, minor)

    return key(min_v.major, min_v.minor) <= key(daemon_major, daemon_minor) <= key(
        max_v.major, max_v.minor
    )


def negotiate_hello(
    hello: common_pb2.Hello,
    *,
    daemon_major: int = PROTOCOL_MAJOR,
    daemon_minor: int = PROTOCOL_MINOR,
    instance_id: str,
) -> common_pb2.HelloAck:
    """Daemon-side negotiation. Rejects incompatible peers before any device touch."""
    if hello.protocol.major != daemon_major:
        err = common_pb2.ErrorInfo(
            code="PROTOCOL_MISMATCH",
            message=(
                f"protocol major mismatch: peer={hello.protocol.major} "
                f"daemon={daemon_major}"
            ),
        )
        return build_daemon_hello_ack(accepted=False, instance_id=instance_id, error=err)

    if hello.role == "worker":
        if not hello.plugin_id:
            err = common_pb2.ErrorInfo(
                code="INVALID_HELLO",
                message="worker Hello must include plugin_id",
            )
            return build_daemon_hello_ack(accepted=False, instance_id=instance_id, error=err)
        if not _protocol_in_range(
            daemon_major,
            daemon_minor,
            hello.min_daemon_protocol,
            hello.max_daemon_protocol,
        ):
            err = common_pb2.ErrorInfo(
                code="PLUGIN_INCOMPATIBLE",
                message=(
                    f"daemon {daemon_major}.{daemon_minor} outside plugin range "
                    f"{hello.min_daemon_protocol.major}.{hello.min_daemon_protocol.minor}"
                    f"-{hello.max_daemon_protocol.major}.{hello.max_daemon_protocol.minor}"
                ),
            )
            return build_daemon_hello_ack(accepted=False, instance_id=instance_id, error=err)

    negotiated_minor = min(hello.protocol.minor, daemon_minor)
    return build_daemon_hello_ack(
        accepted=True,
        instance_id=instance_id,
        negotiated_minor=negotiated_minor,
    )
