# SPDX-License-Identifier: GPL-3.0-only
"""Display RMS from contiguous observed EMG support, never across missing time."""

from __future__ import annotations

import numpy as np

from capture_analysis.types import GapMask, LoadedEmg
from capture_analysis.windows import validity_mask


def emg_rms_envelope(loaded: LoadedEmg, gap_mask: GapMask) -> tuple[np.ndarray, np.ndarray]:
    """Return a roughly 20 Hz first-channel RMS preview with explicit breaks.

    The centered nominal 50 ms kernel is clipped to each observed run and
    normalized by its actual sample count. Missing values are unknown, not zero.
    Output timestamps are retained sample timestamps; NaN separators mark
    disconnected runs for plotting and become JSON null in the saved series.
    """
    times = np.asarray(loaded.t_sample_ns, dtype=np.int64)
    if not times.size or not loaded.X.size:
        return times[:0], np.zeros(0, dtype=np.float64)
    values = loaded.X[0].astype(np.float64, copy=False)
    valid = validity_mask(times, gap_mask) & np.isfinite(values)
    period = max(1, int(round(1e9 / loaded.fs_hz)))
    delta = np.diff(times)
    connected = (delta > 0) & (delta <= period + period // 2)
    for gap in gap_mask.overlaps_window():
        end = gap.end_session_ns
        if end is None:
            end = gap_mask.window.end_session_ns
        connected &= ~((times[:-1] <= end) & (times[1:] >= gap.start_session_ns))
    connected &= valid[:-1] & valid[1:]
    starts = np.flatnonzero(valid & np.r_[True, ~connected])
    stops = np.flatnonzero(valid & np.r_[~connected, True]) + 1
    step = max(1, int(loaded.fs_hz // 20))
    # Match the former centered kernel's alignment without zero padding.
    left_width, right_width = step // 2, (step - 1) // 2
    out_times, out_values = [], []
    for start, stop in zip(starts, stops, strict=True):
        segment = values[start:stop]
        indices = np.arange(0, len(segment), step)
        if indices[-1] != len(segment) - 1:
            indices = np.r_[indices, len(segment) - 1]
        left = np.maximum(0, indices - left_width)
        right = np.minimum(len(segment), indices + right_width + 1)
        # Prefix sums avoid expanding a long convolution window for each point.
        sums = np.r_[0.0, np.cumsum(segment * segment)]
        rms = np.sqrt(np.maximum(0.0, sums[right] - sums[left]) / (right - left))
        if out_times:
            out_times.append(np.array([times[start]], dtype=np.int64))
            out_values.append(np.array([np.nan]))
        out_times.append(times[start + indices])
        out_values.append(rms)
    if not out_times:
        return times[:0], np.zeros(0, dtype=np.float64)
    return np.concatenate(out_times), np.concatenate(out_values)
