# SPDX-License-Identifier: GPL-3.0-only
"""Online LTR11 Doppler features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from capture_analysis.loaders.radar_doppler import iter_radar_doppler
from capture_analysis.types import GapMask, StreamRef, TimeWindow
from capture_analysis.windows import enforce_gap_policy, valid_fraction, validity_mask


def extract_radar_doppler_features(
    stream: StreamRef,
    window: TimeWindow,
    gap_mask: GapMask,
) -> tuple[pd.DataFrame, list[dict], float, list[str]]:
    times: list[int] = []
    mag_mean: list[float] = []
    mag_max: list[float] = []
    peak_bin: list[int] = []
    motion: list[int] = []
    direction: list[int] = []
    warnings = [
        "radar timing is host-arrival; not a hardware-sync claim",
        "feature units are uncalibrated complex samples",
    ]

    for item in iter_radar_doppler(stream, window):
        mag = np.abs(item.z)
        spec = np.abs(np.fft.fft(item.z))
        times.append(item.t_ns)
        mag_mean.append(float(np.mean(mag)))
        mag_max.append(float(np.max(mag)))
        peak_bin.append(int(np.argmax(spec)))
        motion.append(1 if item.motion_detected else 0)
        direction.append(int(item.direction))

    if not times:
        return pd.DataFrame(), [], 0.0, warnings

    t = np.asarray(times, dtype=np.int64)
    valid = validity_mask(t, gap_mask)
    enforce_gap_policy(gap_mask, valid)
    vf = valid_fraction(valid)
    df = pd.DataFrame(
        {
            "t_ns": t,
            "mag_mean": mag_mean,
            "mag_max": mag_max,
            "peak_bin": peak_bin,
            "motion_detected": motion,
            "direction": direction,
            "valid": valid.astype(np.int8),
        }
    )
    meta = [
        {"name": "t_ns", "units": "ns", "calibrated": True},
        {"name": "mag_mean", "units": "a.u.", "calibrated": False},
        {"name": "mag_max", "units": "a.u.", "calibrated": False},
        {"name": "peak_bin", "units": "bin", "calibrated": False},
        {"name": "motion_detected", "units": "bool", "calibrated": True},
        {"name": "direction", "units": "enum", "calibrated": False},
        {"name": "valid", "units": "bool", "calibrated": True},
    ]
    return df, meta, vf, warnings
