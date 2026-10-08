# SPDX-License-Identifier: GPL-3.0-only
"""Load generic.numeric_batch/1 without changing raw samples or native clocks."""

from __future__ import annotations

import json
import math

import numpy as np

from capture_analysis.loaders.base import guard_ram
from capture_analysis.loaders.mcap_iter import decode_protobuf, iter_mcap_messages
from capture_analysis.types import LoadedEmg, StreamRef, TimeWindow


def _decode(payload: bytes) -> tuple[int, list[str], list[float], list[int]]:
    try:
        obj = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        from capture_protocol.generated.capture.v1.data import numeric_batch_pb2

        msg = decode_protobuf(numeric_batch_pb2.NumericBatch, payload)
        return (
            int(msg.channel_count),
            list(msg.channel_names),
            list(msg.samples),
            list(msg.device_time_ns),
        )
    if not isinstance(obj, dict):
        raise ValueError("numeric batch JSON must be an object")
    channels = obj.get("channel_count", 0)
    names = obj.get("channel_names", [])
    samples = obj.get("samples", [])
    times = obj.get("device_time_ns", [])
    if isinstance(channels, bool) or not isinstance(channels, int):
        raise ValueError("numeric channel_count must be an integer")
    if not all(isinstance(values, list) for values in (names, samples, times)):
        raise ValueError("numeric names, samples and timestamps must be arrays")
    if not all(isinstance(name, str) for name in names):
        raise ValueError("numeric channel names must be strings")
    if not all(
        isinstance(value, (int, float)) and not isinstance(value, bool) for value in samples
    ):
        raise ValueError("numeric samples must be numbers")
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in times):
        raise ValueError("numeric device timestamps must be integer nanoseconds")
    return channels, names, samples, times


def load_numeric_batch(
    stream: StreamRef,
    window: TimeWindow,
    *,
    max_ram_bytes: int,
) -> LoadedEmg:
    """Return channels × time, selected by session time and stably time-ordered.

    MCAP log_time is the first datum's session timestamp (SESSION_FORMAT.md).
    Preserve native within-batch device-time deltas at that anchor. This is an
    uncalibrated derived timebase, not a device-clock drift fit. If native times
    are absent, use the required descriptor rate and flag INTERPOLATED_TIMESTAMP.
    Native timestamps remain unchanged in the source MCAP.
    """
    if stream.data_schema_id != "generic.numeric_batch/1":
        raise ValueError(f"unsupported numeric data schema: {stream.data_schema_id!r}")
    fs = stream.require_rate()
    if not math.isfinite(fs):
        raise ValueError("numeric nominal_rate_hz must be finite")
    # A package can have an unknown duration and an open TimeWindow. Estimate
    # from actual batches, never from that window's sentinel or a guessed rate.
    overhead = 1024 * 1024
    guard_ram(overhead, max_ram_bytes=max_ram_bytes, stream=stream)

    channel_ids: list[str] | None = None
    t_parts: list[np.ndarray] = []
    x_parts: list[np.ndarray] = []
    flags: list[int] = []
    retained_bytes = 0
    int64 = np.iinfo(np.int64)

    for name, payload, log_time in iter_mcap_messages(stream.mcap_paths):
        # The Python worker registers the protobuf type name. JSON/older test
        # packages register the data-schema ID. Do not match arbitrary versions.
        if name not in ("capture.v1.data.NumericBatch", "generic.numeric_batch/1"):
            continue
        guard_ram(
            overhead + 8 * (retained_bytes + len(payload)),
            max_ram_bytes=max_ram_bytes,
            stream=stream,
        )
        ch, names, samples, times = _decode(payload)
        if not samples:
            if times:
                raise ValueError("numeric timestamps without sample frames")
            continue
        if ch <= 0 or len(samples) % ch:
            raise ValueError("numeric samples must contain channel_count × whole frames")
        n_frames = len(samples) // ch
        names = names or [f"ch{i}" for i in range(ch)]
        if len(names) != ch or len(set(names)) != ch or not all(names):
            raise ValueError(
                "numeric channel names must be nonempty, unique and match channel_count"
            )
        if channel_ids is None:
            channel_ids = names
        elif channel_ids != names:
            raise ValueError("numeric channel layout changed between batches")
        if times and len(times) != n_frames:
            raise ValueError("numeric device timestamps must contain one value per frame")

        # Include decoded values, timestamps and concatenate/sort copies. Check
        # before allocating arrays, including when the descriptor understates
        # actual batch density. This is an estimate, not a process-memory limit.
        batch_bytes = 8 * (len(samples) + n_frames)
        guard_ram(
            overhead + 8 * (retained_bytes + batch_bytes),
            max_ram_bytes=max_ram_bytes,
            stream=stream,
        )
        if times:
            if any(value < int64.min or value > int64.max for value in times):
                raise ValueError("numeric device timestamp outside int64 range")
            if any(right < left for left, right in zip(times, times[1:], strict=False)):
                raise ValueError("numeric device timestamps run backwards within a batch")
            mapped = [int(log_time) + value - times[0] for value in times]
            quality = 0
        else:
            mapped = [int(log_time) + round(i * 1e9 / fs) for i in range(n_frames)]
            quality = 1 << 3  # INTERPOLATED_TIMESTAMP; see docs/design/TIMING.md.
        if any(value < int64.min or value > int64.max for value in mapped):
            raise ValueError("numeric session timestamp outside int64 range")
        t = np.asarray(mapped, dtype=np.int64)
        keep = (t >= window.start_session_ns) & (t <= window.end_session_ns)
        if not np.any(keep):
            continue
        mat = np.asarray(samples, dtype=np.float64).reshape(n_frames, ch).T
        if not np.all(np.isfinite(mat)):
            raise ValueError("numeric samples must be finite")
        t = t[keep]
        mat = mat[:, keep]
        retained_bytes += t.nbytes + mat.nbytes
        t_parts.append(t)
        x_parts.append(mat)
        flags.append(quality)

    if not x_parts:
        return LoadedEmg(
            channel_ids=channel_ids or [],
            t_sample_ns=np.zeros(0, dtype=np.int64),
            X=np.zeros((len(channel_ids or []), 0), dtype=np.float64),
            fs_hz=float(fs),
            units=stream.units or "a.u.",
        )

    t_all = np.concatenate(t_parts)
    x_all = np.concatenate(x_parts, axis=1)
    order = np.argsort(t_all, kind="stable")
    return LoadedEmg(
        channel_ids=channel_ids or [],
        t_sample_ns=t_all[order],
        X=x_all[:, order],
        fs_hz=float(fs),
        units=stream.units or "a.u.",
        batch_quality_flags=flags,
    )
