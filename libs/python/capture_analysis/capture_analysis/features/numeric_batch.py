# SPDX-License-Identifier: GPL-3.0-only
"""Basic QC features for generic.numeric_batch/1 streams."""

from __future__ import annotations

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

    # X may be channels×time or time×channels; normalize to time×channels.
    x = loaded.X
    if x.ndim == 2 and x.shape[0] == len(loaded.channel_ids):
        x_tc = x.T
    else:
        x_tc = x

    valid = validity_mask(loaded.t_sample_ns, gap_mask)
    enforce_gap_policy(gap_mask, valid)
    vf = valid_fraction(valid)

    fs = loaded.fs_hz or 1.0
    win = max(1, int(round(window_s * fs)))
    hop = max(1, int(round(hop_s * fs)))
    n = x_tc.shape[0]
    rows: list[dict] = []
    t0 = int(loaded.t_sample_ns[0]) if len(loaded.t_sample_ns) else 0
    start = 0
    while start + win <= n:
        end = start + win
        chunk = x_tc[start:end]
        vchunk = valid[start:end] if len(valid) >= end else np.ones(win, dtype=bool)
        if vchunk.any():
            good = chunk[vchunk]
            row = {
                "t_start_ns": t0 + int(start * 1e9 / fs),
                "t_end_ns": t0 + int(end * 1e9 / fs),
                "rate_hz": float(fs),
                "gap_fraction": float(1.0 - vchunk.mean()),
            }
            for i, name in enumerate(loaded.channel_ids):
                col = good[:, i] if good.ndim == 2 and good.shape[1] > i else good
                row[f"{name}_rms"] = float(np.sqrt(np.mean(np.square(col)))) if col.size else 0.0
                row[f"{name}_mean"] = float(np.mean(col)) if col.size else 0.0
            rows.append(row)
        start += hop

    return pd.DataFrame(rows), [{"id": "numeric.basic.v1", "provisional": True}], vf
