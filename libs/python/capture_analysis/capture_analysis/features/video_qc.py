# SPDX-License-Identifier: GPL-3.0-only
"""Video timing QC features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from capture_analysis.loaders.video import LoadedVideoTiming
from capture_analysis.types import GapMask
from capture_analysis.windows import enforce_gap_policy, valid_fraction, validity_mask


def extract_video_qc(
    loaded: LoadedVideoTiming,
    gap_mask: GapMask,
    *,
    nominal_rate_hz: float,
) -> tuple[pd.DataFrame, list[dict], float, list[str]]:
    warnings = list(loaded.warnings)
    t = loaded.t_frame_ns
    if t.size < 2:
        return pd.DataFrame(), [], 0.0, warnings

    valid = validity_mask(t, gap_mask)
    enforce_gap_policy(gap_mask, valid)
    vf = valid_fraction(valid)
    # Same-sign int64 differences fit in int64. Crossing zero can span more
    # than that range, so use Python integers only for those pairs. Both paths
    # subtract before rounding to float, preserving small intervals at large T0.
    cross_zero = (t[:-1] < 0) != (t[1:] < 0)
    if np.any(cross_zero):
        dt_ns = np.zeros(t.size - 1, dtype=np.int64)
        np.subtract(t[1:], t[:-1], out=dt_ns, where=~cross_zero)
        dt = dt_ns.astype(np.float64)
        dt[cross_zero] = np.fromiter(
            (
                int(right) - int(left)
                for left, right in zip(t[:-1][cross_zero], t[1:][cross_zero], strict=True)
            ),
            dtype=np.float64,
            count=int(np.count_nonzero(cross_zero)),
        )
    else:
        dt = np.diff(t).astype(np.float64)
    dt_s = dt / 1e9
    connected = valid[:-1] & valid[1:]
    for gap in gap_mask.overlaps_window():
        end = gap.end_session_ns
        if end is None:
            end = gap_mask.window.end_session_ns
        if end < gap.start_session_ns:
            continue
        connected &= ~((t[:-1] <= end) & (t[1:] >= gap.start_session_ns))
    enforce_gap_policy(gap_mask, connected)
    interval_valid = connected & (dt_s > 0)
    fps_inst = np.full(dt_s.shape, np.nan)
    np.divide(1.0, dt_s, out=fps_inst, where=interval_valid)
    df = pd.DataFrame(
        {
            "t_ns": t[1:],
            "dt_s": dt_s,
            "fps_inst": fps_inst,
            "valid": interval_valid.astype(np.int8),
        }
    )
    usable_dt = dt_s[interval_valid]
    valid_intervals = int(np.count_nonzero(interval_valid))
    summary = {
        "frame_count": int(t.size),
        "interval_count": int(dt_s.size),
        "valid_interval_count": valid_intervals,
        "invalid_interval_count": int(dt_s.size) - valid_intervals,
        "fps_median": float(np.median(fps_inst[interval_valid])) if valid_intervals else None,
        "dt_p50_s": float(np.percentile(usable_dt, 50)) if valid_intervals else None,
        "dt_p95_s": float(np.percentile(usable_dt, 95)) if valid_intervals else None,
        "nominal_rate_hz": float(nominal_rate_hz),
    }
    meta = [
        {"name": "t_ns", "units": "ns", "calibrated": True},
        {"name": "dt_s", "units": "s", "calibrated": True},
        {"name": "fps_inst", "units": "Hz", "calibrated": True},
        {"name": "valid", "units": "bool", "calibrated": True},
    ]
    # Attach summary as attrs via a one-row sidecar handled by caller through warnings/json
    warnings.append(f"video_qc_summary={summary}")
    return df, meta, vf, warnings
