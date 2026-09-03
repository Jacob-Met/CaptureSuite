# SPDX-License-Identifier: GPL-3.0-only
"""Online FMCW radar frame features (streaming; ADC counts)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from capture_analysis.loaders.radar_frame import iter_radar_frames
from capture_analysis.types import GapMask, StreamRef, TimeWindow
from capture_analysis.windows import enforce_gap_policy, valid_fraction, validity_mask


def extract_radar_frame_features(
    stream: StreamRef,
    window: TimeWindow,
    gap_mask: GapMask,
    *,
    derived_dir: Path | None = None,
    store_rd_every_n_frames: int = 30,
) -> tuple[pd.DataFrame, list[dict], float, list[str]]:
    times: list[int] = []
    energy: list[float] = []
    peak_bin: list[int] = []
    warnings: list[str] = [
        "radar timing is host-arrival; not a hardware-sync claim",
        "feature units are ADC counts (calibrated=false)",
    ]
    frame_i = 0
    mid_cube: np.ndarray | None = None
    mid_t = 0

    for item in iter_radar_frames(stream, window):
        cube = item.cube.astype(np.float64, copy=False)
        e = float(np.mean(cube * cube))
        # Range profile: mean over chirps and RX
        profile = np.mean(cube, axis=(0, 1))
        times.append(item.t_ns)
        energy.append(e)
        peak_bin.append(int(np.argmax(profile)))
        if mid_cube is None or abs(item.t_ns - (window.start_session_ns + window.end_session_ns) // 2) < abs(
            mid_t - (window.start_session_ns + window.end_session_ns) // 2
        ):
            mid_cube = item.cube
            mid_t = item.t_ns
        if derived_dir is not None and store_rd_every_n_frames > 0:
            if frame_i % store_rd_every_n_frames == 0:
                # Simple RD: FFT along chirps of mean-RX slow-time
                mean_rx = np.mean(cube, axis=0)  # chirps x samples
                mean_rx = mean_rx - np.mean(mean_rx, axis=0, keepdims=True)
                windowed = mean_rx * np.hanning(mean_rx.shape[0])[:, None]
                rd = np.fft.fftshift(np.fft.fft(windowed, axis=0), axes=0)
                mag = np.abs(rd).astype(np.float32)
                derived_dir.mkdir(parents=True, exist_ok=True)
                np.save(derived_dir / f"range_doppler_f{frame_i:06d}.npy", mag)
        frame_i += 1

    if not times:
        return pd.DataFrame(), [], 0.0, warnings

    t = np.asarray(times, dtype=np.int64)
    valid = validity_mask(t, gap_mask)
    enforce_gap_policy(gap_mask, valid)
    vf = valid_fraction(valid)
    df = pd.DataFrame(
        {
            "t_ns": t,
            "energy": np.asarray(energy, dtype=np.float64),
            "peak_range_bin": np.asarray(peak_bin, dtype=np.int32),
            "valid": valid.astype(np.int8),
        }
    )
    if derived_dir is not None and mid_cube is not None:
        derived_dir.mkdir(parents=True, exist_ok=True)
        np.save(derived_dir / "range_profile_mid.npy", np.mean(mid_cube.astype(np.float64), axis=(0, 1)))

    meta = [
        {"name": "t_ns", "units": "ns", "calibrated": True},
        {"name": "energy", "units": "adc_counts^2", "calibrated": False},
        {"name": "peak_range_bin", "units": "bin", "calibrated": False},
        {"name": "valid", "units": "bool", "calibrated": True},
    ]
    return df, meta, vf, warnings
