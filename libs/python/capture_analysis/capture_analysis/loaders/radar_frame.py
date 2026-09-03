# SPDX-License-Identifier: GPL-3.0-only
"""Streaming loader for radar.frame/1 (never materializes a full soak)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from capture_analysis.loaders.mcap_iter import decode_protobuf, iter_mcap_messages
from capture_analysis.types import StreamRef, TimeWindow


@dataclass(frozen=True)
class RadarFrameItem:
    t_ns: int
    frame_index: int
    configuration_hash: str
    encoding: str
    cube: np.ndarray  # (rx, chirps, samples) uint16 or float32


def iter_radar_frames(
    stream: StreamRef,
    window: TimeWindow,
) -> Iterator[RadarFrameItem]:
    from capture_protocol.generated.capture.v1.data import radar_frame_pb2

    for _name, payload, _log in iter_mcap_messages(
        stream.mcap_paths, schema_needle="radar.frame"
    ):
        msg = decode_protobuf(radar_frame_pb2.RadarFrame, payload)
        t = int(msg.timing.session_time_ns)
        if t < window.start_session_ns or t > window.end_session_ns:
            continue
        rx = int(msg.num_rx)
        chirps = int(msg.num_chirps)
        samples = int(msg.num_samples)
        enc = msg.sample_encoding or "uint16_le_raw_interleaved"
        if enc == "float32_le":
            raw = np.frombuffer(msg.payload, dtype="<f4")
        else:
            raw = np.frombuffer(msg.payload, dtype="<u2")
        expected = rx * chirps * samples
        if raw.size != expected:
            # Skip malformed rather than inventing geometry.
            continue
        cube = raw.reshape(rx, chirps, samples)
        yield RadarFrameItem(
            t_ns=t,
            frame_index=int(msg.frame_index),
            configuration_hash=str(msg.configuration_hash or ""),
            encoding=enc,
            cube=cube,
        )
