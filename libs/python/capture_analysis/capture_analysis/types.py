# SPDX-License-Identifier: GPL-3.0-only
"""Shared dataclasses for offline analysis (Phase A contracts)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StreamRef:
    source_id: str
    stream_id: str
    modality: str
    data_schema_id: str
    nominal_rate_hz: float
    units: str
    dimensions: tuple[int, ...] = ()
    mcap_paths: tuple[Path, ...] = ()
    mkv_paths: tuple[Path, ...] = ()
    timing_mcap_paths: tuple[Path, ...] = ()
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    stream_json_path: Path | None = None

    def require_rate(self) -> float:
        if self.nominal_rate_hz <= 0:
            raise ValueError(
                f"stream {self.source_id}/{self.stream_id} missing nominal_rate_hz "
                "(refusing to invent a timebase)"
            )
        return self.nominal_rate_hz


@dataclass(frozen=True)
class TimeWindow:
    start_session_ns: int
    end_session_ns: int
    label: str = "full"

    def contains(self, t_ns: int) -> bool:
        return self.start_session_ns <= t_ns <= self.end_session_ns


@dataclass(frozen=True)
class GapInterval:
    source_id: str
    stream_id: str
    cause: str
    start_session_ns: int
    end_session_ns: int | None
    closed: bool


@dataclass
class GapMask:
    """Invalid intervals for one StreamRef inside a TimeWindow."""

    stream: StreamRef
    window: TimeWindow
    gaps: list[GapInterval] = field(default_factory=list)
    policy: str = "mask"  # mask | split | fail

    def overlaps_window(self) -> list[GapInterval]:
        out: list[GapInterval] = []
        for g in self.gaps:
            end = g.end_session_ns if g.end_session_ns is not None else self.window.end_session_ns
            if (
                end < self.window.start_session_ns
                or g.start_session_ns > self.window.end_session_ns
            ):
                continue
            out.append(g)
        return out


@dataclass
class AnalysisGrid:
    grid_id: str
    rate_hz: float
    start_ns: int
    end_ns: int
    method: str  # linear | previous | window_mean
    source_stream_ids: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    valid_fraction_by_source: dict[str, float] = field(default_factory=dict)

    def to_manifest(self) -> dict[str, Any]:
        return {
            "gridId": self.grid_id,
            "rateHz": self.rate_hz,
            "startNs": self.start_ns,
            "endNs": self.end_ns,
            "method": self.method,
            "sourceStreamIds": list(self.source_stream_ids),
            "params": dict(self.params),
            "validFractionBySource": dict(self.valid_fraction_by_source),
        }


# Phase B will fill these; Phase A only needs the type names for loader stubs.
@dataclass
class LoadedEmg:
    channel_ids: list[str]
    t_sample_ns: Any  # numpy int64[N] in Phase B
    X: Any  # numpy float32[C,N]
    fs_hz: float
    units: str
    batch_quality_flags: list[int] = field(default_factory=list)


@dataclass
class LoadedImu:
    sensor_ids: list[str]
    t_frame_ns: Any
    accel: Any
    gyro: Any
    quat: Any
    units: str


class FrameIterator(Iterator[Any]):
    """Marker for streaming loaders (radar/video). No full-stream materialize API."""
