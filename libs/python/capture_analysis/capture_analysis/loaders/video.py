# SPDX-License-Identifier: GPL-3.0-only
"""Video timing QC loader (Phase B) + segment index stub for Phase D."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from capture_analysis.loaders.mcap_iter import decode_protobuf, iter_mcap_messages
from capture_analysis.types import StreamRef, TimeWindow


@dataclass
class VideoSegmentIndex:
    path: Path
    first_session_ns: int
    last_session_ns: int
    frame_count: int


@dataclass
class LoadedVideoTiming:
    t_frame_ns: np.ndarray
    segments: list[VideoSegmentIndex] = field(default_factory=list)
    mkv_paths: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_video_timing(stream: StreamRef, window: TimeWindow) -> LoadedVideoTiming:
    """Load frame session times from timing MCAP (or data MCAP with video schema)."""
    from capture_protocol.generated.capture.v1.data import video_timing_pb2

    paths = list(stream.timing_mcap_paths) or list(stream.mcap_paths)
    times: list[int] = []
    warnings: list[str] = []
    for _name, payload, _log in iter_mcap_messages(paths, schema_needle="video."):
        try:
            msg = decode_protobuf(video_timing_pb2.VideoFrameTiming, payload)
        except Exception:
            continue
        t = int(msg.timing.session_time_ns)
        if t < window.start_session_ns or t > window.end_session_ns:
            continue
        times.append(t)

    t_arr = np.asarray(sorted(times), dtype=np.int64)
    segments: list[VideoSegmentIndex] = []
    for mkv in stream.mkv_paths:
        segments.append(
            VideoSegmentIndex(
                path=mkv,
                first_session_ns=int(t_arr[0]) if t_arr.size else 0,
                last_session_ns=int(t_arr[-1]) if t_arr.size else 0,
                frame_count=int(t_arr.size),
            )
        )
    if stream.mkv_paths and t_arr.size == 0:
        warnings.append("mkv present but no timing messages decoded in window")
    return LoadedVideoTiming(
        t_frame_ns=t_arr,
        segments=segments,
        mkv_paths=list(stream.mkv_paths),
        warnings=warnings,
    )
