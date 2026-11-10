# SPDX-License-Identifier: GPL-3.0-only
"""Shared matplotlib style for analysis figures."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from capture_analysis.types import GapInterval, TimeWindow  # noqa: E402


def new_fig(nrows: int = 1, height: float = 2.2):
    fig, axes = plt.subplots(nrows, 1, figsize=(11, height * nrows), sharex=True)
    if nrows == 1:
        axes = [axes]
    return fig, axes


def shade_gaps(ax, gaps: list[GapInterval], window: TimeWindow, *, t0_ns: int) -> None:
    for g in gaps:
        start = max(g.start_session_ns, window.start_session_ns)
        end = g.end_session_ns if g.end_session_ns is not None else window.end_session_ns
        end = min(end, window.end_session_ns)
        if end <= start:
            continue
        ax.axvspan((start - t0_ns) / 1e9, (end - t0_ns) / 1e9, color="#e5484d", alpha=0.15)


def save_fig(fig, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def to_seconds(t_ns: np.ndarray, t0_ns: int) -> np.ndarray:
    return (np.asarray(t_ns, dtype=np.float64) - t0_ns) / 1e9


def plot_recorded_series(
    ax,
    t_ns: np.ndarray,
    y: np.ndarray,
    *,
    window: TimeWindow,
    gaps: list[GapInterval],
    max_points: int = 20000,
    **line_options,
) -> None:
    """Plot session seconds without joining samples across declared missing intervals.

    Split before display thinning so a short gap, missing value, or backwards
    timestamp cannot disappear between retained display points. Raw arrays stay
    unchanged; this is a display reduction, never a resampled measurement.
    """
    t = np.asarray(t_ns, dtype=np.int64)
    values = np.asarray(y, dtype=np.float64)
    if t.ndim != 1 or values.shape != t.shape:
        raise ValueError("plot timestamps and values must be equal-length vectors")
    if t.size == 0:
        return
    valid = np.isfinite(values) & (t >= window.start_session_ns) & (t <= window.end_session_ns)
    connected = t[1:] > t[:-1]
    for gap in gaps:
        end = gap.end_session_ns if gap.end_session_ns is not None else window.end_session_ns
        if end < gap.start_session_ns:
            continue
        valid &= ~((t >= gap.start_session_ns) & (t <= end))
        connected &= ~((t[:-1] <= end) & (t[1:] >= gap.start_session_ns))
    connected &= valid[:-1] & valid[1:]
    starts = np.flatnonzero(valid & np.r_[True, ~connected])
    ends = np.flatnonzero(valid & np.r_[~connected, True]) + 1
    step = max(1, int(np.ceil(t.size / max_points)))
    x_parts, y_parts = [], []
    for start, end in zip(starts, ends, strict=True):
        indices = np.arange(start, end, step)
        if indices[-1] != end - 1:
            indices = np.r_[indices, end - 1]
        x_parts.extend([to_seconds(t[indices], 0), np.array([np.nan])])
        y_parts.extend([values[indices], np.array([np.nan])])
    if x_parts:
        ax.plot(np.concatenate(x_parts), np.concatenate(y_parts), **line_options)
        # A one-sample valid region has no line segment. Keep it visible.
        singletons = starts[(ends - starts) == 1]
        if singletons.size:
            marker_options = {key: value for key, value in line_options.items() if key != "label"}
            ax.plot(
                to_seconds(t[singletons], 0),
                values[singletons],
                linestyle="none",
                marker=".",
                **marker_options,
            )


def shade_recorded_gaps(ax, gaps, window: TimeWindow, t_ns: np.ndarray) -> None:
    """Shade only the displayed recording extent, including durationless packages."""
    t = np.asarray(t_ns, dtype=np.int64)
    if not t.size:
        return
    visible = TimeWindow(
        max(window.start_session_ns, int(t.min())),
        min(window.end_session_ns, int(t.max())),
    )
    shade_gaps(ax, gaps, visible, t0_ns=0)
