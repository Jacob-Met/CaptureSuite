# SPDX-License-Identifier: GPL-3.0-only
"""Synchronized multi-panel dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from capture_analysis.plots.style import new_fig, save_fig, shade_gaps, to_seconds
from capture_analysis.types import GapInterval, TimeWindow


def plot_sync_dashboard(
    path: Path,
    *,
    window: TimeWindow,
    gaps: list[GapInterval],
    series: list[dict[str, Any]],
    title: str,
) -> None:
    """series items: {label, t_ns, y, color?}"""
    if not series:
        return
    t0 = min(int(np.min(np.asarray(item["t_ns"]))) for item in series)
    fig, axes = new_fig(len(series), height=2.0)
    for ax, item in zip(axes, series, strict=True):
        t = to_seconds(np.asarray(item["t_ns"]), t0)
        y = np.asarray(item["y"], dtype=np.float64)
        ax.plot(t, y, color=item.get("color", "#3d8bfd"), linewidth=1.0)
        ax.set_ylabel(item["label"])
        shade_gaps(ax, gaps, window, t0_ns=t0)
        ax.grid(True, alpha=0.25)
    axes[-1].set_xlabel("session time (s)")
    fig.suptitle(title, fontsize=11)
    save_fig(fig, path)
