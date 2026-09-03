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

    for i0, i1 in _window_indices(x.shape[1], win, hop):
        v = valid[i0:i1]
        if not np.any(v):
            continue
        seg = x[:, i0:i1][:, v]
        t_mid = int(np.median(t[i0:i1][v]))
        row: dict = {
            "t_mid_ns": t_mid,
            "valid_fraction": float(np.mean(v)),
        }
        for c, ch in enumerate(loaded.channel_ids):
            s = seg[c].astype(np.float64, copy=False)
            if s.size == 0:
                continue
            diff = np.diff(s)
            zc = int(np.sum((s[:-1] * s[1:]) < 0)) if s.size > 1 else 0
            ssc = (
                int(np.sum((diff[:-1] * diff[1:]) < 0)) if diff.size > 1 else 0
            )
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
