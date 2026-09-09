# SPDX-License-Identifier: GPL-3.0-only
"""Per-modality figure helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from capture_analysis.plots.style import new_fig, save_fig, shade_gaps, to_seconds
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
    t0 = int(loaded.t_sample_ns[0])
    t = to_seconds(loaded.t_sample_ns, t0)
    # Downsample for plotting if huge
    step = max(1, t.size // 20000)
    for i in range(n):
        axes[i].plot(t[::step], loaded.X[i, ::step], linewidth=0.6, color="#35c46b")
        axes[i].set_ylabel(loaded.channel_ids[i][:12])
        shade_gaps(axes[i], gaps, window, t0_ns=t0)
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
    t0 = int(loaded.t_frame_ns[0])
    t = to_seconds(loaded.t_frame_ns, t0)
    for s, sid in enumerate(loaded.sensor_ids[:3]):
        mag = np.linalg.norm(loaded.accel[:, s], axis=1)
        ax.plot(t, mag, label=sid, linewidth=1.0)
    shade_gaps(ax, gaps, window, t0_ns=t0)
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
) -> None:
    if t_ns.size == 0:
        return
    fig, axes = new_fig(1, height=2.8)
    ax = axes[0]
    t0 = int(np.min(t_ns))
    ax.plot(to_seconds(t_ns, t0), y, color=color, linewidth=1.0)
    shade_gaps(ax, gaps, window, t0_ns=t0)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("session time (s)")
    fig.suptitle(title, fontsize=11)
    save_fig(fig, path)
