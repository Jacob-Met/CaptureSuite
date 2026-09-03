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
