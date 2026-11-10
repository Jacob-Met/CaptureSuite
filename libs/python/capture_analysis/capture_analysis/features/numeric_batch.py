# SPDX-License-Identifier: GPL-3.0-only
"""Basic QC features for generic.numeric_batch/1 streams."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from capture_analysis.sample_windows import (
    elapsed_sample_windows,
    expected_samples,
    sample_coverage,
)
from capture_analysis.types import GapMask, LoadedEmg
from capture_analysis.windows import enforce_gap_policy, validity_mask


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
    vf = sample_coverage(t, valid, loaded.fs_hz)

    fs = loaded.fs_hz
    rows: list[dict] = []
    for window in elapsed_sample_windows(
        t, valid, gap_mask, rate_hz=fs, window_s=window_s, hop_s=hop_s
    ):
        first, stop = window.first, window.stop
        vchunk = valid[first:stop]
        good = x_tc[first:stop][vchunk]
        expected = expected_samples(
            window.start_ns, window.end_ns, fs, origin_ns=window.grid_origin_ns
        )
        valid_count = int(np.count_nonzero(vchunk))
        coverage = valid_count / max(expected, stop - first)
        row = {
            "t_start_ns": window.start_ns,
            "t_end_ns": window.end_ns,
            "rate_hz": float(fs),
            "sample_count": stop - first,
            "valid_sample_count": valid_count,
            "expected_sample_count": expected,
            "valid_fraction": coverage,
            "gap_fraction": 1.0 - coverage,
        }
        for i, name in enumerate(loaded.channel_ids):
            col = good[:, i].astype(np.float64, copy=False)
            scale = float(np.max(np.abs(col)))
            # Scaling preserves the magnitude of finite float64 recordings.
            normalized = col / scale if scale else col
            row[f"{name}_rms"] = scale * float(np.sqrt(np.mean(normalized * normalized)))
            row[f"{name}_mean"] = scale * float(np.mean(normalized))
        rows.append(row)

    meta = []
    columns = [
        ("t_start_ns", "ns"),
        ("t_end_ns", "ns"),
        ("rate_hz", "Hz"),
        ("sample_count", "count"),
        ("valid_sample_count", "count"),
        ("expected_sample_count", "count"),
        ("valid_fraction", "1"),
        ("gap_fraction", "1"),
    ]
    for name in loaded.channel_ids:
        columns.extend([(f"{name}_rms", loaded.units), (f"{name}_mean", loaded.units)])
    for name, units in columns:
        meta.append(
            {
                "name": name,
                "units": units,
                "id": "numeric.basic.v2",
                "windowSemantics": "elapsed_session_time",
                "windowNs": int(round(window_s * 1e9)),
                "hopNs": int(round(hop_s * 1e9)),
                "coverageMethod": "valid-retained/nominal-rate-positions",
                "provisional": True,
                "calibrated": False,
                "timestampMethod": "mcap-first-datum+device-delta-or-nominal-rate",
                "interpolatedTimestamps": any(
                    flag & (1 << 3) for flag in loaded.batch_quality_flags
                ),
            }
        )
    return pd.DataFrame(rows), meta, vf
