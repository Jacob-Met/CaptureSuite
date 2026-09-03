# SPDX-License-Identifier: GPL-3.0-only
"""Load emg.batch/1 into a contiguous matrix (RAM-guarded)."""

from __future__ import annotations

import numpy as np

from capture_analysis.loaders.base import estimate_emg_bytes, guard_ram
from capture_analysis.loaders.mcap_iter import decode_protobuf, iter_mcap_messages
from capture_analysis.types import LoadedEmg, StreamRef, TimeWindow


def load_emg(
    stream: StreamRef,
    window: TimeWindow,
    *,
    max_ram_bytes: int,
) -> LoadedEmg:
    fs = stream.require_rate()
    channel_hint = int(stream.dimensions[0]) if stream.dimensions else None
    guard_ram(
        estimate_emg_bytes(stream, window, channel_count=channel_hint),
        max_ram_bytes=max_ram_bytes,
        stream=stream,
    )

    from capture_protocol.generated.capture.v1.data import emg_batch_pb2

    channel_ids: list[str] | None = None
    t_parts: list[np.ndarray] = []
    x_parts: list[np.ndarray] = []
    flags: list[int] = []

    for _name, payload, _log in iter_mcap_messages(
        stream.mcap_paths, schema_needle="emg.batch"
    ):
        msg = decode_protobuf(emg_batch_pb2.EmgBatch, payload)
        n = int(msg.sample_count)
        if n <= 0:
            continue
        ch_ids = list(msg.channel_ids)
        if not ch_ids:
            continue
        if channel_ids is None:
            channel_ids = ch_ids
        elif ch_ids != channel_ids:
            raise RuntimeError(
                f"EMG channel_ids changed mid-stream on {stream.source_id}"
            )
        c = len(channel_ids)
        raw = np.frombuffer(msg.samples_f32_le, dtype="<f4")
        if raw.size != c * n:
            raise RuntimeError(
                f"EMG payload size mismatch on {stream.source_id}: "
                f"got {raw.size}, expected {c * n}"
            )
        mat = raw.reshape(c, n)
        t0 = int(msg.timing.session_time_ns)
        # Per-sample times from batch start using nominal rate.
        t = t0 + (np.arange(n, dtype=np.int64) * int(round(1e9 / fs)))
        # Keep batches that overlap the window at all.
        if t[-1] < window.start_session_ns or t[0] > window.end_session_ns:
            continue
        t_parts.append(t)
        x_parts.append(mat)
        flags.append(int(msg.quality_flags))

    if not t_parts or channel_ids is None:
        return LoadedEmg(
            channel_ids=[],
            t_sample_ns=np.zeros(0, dtype=np.int64),
            X=np.zeros((0, 0), dtype=np.float32),
            fs_hz=fs,
            units=stream.units or "mV",
            batch_quality_flags=[],
        )

    t_all = np.concatenate(t_parts)
    x_all = np.concatenate(x_parts, axis=1)
    order = np.argsort(t_all, kind="mergesort")
    t_all = t_all[order]
    x_all = x_all[:, order]
    in_win = (t_all >= window.start_session_ns) & (t_all <= window.end_session_ns)
    return LoadedEmg(
        channel_ids=channel_ids,
        t_sample_ns=t_all[in_win],
        X=x_all[:, in_win].astype(np.float32, copy=False),
        fs_hz=fs,
        units=stream.units or "mV",
        batch_quality_flags=flags,
    )
