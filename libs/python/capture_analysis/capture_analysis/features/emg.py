# SPDX-License-Identifier: GPL-3.0-only
"""EMG windowed features (provisional defaults until real Delsys data)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from capture_analysis.types import GapMask, LoadedEmg
from capture_analysis.windows import enforce_gap_policy, valid_fraction, validity_mask


def _window_indices(n: int, win: int, hop: int) -> list[tuple[int, int]]:
    if n < win or win <= 0:
        return [(0, n)] if n > 0 else []
    out: list[tuple[int, int]] = []
    start = 0
    while start + win <= n:
        out.append((start, start + win))
        start += hop
    return out


def _uninterrupted_pairs(t: np.ndarray, valid: np.ndarray, gap_mask: GapMask) -> np.ndarray:
    """Adjacent retained samples must not span a recorded gap, even an empty one."""
    pairs = valid[:-1] & valid[1:]
    for gap in gap_mask.overlaps_window():
        end = gap.end_session_ns
        if end is None:
            end = gap_mask.window.end_session_ns
        pairs &= ~((t[:-1] <= end) & (t[1:] >= gap.start_session_ns))
    return pairs


def extract_emg_features(
    loaded: LoadedEmg,
    gap_mask: GapMask,
    *,
    window_s: float = 0.100,
    hop_s: float = 0.050,
) -> tuple[pd.DataFrame, list[dict], float]:
    if loaded.X.size == 0 or not loaded.channel_ids:
        return pd.DataFrame(), [], 0.0

    valid = validity_mask(loaded.t_sample_ns, gap_mask)
    enforce_gap_policy(gap_mask, valid)
    vf = valid_fraction(valid)

    fs = loaded.fs_hz
    win = max(1, int(round(window_s * fs)))
    hop = max(1, int(round(hop_s * fs)))
    rows: list[dict] = []
    x = loaded.X
    t = loaded.t_sample_ns
    continuous = _uninterrupted_pairs(t, valid, gap_mask)
    all_continuous = bool(np.all(continuous))

    for i0, i1 in _window_indices(x.shape[1], win, hop):
        v = valid[i0:i1]
        if not np.any(v):
            continue
        seg = x[:, i0:i1][:, v]
        pairs = continuous[i0:i1 - 1]
        uninterrupted = all_continuous or bool(np.all(pairs))
        if not uninterrupted:
            triples = pairs[:-1] & pairs[1:]
        t_mid = int(np.median(t[i0:i1][v]))
        row: dict = {
            "t_mid_ns": t_mid,
            "valid_fraction": float(np.mean(v)),
        }
        for c, ch in enumerate(loaded.channel_ids):
            s = seg[c].astype(np.float64, copy=False)
            if s.size == 0:
                continue
            if uninterrupted:
                diff = np.diff(s)
                zc = int(np.sum((s[:-1] * s[1:]) < 0)) if s.size > 1 else 0
                ssc = int(np.sum((diff[:-1] * diff[1:]) < 0)) if diff.size > 1 else 0
            else:
                original = x[c, i0:i1].astype(np.float64, copy=False)
                left, right = original[:-1][pairs], original[1:][pairs]
                diff = right - left
                zc = int(np.sum((left * right) < 0))
                before = original[:-2][triples]
                middle = original[1:-1][triples]
                after = original[2:][triples]
                ssc = int(np.sum(((middle - before) * (after - middle)) < 0))
            row[f"{ch}_rms"] = float(np.sqrt(np.mean(s * s)))
            row[f"{ch}_mav"] = float(np.mean(np.abs(s)))
            row[f"{ch}_wl"] = float(np.sum(np.abs(diff))) if diff.size else 0.0
            row[f"{ch}_zc"] = zc
            row[f"{ch}_ssc"] = ssc
        rows.append(row)

    df = pd.DataFrame(rows)
    meta: list[dict] = [
        {"name": "t_mid_ns", "units": "ns", "calibrated": True},
        {"name": "valid_fraction", "units": "1", "calibrated": True},
    ]
    units = loaded.units or "mV"
    for ch in loaded.channel_ids:
        for suffix, u, cal in (
            ("rms", units, False),
            ("mav", units, False),
            ("wl", units, False),
            ("zc", "count", True),
            ("ssc", "count", True),
        ):
            meta.append(
                {
                    "name": f"{ch}_{suffix}",
                    "units": u,
                    "calibrated": cal,
                }
            )
    return df, meta, vf


def analytic_rms(amplitude: float) -> float:
    return float(amplitude / np.sqrt(2.0))


def analytic_mav(amplitude: float) -> float:
    return float(2.0 * amplitude / np.pi)
