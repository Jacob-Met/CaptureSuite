# SPDX-License-Identifier: GPL-3.0-only
"""EMG windowed features (provisional defaults until real Delsys data)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from capture_analysis.sample_windows import (
    elapsed_sample_windows,
    expected_samples,
    sample_coverage,
)
from capture_analysis.types import GapMask, LoadedEmg
from capture_analysis.windows import enforce_gap_policy, validity_mask


def extract_emg_features(
    loaded: LoadedEmg,
    gap_mask: GapMask,
    *,
    window_s: float = 0.100,
    hop_s: float = 0.050,
) -> tuple[pd.DataFrame, list[dict], float]:
    valid = validity_mask(loaded.t_sample_ns, gap_mask)
    enforce_gap_policy(gap_mask, valid)
    if loaded.X.size == 0 or not loaded.channel_ids:
        return pd.DataFrame(), [], 0.0

    fs = loaded.fs_hz
    rows: list[dict] = []
    x = loaded.X
    t = np.asarray(loaded.t_sample_ns, dtype=np.int64)
    vf = sample_coverage(t, valid, fs)

    for window in elapsed_sample_windows(
        t,
        valid,
        gap_mask,
        rate_hz=fs,
        window_s=window_s,
        hop_s=hop_s,
    ):
        i0, i1 = window.first, window.stop
        v = valid[i0:i1]
        pairs = v[:-1] & v[1:]
        times = t[i0:i1]
        for gap in gap_mask.overlaps_window():
            end = gap.end_session_ns
            if end is None:
                end = gap_mask.window.end_session_ns
            # A declared missing interval can contain no stored samples at all.
            pairs &= ~((times[:-1] <= end) & (times[1:] >= gap.start_session_ns))
        triples = pairs[:-1] & pairs[1:]
        seg = x[:, i0:i1][:, v]
        expected = expected_samples(
            window.start_ns,
            window.end_ns,
            fs,
            origin_ns=window.grid_origin_ns,
        )
        valid_count = int(np.count_nonzero(v))
        row: dict = {
            "t_start_ns": window.start_ns,
            "t_end_ns": window.end_ns,
            "t_mid_ns": int(np.median(times[v])),
            "sample_count": i1 - i0,
            "valid_sample_count": valid_count,
            "expected_sample_count": expected,
            "valid_fraction": valid_count / max(expected, i1 - i0),
        }
        for c, ch in enumerate(loaded.channel_ids):
            s = seg[c].astype(np.float64, copy=False)
            # Temporal features require adjacent observed samples. Filtering first
            # would join opposite sides of a gap and invent transitions.
            full = x[c, i0:i1].astype(np.float64, copy=False)
            diff = np.diff(full)
            zc = int(np.sum(((full[:-1] * full[1:]) < 0) & pairs))
            ssc = int(np.sum(((diff[:-1] * diff[1:]) < 0) & triples))
            row[f"{ch}_rms"] = float(np.sqrt(np.mean(s * s)))
            row[f"{ch}_mav"] = float(np.mean(np.abs(s)))
            row[f"{ch}_wl"] = float(np.sum(np.abs(diff[pairs]))) if diff.size else 0.0
            row[f"{ch}_zc"] = zc
            row[f"{ch}_ssc"] = ssc
        rows.append(row)

    df = pd.DataFrame(rows)
    meta: list[dict] = [
        {"name": name, "units": units, "calibrated": calibrated}
        for name, units, calibrated in (
            ("t_start_ns", "ns", True),
            ("t_end_ns", "ns", True),
            ("t_mid_ns", "ns", True),
            ("sample_count", "count", True),
            ("valid_sample_count", "count", True),
            ("expected_sample_count", "count", False),
            ("valid_fraction", "1", False),
        )
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
            meta.append({"name": f"{ch}_{suffix}", "units": u, "calibrated": cal})
    for column in meta:
        column.update(
            {
                "id": "emg.windowed.v2",
                "windowSemantics": "elapsed_session_time",
                "windowNs": int(round(window_s * 1e9)),
                "hopNs": int(round(hop_s * 1e9)),
            }
        )
    return df, meta, vf


def analytic_rms(amplitude: float) -> float:
    return float(amplitude / np.sqrt(2.0))


def analytic_mav(amplitude: float) -> float:
    return float(2.0 * amplitude / np.pi)
