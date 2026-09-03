# SPDX-License-Identifier: GPL-3.0-only
"""Load generic.numeric_batch/1 (protobuf or JSON) into a contiguous matrix."""

from __future__ import annotations

import json

import numpy as np

from capture_analysis.loaders.base import estimate_emg_bytes, guard_ram
from capture_analysis.loaders.mcap_iter import decode_protobuf, iter_mcap_messages
from capture_analysis.types import LoadedEmg, StreamRef, TimeWindow


def load_numeric_batch(
    stream: StreamRef,
    window: TimeWindow,
    *,
    max_ram_bytes: int,
) -> LoadedEmg:
    """Reuse LoadedEmg shape: channels × time with device timestamps."""
    fs = stream.require_rate() if stream.nominal_rate_hz else 100.0
    channel_hint = int(stream.dimensions[0]) if stream.dimensions else None
    # Soft RAM guard using EMG estimator as an upper bound.
    try:
        guard_ram(
            estimate_emg_bytes(stream, window, channel_count=channel_hint or 8),
            max_ram_bytes=max_ram_bytes,
            stream=stream,
        )
    except Exception:  # noqa: BLE001
        pass

    channel_ids: list[str] | None = None
    t_parts: list[np.ndarray] = []
    x_parts: list[np.ndarray] = []

    for _name, payload, _log in iter_mcap_messages(
        stream.mcap_paths, schema_needle="numeric_batch"
    ):
        ch = 0
        names: list[str] = []
        samples: list[float] = []
        times: list[int] = []
        try:
            from capture_protocol.generated.capture.v1.data import numeric_batch_pb2

            msg = decode_protobuf(numeric_batch_pb2.NumericBatch, payload)
            ch = int(msg.channel_count)
            names = list(msg.channel_names)
            samples = list(msg.samples)
            times = list(msg.device_time_ns)
        except Exception:  # noqa: BLE001
            try:
                obj = json.loads(payload.decode("utf-8"))
            except Exception:  # noqa: BLE001
                continue
            ch = int(obj.get("channel_count", 0))
            names = list(obj.get("channel_names", []))
            samples = [float(x) for x in obj.get("samples", [])]
            times = [int(x) for x in obj.get("device_time_ns", [])]

        if ch <= 0 or not samples:
            continue
        n_frames = len(samples) // ch
        if n_frames <= 0:
            continue
        if channel_ids is None:
            channel_ids = names[:ch] if names else [f"ch{i}" for i in range(ch)]
        mat = np.asarray(samples[: n_frames * ch], dtype=np.float64).reshape(n_frames, ch)
        if times and len(times) >= n_frames:
            t = np.asarray(times[:n_frames], dtype=np.int64)
        else:
            t = np.arange(n_frames, dtype=np.int64)
        t_parts.append(t)
        x_parts.append(mat)

    if not x_parts or channel_ids is None:
        return LoadedEmg(
            stream=stream,
            channel_ids=[],
            t_sample_ns=np.zeros(0, dtype=np.int64),
            X=np.zeros((0, 0), dtype=np.float64),
            fs_hz=float(fs),
            units="a.u.",
            quality_flags=np.zeros(0, dtype=np.uint8),
        )

    t_all = np.concatenate(t_parts)
    x_all = np.concatenate(x_parts, axis=0)
    return LoadedEmg(
        stream=stream,
        channel_ids=channel_ids,
        t_sample_ns=t_all,
        X=x_all.T,  # channels × time, matching EMG convention when possible
        fs_hz=float(fs),
        units=stream.units or "a.u.",
        quality_flags=np.zeros(t_all.shape[0], dtype=np.uint8),
    )
