# SPDX-License-Identifier: GPL-3.0-only
"""Chunked MCAP iteration helpers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any


def iter_mcap_messages(
    paths: tuple[Path, ...] | list[Path],
    *,
    schema_needle: str | None = None,
) -> Iterator[tuple[str, bytes, int]]:
    """Yield (schema_name, payload, log_time_ns) for matching messages."""
    try:
        from mcap.reader import make_reader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install mcap to decode analysis streams") from exc

    for path in paths:
        if not path.is_file():
            continue
        with path.open("rb") as fh:
            for schema, _channel, message in make_reader(fh).iter_messages():
                name = schema.name if schema else ""
                if schema_needle and schema_needle not in name:
                    continue
                log_time = int(getattr(message, "log_time", 0) or 0)
                yield name, message.data, log_time


def decode_protobuf(decoder_cls: Any, data: bytes) -> Any:
    msg = decoder_cls()
    msg.ParseFromString(data)
    return msg
