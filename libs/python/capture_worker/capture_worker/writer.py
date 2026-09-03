# SPDX-License-Identifier: Apache-2.0
"""MCAP segment writer helper for Python workers."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcap.well_known import MessageEncoding, SchemaEncoding
from mcap.writer import Writer


@dataclass(slots=True)
class SealedSegment:
    source_id: str
    stream_id: str
    path: str  # package-relative, forward slashes
    absolute_path: Path
    size_bytes: int
    hash_blake3_hex: str
    start_session_time_ns: int
    end_session_time_ns: int
    actual_count: int
    segment_index: int


def _blake3_file_hex(path: Path) -> str:
    """Return BLAKE3 hex digest when the optional ``blake3`` package is present."""
    try:
        from blake3 import blake3  # type: ignore[import-not-found]
    except ImportError:
        return ""
    hasher = blake3()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


class McapSegmentWriter:
    """Write protobuf payloads into rotating ``NNNNNN.mcap`` segment files."""

    def __init__(
        self,
        *,
        package_root: Path,
        source_id: str,
        stream_id: str,
        schema_name: str,
        data_schema_id: str,
        schema_data: bytes = b"",
        rotate_bytes: int = 512 * 1024 * 1024,
        on_sealed: Callable[[SealedSegment], None] | None = None,
    ) -> None:
        self.package_root = package_root.resolve()
        self.source_id = source_id
        self.stream_id = stream_id
        self.schema_name = schema_name
        self.data_schema_id = data_schema_id
        self.schema_data = schema_data
        self.rotate_bytes = rotate_bytes
        self.on_sealed = on_sealed

        self._segments_dir = (
            self.package_root / "streams" / source_id / stream_id / "segments"
        )
        self._segments_dir.mkdir(parents=True, exist_ok=True)

        self._segment_index = 0
        self._file: Any = None
        self._writer: Writer | None = None
        self._channel_id = 0
        self._approx_bytes = 0
        self._count = 0
        self._start_ns = -1
        self._end_ns = -1
        self._total = 0

    def open(self, initial_segment_index: int = 0) -> None:
        self._segment_index = initial_segment_index
        self._open_segment()

    def append(
        self,
        payload: bytes,
        *,
        log_time_ns: int,
        publish_time_ns: int | None = None,
    ) -> None:
        if self._writer is None:
            raise RuntimeError("writer not open")
        if publish_time_ns is None:
            publish_time_ns = log_time_ns
        self._writer.add_message(
            channel_id=self._channel_id,
            log_time=log_time_ns,
            data=payload,
            publish_time=publish_time_ns,
        )
        self._approx_bytes += len(payload) + 64
        self._count += 1
        self._total += 1
        if self._start_ns < 0:
            self._start_ns = log_time_ns
        self._end_ns = log_time_ns
        if self._approx_bytes >= self.rotate_bytes:
            self._rotate()

    def close(self) -> SealedSegment | None:
        return self._close_segment(seal=True)

    def append_gap(
        self,
        *,
        reason: str,
        session_time_ns: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append a local gap note under the stream directory (daemon owns health/)."""
        gaps_path = self._segments_dir.parent / "worker_gaps.jsonl"
        row = {
            "reason": reason,
            "sessionTimeNs": session_time_ns,
            "sourceId": self.source_id,
            "streamId": self.stream_id,
            "details": details or {},
        }
        with gaps_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")

    def _relative(self, absolute: Path) -> str:
        return absolute.resolve().relative_to(self.package_root).as_posix()

    def _segment_path(self) -> Path:
        return self._segments_dir / f"{self._segment_index:06d}.mcap"

    def _open_segment(self) -> None:
        path = self._segment_path()
        self._file = path.open("wb")
        self._writer = Writer(self._file)
        self._writer.start(profile="", library="capture_worker")
        schema_id = self._writer.register_schema(
            name=self.schema_name,
            encoding=SchemaEncoding.Protobuf,
            data=self.schema_data,
        )
        topic = f"{self.source_id}/{self.stream_id}/{self.data_schema_id}"
        self._channel_id = self._writer.register_channel(
            topic=topic,
            message_encoding=MessageEncoding.Protobuf,
            schema_id=schema_id,
            metadata={"data_schema_id": self.data_schema_id},
        )
        self._approx_bytes = 0
        self._count = 0
        self._start_ns = -1
        self._end_ns = -1

    def _close_segment(self, *, seal: bool) -> SealedSegment | None:
        if self._writer is None or self._file is None:
            return None
        path = self._segment_path()
        self._writer.finish()
        self._writer = None
        self._file.close()
        self._file = None
        if not seal or self._count <= 0:
            return None
        size = path.stat().st_size if path.is_file() else 0
        sealed = SealedSegment(
            source_id=self.source_id,
            stream_id=self.stream_id,
            path=self._relative(path),
            absolute_path=path,
            size_bytes=size,
            hash_blake3_hex=_blake3_file_hex(path),
            start_session_time_ns=max(0, self._start_ns),
            end_session_time_ns=max(0, self._end_ns),
            actual_count=self._count,
            segment_index=self._segment_index,
        )
        if self.on_sealed is not None:
            self.on_sealed(sealed)
        return sealed

    def _rotate(self) -> None:
        self._close_segment(seal=True)
        self._segment_index += 1
        self._open_segment()
