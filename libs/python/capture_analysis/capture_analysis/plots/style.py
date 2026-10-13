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
    timestamps = np.asarray(t_ns)
    if timestamps.dtype.kind in "iu" and isinstance(t0_ns, (int, np.integer)):
        if timestamps.size == 0:
            return timestamps.astype(np.float64)
        origin = int(t0_ns)
        lower, upper = int(timestamps.min()), int(timestamps.max())
        limits = np.iinfo(np.int64)
        if (limits.min <= min(lower, origin) and max(upper, origin) <= limits.max
                and limits.min <= lower - origin and upper - origin <= limits.max):
            offsets = timestamps.astype(np.int64, copy=False) - np.int64(origin)
        else:
            # Python integers preserve offsets spanning the signed-int64 boundary.
            offsets = timestamps.astype(object) - origin
        return np.asarray(offsets, dtype=np.float64) / 1e9
    return (np.asarray(timestamps, dtype=np.float64) - t0_ns) / 1e9


def plot_observations(ax, x, y, *, color: str, linewidth: float = 1.0):
    """Keep line segments, adding a point only when a finite observation is isolated."""
    lines = ax.plot(x, y, color=color, linewidth=linewidth)
    for line in lines:
        valid = np.isfinite(line.get_xdata(orig=False)) & np.isfinite(line.get_ydata(orig=False))
        neighbor = np.zeros(valid.shape, dtype=bool)
        neighbor[1:] |= valid[:-1]
        neighbor[:-1] |= valid[1:]
        isolated = np.flatnonzero(valid & ~neighbor)
        if isolated.size:
            line.set_marker("o")
            line.set_markersize(3)
            line.set_markevery(isolated.tolist())
    return lines
