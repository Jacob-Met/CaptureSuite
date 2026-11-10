# SPDX-License-Identifier: GPL-3.0-only
"""IMU windowed features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from capture_analysis.sample_windows import elapsed_sample_windows, expected_samples
from capture_analysis.types import GapMask, LoadedImu
from capture_analysis.windows import enforce_gap_policy, valid_fraction, validity_mask


def extract_imu_features(
    loaded: LoadedImu,
    gap_mask: GapMask,
    *,
    window_s: float = 0.20,
    hop_s: float = 0.10,
    nominal_rate_hz: float,
) -> tuple[pd.DataFrame, list[dict], float]:
    if loaded.t_frame_ns.size == 0:
        return pd.DataFrame(), [], 0.0

    valid = validity_mask(loaded.t_frame_ns, gap_mask)
    enforce_gap_policy(gap_mask, valid)
    vf = valid_fraction(valid)

    rows: list[dict] = []
    for window in elapsed_sample_windows(
        loaded.t_frame_ns,
        valid,
        gap_mask,
        rate_hz=nominal_rate_hz,
        window_s=window_s,
        hop_s=hop_s,
    ):
        i0, i1 = window.first, window.stop
        v = valid[i0:i1]
        if not np.any(v):
            continue
        t_mid = int(np.median(loaded.t_frame_ns[i0:i1][v]))
        row: dict = {
            "t_start_ns": window.start_ns,
            "t_end_ns": window.end_ns,
            "t_mid_ns": t_mid,
            "expected_frame_count": expected_samples(
                window.start_ns, window.end_ns, nominal_rate_hz,
                origin_ns=window.grid_origin_ns,
            ),
            "valid_fraction": float(np.mean(v)),
            "window_frame_count": int(i1 - i0),
        }
        for s, sid in enumerate(loaded.sensor_ids):
            # Missing sensors are NaN-padded by the loader. Keep accelerometer
            # and gyro support separate, and use one complete-vector population
            # for every statistic from a measurement, including its axes.
            a_raw = loaded.accel[i0:i1, s]
            g_raw = loaded.gyro[i0:i1, s]
            a_valid = v & np.isfinite(a_raw).all(axis=1)
            g_valid = v & np.isfinite(g_raw).all(axis=1)
            a = a_raw[a_valid].astype(np.float64, copy=False)
            g = g_raw[g_valid].astype(np.float64, copy=False)
            for measurement, supported in (("acc", a_valid), ("gyro", g_valid)):
                row[f"{sid}_{measurement}_sample_count"] = int(np.sum(supported))
                row[f"{sid}_{measurement}_valid_fraction"] = float(np.mean(supported))
            # No observations means unknown, never a fabricated zero reading.
            mag = np.linalg.norm(a, axis=1)
            gmag = np.linalg.norm(g, axis=1)
            row[f"{sid}_acc_mag_mean"] = float(np.mean(mag)) if mag.size else np.nan
            row[f"{sid}_acc_mag_std"] = float(np.std(mag)) if mag.size else np.nan
            row[f"{sid}_gyro_mag_mean"] = float(np.mean(gmag)) if gmag.size else np.nan
            for axis, name in enumerate("xyz"):
                row[f"{sid}_acc_{name}_mean"] = (
                    float(np.mean(a[:, axis])) if a.size else np.nan
                )
                row[f"{sid}_acc_{name}_std"] = (
                    float(np.std(a[:, axis])) if a.size else np.nan
                )
        rows.append(row)

    df = pd.DataFrame(rows)
    meta = [
        {"name": "t_start_ns", "units": "ns", "calibrated": True,
         "description": "Inclusive elapsed-session-time window start."},
        {"name": "t_end_ns", "units": "ns", "calibrated": True,
         "description": "Exclusive elapsed-session-time window end."},
        {"name": "expected_frame_count", "units": "count", "calibrated": False,
         "description": "Nominal frame positions in the elapsed window; not clock calibration."},
        {"name": "t_mid_ns", "units": "ns", "calibrated": True},
        {
            "name": "valid_fraction", "units": "1", "calibrated": True,
            "description": "Fraction of retained frames outside declared gaps; not sensor support.",
        },
        {
            "name": "window_frame_count", "units": "count", "calibrated": True,
            "description": "Retained frame slots in this window, including masked frames.",
        },
    ]
    units = loaded.units or "a.u."
    for sid in loaded.sensor_ids:
        for measurement in ("acc", "gyro"):
            for suffix, unit, description in (
                (
                    "sample_count", "count",
                    "Finite 3-axis vectors outside declared gaps used by this measurement.",
                ),
                (
                    "valid_fraction", "1",
                    "Used vectors divided by window_frame_count; not elapsed-time coverage.",
                ),
            ):
                meta.append({
                    "name": f"{sid}_{measurement}_{suffix}", "units": unit,
                    "calibrated": True, "description": description,
                })
        for name in (
            "acc_mag_mean",
            "acc_mag_std",
            "gyro_mag_mean",
            "acc_x_mean",
            "acc_x_std",
            "acc_y_mean",
            "acc_y_std",
            "acc_z_mean",
            "acc_z_std",
        ):
            meta.append(
                {"name": f"{sid}_{name}", "units": units, "calibrated": False}
            )
    return df, meta, vf
