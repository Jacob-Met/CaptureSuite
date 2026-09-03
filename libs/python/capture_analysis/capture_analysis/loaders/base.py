# SPDX-License-Identifier: GPL-3.0-only
"""Loader contracts and RAM budget guard (Phase A).

Radar and video loaders must expose iterators only — there is deliberately no
API that returns an entire radar stream as one array. EMG/IMU may materialize
after `guard_ram` succeeds.
"""

from __future__ import annotations

from capture_analysis.types import StreamRef, TimeWindow

DEFAULT_MAX_RAM_BYTES = 2 * 1024**3  # 2 GiB


class LoaderNotImplemented(NotImplementedError):
    """Raised until Phase B implements the named loader."""


class RamBudgetExceeded(RuntimeError):
    pass


def estimate_emg_bytes(
    stream: StreamRef,
    window: TimeWindow,
    *,
    channel_count: int | None = None,
) -> int:
    """Rough upper bound: fs * channels * 4 bytes * duration."""
    fs = stream.require_rate()
    ch = channel_count
    if ch is None:
        ch = int(stream.dimensions[0]) if stream.dimensions else 8
    duration_s = max(0.0, (window.end_session_ns - window.start_session_ns) / 1e9)
    # 1.25x slack for batch overhead / quality side tables
    return int(fs * ch * 4 * duration_s * 1.25) + 1024 * 1024


def estimate_imu_bytes(
    stream: StreamRef,
    window: TimeWindow,
    *,
    sensor_count: int | None = None,
) -> int:
    fs = stream.require_rate()
    sensors = sensor_count
    if sensors is None:
        sensors = int(stream.dimensions[0]) if stream.dimensions else 4
    duration_s = max(0.0, (window.end_session_ns - window.start_session_ns) / 1e9)
    # ~13 floats (quat+accel+gyro+mag) * 4 bytes per sensor per frame
    return int(fs * sensors * 13 * 4 * duration_s * 1.25) + 1024 * 1024


def guard_ram(
    estimated_bytes: int,
    *,
    max_ram_bytes: int = DEFAULT_MAX_RAM_BYTES,
    stream: StreamRef | None = None,
) -> None:
    if estimated_bytes <= max_ram_bytes:
        return
    label = (
        f"{stream.source_id}/{stream.stream_id}"
        if stream is not None
        else "stream"
    )
    raise RamBudgetExceeded(
        f"{label} would allocate ~{estimated_bytes / (1024**3):.2f} GiB "
        f"(limit {max_ram_bytes / (1024**3):.2f} GiB); "
        "narrow --start-ns/--end-ns or raise --max-ram-bytes"
    )


def iter_frames_not_implemented(stream: StreamRef, window: TimeWindow):  # noqa: ARG001
    """Placeholder signature for streaming loaders (radar / video)."""
    raise LoaderNotImplemented(
        f"streaming loader for schema {stream.data_schema_id!r} arrives in Phase B"
    )
