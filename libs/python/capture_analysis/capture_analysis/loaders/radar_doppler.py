# SPDX-License-Identifier: GPL-3.0-only
"""Streaming loader for radar.doppler/1."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from capture_analysis.loaders.mcap_iter import decode_protobuf, iter_mcap_messages
from capture_analysis.types import StreamRef, TimeWindow


@dataclass(frozen=True)
class RadarDopplerItem:
    t_ns: int
    frame_index: int
    z: np.ndarray  # complex64[N]
    motion_detected: bool
    direction: int


def iter_radar_doppler(
    stream: StreamRef,
    window: TimeWindow,
) -> Iterator[RadarDopplerItem]:
    from capture_protocol.generated.capture.v1.data import radar_doppler_pb2

    for _name, payload, _log in iter_mcap_messages(
        stream.mcap_paths, schema_needle="radar.doppler"
    ):
        msg = decode_protobuf(radar_doppler_pb2.RadarDopplerFrame, payload)
        t = int(msg.timing.session_time_ns)
        if t < window.start_session_ns or t > window.end_session_ns:
            continue
        n = int(msg.num_samples)
        raw = np.frombuffer(msg.payload, dtype="<f4")
        if raw.size != n * 2:
            continue
        z = raw.reshape(n, 2)
        complex_z = z[:, 0].astype(np.float32) + 1j * z[:, 1].astype(np.float32)
        yield RadarDopplerItem(
            t_ns=t,
            frame_index=int(msg.frame_index),
            z=complex_z.astype(np.complex64, copy=False),
            motion_detected=bool(msg.motion_detected),
            direction=int(msg.direction),
        )
