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
    dt = np.diff(t.astype(np.float64))
    dt_s = dt / 1e9
    fps_inst = np.where(dt_s > 0, 1.0 / dt_s, np.nan)
    df = pd.DataFrame(
        {
            "t_ns": t[1:],
            "dt_s": dt_s,
            "fps_inst": fps_inst,
            "valid": valid[1:].astype(np.int8),
        }
    )
    summary = {
        "frame_count": int(t.size),
        "fps_median": float(np.nanmedian(fps_inst)),
        "dt_p50_s": float(np.nanpercentile(dt_s, 50)),
        "dt_p95_s": float(np.nanpercentile(dt_s, 95)),
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
