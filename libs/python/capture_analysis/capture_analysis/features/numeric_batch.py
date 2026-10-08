# SPDX-License-Identifier: GPL-3.0-only
"""Basic QC features for generic.numeric_batch/1 streams."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from capture_analysis.types import GapMask, LoadedEmg
from capture_analysis.windows import enforce_gap_policy, valid_fraction, validity_mask


def extract_numeric_batch_features(
    loaded: LoadedEmg,
    gap_mask: GapMask,
    *,
    window_s: float = 1.0,
    hop_s: float = 0.5,
) -> tuple[pd.DataFrame, list[dict], float]:
    if loaded.X.size == 0 or not loaded.channel_ids:
        return pd.DataFrame(), [], 0.0

    if loaded.X.shape != (len(loaded.channel_ids), len(loaded.t_sample_ns)):
        raise ValueError("numeric samples must have shape channels × timestamps")
    if not np.all(np.isfinite(loaded.X)):
        raise ValueError("numeric samples must be finite")
    if not all(math.isfinite(value) and value > 0 for value in (loaded.fs_hz, window_s, hop_s)):
        raise ValueError("numeric rate, window_s and hop_s must be finite and positive")
    t = np.asarray(loaded.t_sample_ns, dtype=np.int64)
    if np.any(t[1:] < t[:-1]):
        raise ValueError("numeric feature timestamps must be ordered")
    x_tc = loaded.X.T

    valid = validity_mask(loaded.t_sample_ns, gap_mask)
    enforce_gap_policy(gap_mask, valid)
    vf = valid_fraction(valid)

    fs = loaded.fs_hz
    win = max(1, int(round(window_s * fs)))
    hop = max(1, int(round(hop_s * fs)))
    n = x_tc.shape[0]
    rows: list[dict] = []
    boundaries = {0, n}
    if gap_mask.policy == "split":
        # Split even when a recorded gap contains no sample: validity alone
        # cannot detect the discontinuity between adjacent retained samples.
        for gap in gap_mask.overlaps_window():
            end = gap.end_session_ns
            if end is None:
                end = gap_mask.window.end_session_ns
            boundaries.add(int(np.searchsorted(t, gap.start_session_ns, side="left")))
            boundaries.add(int(np.searchsorted(t, end, side="right")))
    ordered = sorted(boundaries)
    for run_start, run_end in zip(ordered, ordered[1:], strict=False):
        for start in range(run_start, run_end - win + 1, hop):
            end = start + win
            vchunk = valid[start:end]
            if not vchunk.any():
                continue
            good = x_tc[start:end][vchunk]
            row = {
                "t_start_ns": int(t[start]),
                "t_end_ns": int(t[end - 1]) + round(1e9 / fs),
                "rate_hz": float(fs),
                "gap_fraction": float(1.0 - vchunk.mean()),
            }
            for i, name in enumerate(loaded.channel_ids):
                col = good[:, i].astype(np.float64, copy=False)
                scale = float(np.max(np.abs(col)))
                # Scaling prevents overflow/underflow in squares and sums for
                # finite float64 recordings without discarding their magnitude.
                normalized = col / scale if scale else col
                row[f"{name}_rms"] = scale * float(np.sqrt(np.mean(normalized * normalized)))
                row[f"{name}_mean"] = scale * float(np.mean(normalized))
            rows.append(row)

    meta = []
    columns = [
        ("t_start_ns", "ns"),
        ("t_end_ns", "ns"),
        ("rate_hz", "Hz"),
        ("gap_fraction", "1"),
    ]
    for name in loaded.channel_ids:
        columns.extend([(f"{name}_rms", loaded.units), (f"{name}_mean", loaded.units)])
    for name, units in columns:
        meta.append(
            {
                "name": name,
                "units": units,
                "id": "numeric.basic.v1",
                "provisional": True,
                "calibrated": False,
                "timestampMethod": "mcap-first-datum+device-delta-or-nominal-rate",
                "interpolatedTimestamps": any(
                    flag & (1 << 3) for flag in loaded.batch_quality_flags
                ),
            }
        )
    return pd.DataFrame(rows), meta, vf
