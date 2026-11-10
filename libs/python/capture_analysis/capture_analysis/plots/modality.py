# SPDX-License-Identifier: GPL-3.0-only
"""Per-modality figure helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from capture_analysis.plots.style import (
    new_fig,
    plot_recorded_series,
    save_fig,
    shade_recorded_gaps,
)
from capture_analysis.types import GapInterval, LoadedEmg, LoadedImu, TimeWindow


def plot_emg_channels(
    path: Path,
    loaded: LoadedEmg,
    *,
    window: TimeWindow,
    gaps: list[GapInterval],
    max_channels: int = 4,
) -> None:
    if loaded.X.size == 0:
        return
    n = min(max_channels, len(loaded.channel_ids))
    fig, axes = new_fig(n, height=1.8)
    for i in range(n):
        plot_recorded_series(
            axes[i],
            loaded.t_sample_ns,
            loaded.X[i],
            window=window,
            gaps=gaps,
            linewidth=0.6,
            color="#35c46b",
        )
        axes[i].set_ylabel(loaded.channel_ids[i][:12])
        shade_recorded_gaps(axes[i], gaps, window, loaded.t_sample_ns)
    axes[-1].set_xlabel("session time (s)")
    fig.suptitle("EMG channels", fontsize=11)
    save_fig(fig, path)


def plot_imu_accel(
    path: Path,
    loaded: LoadedImu,
    *,
    window: TimeWindow,
    gaps: list[GapInterval],
) -> None:
    if loaded.t_frame_ns.size == 0 or not loaded.sensor_ids:
        return
    fig, axes = new_fig(1, height=3.0)
    ax = axes[0]
    for s, sid in enumerate(loaded.sensor_ids[:3]):
        mag = np.linalg.norm(loaded.accel[:, s], axis=1)
        plot_recorded_series(
            ax,
            loaded.t_frame_ns,
            mag,
            window=window,
            gaps=gaps,
            label=sid,
            linewidth=1.0,
        )
    shade_recorded_gaps(ax, gaps, window, loaded.t_frame_ns)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_ylabel("|a|")
    ax.set_xlabel("session time (s)")
    fig.suptitle("IMU acceleration magnitude", fontsize=11)
    save_fig(fig, path)


def plot_series(
    path: Path,
    t_ns: np.ndarray,
    y: np.ndarray,
    *,
    window: TimeWindow,
    gaps: list[GapInterval],
    ylabel: str,
    title: str,
    color: str = "#3d8bfd",
    xlabel: str = "session time (s)",
) -> None:
    if t_ns.size == 0:
        return
    fig, axes = new_fig(1, height=2.8)
    ax = axes[0]
    plot_recorded_series(
        ax,
        t_ns,
        y,
        window=window,
        gaps=gaps,
        color=color,
        linewidth=1.0,
    )
    shade_recorded_gaps(ax, gaps, window, t_ns)
    ax.set_ylabel(ylabel)
    ax.set_xlabel(xlabel)
    fig.suptitle(title, fontsize=11)
    save_fig(fig, path)
