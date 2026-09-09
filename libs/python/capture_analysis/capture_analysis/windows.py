# SPDX-License-Identifier: GPL-3.0-only
"""Time windows, checkpoint sections, and gap masks."""

from __future__ import annotations

from typing import Any

import numpy as np
from capture_session.package_reader import GapSummary, ReviewSummary

from capture_analysis.types import GapInterval, GapMask, StreamRef, TimeWindow


def full_window(summary: ReviewSummary) -> TimeWindow:
    end = max(int(summary.duration_ns), 0)
    if end <= 1:
        # Integrity often omits endSessionTimeNs, and session_time_ns can be
        # negative (pre-T0 / mapping quirks). Use a fully open window; plots
        # zero to the first sample of each series.
        return TimeWindow(-(1 << 62) + 1, (1 << 62) - 1, label="full")
    return TimeWindow(0, end, label="full")


def resolve_window(
    summary: ReviewSummary,
    *,
    start_ns: int | None = None,
    end_ns: int | None = None,
    checkpoint_section: str | None = None,
) -> TimeWindow:
    base = full_window(summary)
    if checkpoint_section:
        return checkpoint_section_window(summary, checkpoint_section)
    start = base.start_session_ns if start_ns is None else int(start_ns)
    end = base.end_session_ns if end_ns is None else int(end_ns)
    if end < start:
        raise ValueError(f"invalid window: start={start} end={end}")
    label = "full" if start_ns is None and end_ns is None else "custom"
    return TimeWindow(start, end, label=label)


def _checkpoint_time_ns(cp: dict[str, Any]) -> int:
    for key in (
        "effectiveTimestampNs",
        "effective_timestamp_ns",
        "originalTimestampNs",
        "original_timestamp_ns",
        "timestampNs",
        "timestamp_ns",
    ):
        if key in cp and cp[key] is not None:
            return int(cp[key])
    return 0


def _checkpoint_id(cp: dict[str, Any]) -> str:
    return str(cp.get("checkpointId") or cp.get("checkpoint_id") or cp.get("name") or "")


def checkpoint_section_window(summary: ReviewSummary, section_id: str) -> TimeWindow:
    cps = sorted(summary.checkpoints, key=_checkpoint_time_ns)
    if not cps:
        raise ValueError("no checkpoints in package")
    idx = None
    for i, cp in enumerate(cps):
        if _checkpoint_id(cp) == section_id or str(cp.get("name") or "") == section_id:
            idx = i
            break
    if idx is None:
        raise ValueError(f"checkpoint section not found: {section_id}")
    start = _checkpoint_time_ns(cps[idx])
    if idx + 1 < len(cps):
        end = _checkpoint_time_ns(cps[idx + 1])
    else:
        end = max(int(summary.duration_ns), start + 1)
    return TimeWindow(start, end, label=f"cp:{section_id}")


def gaps_to_intervals(summary: ReviewSummary) -> list[GapInterval]:
    out: list[GapInterval] = []
    for g in summary.gaps:
        out.append(
            GapInterval(
                source_id=g.source_id,
                stream_id=g.stream_id,
                cause=g.cause,
                start_session_ns=g.start_session_time_ns,
                end_session_ns=g.end_session_time_ns,
                closed=g.closed,
            )
        )
    return out


def build_gap_mask(
    stream: StreamRef,
    window: TimeWindow,
    gaps: list[GapInterval] | list[GapSummary],
    *,
    policy: str = "mask",
) -> GapMask:
    intervals: list[GapInterval] = []
    for g in gaps:
        if isinstance(g, GapInterval):
            if g.source_id and g.source_id != stream.source_id:
                continue
            intervals.append(g)
        else:
            if g.source_id and g.source_id != stream.source_id:
                continue
            intervals.append(
                GapInterval(
                    source_id=g.source_id,
                    stream_id=g.stream_id,
                    cause=g.cause,
                    start_session_ns=g.start_session_time_ns,
                    end_session_ns=g.end_session_time_ns,
                    closed=g.closed,
                )
            )
    return GapMask(stream=stream, window=window, gaps=intervals, policy=policy)


def validity_mask(
    t_ns: np.ndarray,
    gap_mask: GapMask,
    *,
    window: TimeWindow | None = None,
) -> np.ndarray:
    """True where samples are valid (inside window and outside gaps)."""
    win = window or gap_mask.window
    t = np.asarray(t_ns, dtype=np.int64)
    valid = (t >= win.start_session_ns) & (t <= win.end_session_ns)
    for g in gap_mask.overlaps_window():
        end = g.end_session_ns if g.end_session_ns is not None else win.end_session_ns
        valid &= ~((t >= g.start_session_ns) & (t <= end))
    return valid


def valid_fraction(valid: np.ndarray) -> float:
    if valid.size == 0:
        return 0.0
    return float(np.count_nonzero(valid) / valid.size)


def enforce_gap_policy(gap_mask: GapMask, valid: np.ndarray) -> None:
    if gap_mask.policy != "fail":
        return
    if gap_mask.overlaps_window() and valid.size and not bool(np.all(valid)):
        raise RuntimeError(
            f"gap_policy=fail: gaps overlap {gap_mask.stream.source_id}/{gap_mask.stream.stream_id}"
        )


def split_valid_runs(valid: np.ndarray) -> list[tuple[int, int]]:
    """Return [start, end) index ranges of contiguous True runs."""
    if valid.size == 0:
        return []
    v = np.asarray(valid, dtype=bool)
    edges = np.diff(v.astype(np.int8))
    starts = list(np.where(edges == 1)[0] + 1)
    ends = list(np.where(edges == -1)[0] + 1)
    if v[0]:
        starts = [0] + starts
    if v[-1]:
        ends = ends + [v.size]
    return list(zip(starts, ends, strict=True))
