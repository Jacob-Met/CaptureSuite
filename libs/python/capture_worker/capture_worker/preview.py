# SPDX-License-Identifier: Apache-2.0
"""Preview frame helpers for Python workers."""

from __future__ import annotations

from collections.abc import Sequence

from capture_protocol.generated.capture.v1 import preview_pb2


def build_trace_preview(
    *,
    source_id: str,
    stream_id: str,
    channel_names: Sequence[str],
    samples: Sequence[float],
    points_per_channel: int,
    session_time_ns: int,
    sequence: int,
    kind: int = preview_pb2.PREVIEW_KIND_TRACE_BLOCK,
    units: str = "a.u.",
    display_min: float = -1.0,
    display_max: float = 1.0,
    decimated_from_rate_hz: float = 0.0,
    dropped_since_last: int = 0,
) -> preview_pb2.PreviewFrame:
    """Build a TRACE_BLOCK / TRACE_SINGLE / SCALAR_SERIES preview frame."""
    frame = preview_pb2.PreviewFrame()
    frame.source_id = source_id
    frame.stream_id = stream_id
    frame.kind = kind
    frame.session_time_ns = session_time_ns
    frame.sequence = sequence
    frame.dropped_since_last = dropped_since_last
    trace = frame.trace
    trace.channel_names.extend(channel_names)
    trace.channel_count = len(channel_names)
    trace.points_per_channel = points_per_channel
    trace.samples.extend(float(x) for x in samples)
    trace.display_min = display_min
    trace.display_max = display_max
    trace.units = units
    trace.decimated_from_rate_hz = decimated_from_rate_hz
    return frame


def build_preview_descriptor(
    *,
    source_id: str,
    stream_id: str = "",
    kind: int = preview_pb2.PREVIEW_KIND_TRACE_BLOCK,
    max_rate_hz: float = 20.0,
    max_payload_bytes: int = 32 * 1024,
    available_channels: Sequence[str] | None = None,
) -> preview_pb2.PreviewDescriptor:
    desc = preview_pb2.PreviewDescriptor()
    desc.source_id = source_id
    desc.stream_id = stream_id
    desc.kind = kind
    desc.ring_slot_count = 3
    desc.max_payload_bytes = max_payload_bytes
    desc.max_rate_hz = max_rate_hz
    desc.drop_policy = preview_pb2.PREVIEW_DROP_POLICY_LATEST_WINS
    desc.content_type = "application/x-capture-trace"
    desc.enabled = True
    if available_channels:
        desc.available_channels.extend(available_channels)
    return desc


def make_trace_preview(
    *,
    source_id: str,
    stream_id: str,
    session_time_ns: int,
    sequence: int,
    samples: Sequence[float],
    channel_count: int,
    channel_names: Sequence[str] | None = None,
    units: str = "a.u.",
    display_min: float = -1.0,
    display_max: float = 1.0,
    points_per_channel: int | None = None,
) -> preview_pb2.PreviewFrame:
    """Compatibility wrapper used by LSL / older call sites."""
    names = list(channel_names) if channel_names is not None else [
        f"ch{i}" for i in range(channel_count)
    ]
    if points_per_channel is None:
        points_per_channel = max(1, len(samples) // max(1, channel_count))
    return build_trace_preview(
        source_id=source_id,
        stream_id=stream_id,
        channel_names=names,
        samples=samples,
        points_per_channel=points_per_channel,
        session_time_ns=session_time_ns,
        sequence=sequence,
        units=units,
        display_min=display_min,
        display_max=display_max,
    )
