# SPDX-License-Identifier: GPL-3.0-only
"""Synchronized multi-panel dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from capture_analysis.plots.style import (
    new_fig,
    plot_recorded_series,
    save_fig,
    shade_recorded_gaps,
)
from capture_analysis.types import GapInterval, TimeWindow


def plot_sync_dashboard(
    path: Path,
    *,
    window: TimeWindow,
    gaps: list[GapInterval],
    series: list[dict[str, Any]],
    title: str,
) -> None:
    """series items: {label, t_ns, y, color?, gaps?}; gaps are stream-scoped."""
    if not series:
        return
    fig, axes = new_fig(len(series), height=2.0)
    for ax, item in zip(axes, series, strict=True):
        t = np.asarray(item["t_ns"])
        y = np.asarray(item["y"], dtype=np.float64)
        lane_gaps = item.get("gaps", gaps)
        plot_recorded_series(
            ax,
            t,
            y,
            window=window,
            gaps=lane_gaps,
            color=item.get("color", "#3d8bfd"),
            linewidth=1.0,
        )
        ax.set_ylabel(item["label"])
        shade_recorded_gaps(ax, lane_gaps, window, t)
        ax.grid(True, alpha=0.25)
    axes[-1].set_xlabel("session time (s)")
    fig.suptitle(title, fontsize=11)
    save_fig(fig, path)
