# SPDX-License-Identifier: GPL-3.0-only
"""Basic QC features for generic.numeric_batch/1 streams."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from capture_analysis.types import GapMask, LoadedEmg
from capture_analysis.windows import enforce_gap_policy, valid_fraction, validity_mask

DEFAULT_WINDOW_S = 1.0
DEFAULT_HOP_S = 0.5


def _window_sizes(fs: float, window_s: float, hop_s: float) -> tuple[int, int]:
    return max(1, int(round(window_s * fs))), max(1, int(round(hop_s * fs)))


def numeric_measurement_context(
    loaded: LoadedEmg,
    gap_mask: GapMask,
    *,
    window_s: float = DEFAULT_WINDOW_S,
    hop_s: float = DEFAULT_HOP_S,
) -> dict:
    """Record the estimator's actual slot settings, without inferring coverage."""
    win, hop = _window_sizes(loaded.fs_hz, window_s, hop_s)
    return {
        "schemaId": "capture.numeric_measurement_context/1",
        "methodId": "numeric.basic.v1",
        "sampleRateHz": float(loaded.fs_hz),
        "requestedWindowSeconds": float(window_s),
        "requestedHopSeconds": float(hop_s),
        "windowSampleSlots": win,
        "hopSampleSlots": hop,
        "nominalWindowSeconds": win / loaded.fs_hz,
        "nominalHopSeconds": hop / loaded.fs_hz,
        "rounding": "nearest-integer-ties-to-even-minimum-one",
        "windowPlacement": "retained-sample-slots-within-each-split-run",
        "interval": {
            "startColumn": "t_start_ns",
            "endColumn": "t_end_ns",
            "timebase": "session nanoseconds",
            "start": "first retained sample timestamp in the window",
            "end": "last retained sample timestamp plus rounded nominal sample period",
            "coverage": "bounds of retained sample slots, not continuous measured coverage",
        },
        "gapPolicy": gap_mask.policy,
        "sampleWeighting": "equal weight per valid retained sample; not time weighted",
        "mean": "arithmetic mean of valid retained sample values",
        "rms": "square root of the mean of squared valid retained sample values",
        "missingData": "samples in declared gaps are excluded; no values are interpolated",
        "rowContextColumns": [
            "t_start_ns",
            "t_end_ns",
            "rate_hz",
            "sample_count",
            "valid_sample_count",
            "gap_fraction",
        ],
    }


def extract_numeric_batch_features(
    loaded: LoadedEmg,
    gap_mask: GapMask,
    *,
    window_s: float = DEFAULT_WINDOW_S,
    hop_s: float = DEFAULT_HOP_S,
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
    vf = valid_fraction(valid)

    fs = loaded.fs_hz
    win, hop = _window_sizes(fs, window_s, hop_s)
    n = x_tc.shape[0]
    rows: list[dict] = []
    boundaries = {0, n}
    if gap_mask.policy == "split":
        # Split even when a recorded gap contains no sample: validity alone
        # cannot detect the discontinuity between adjacent retained samples.
        for gap in gap_mask.overlaps_window():
            end = gap.end_session_ns
            if end is None:
                end = gap_mask.window.end_session_ns
            boundaries.add(int(np.searchsorted(t, gap.start_session_ns, side="left")))
            boundaries.add(int(np.searchsorted(t, end, side="right")))
    ordered = sorted(boundaries)
    for run_start, run_end in zip(ordered, ordered[1:], strict=False):
        for start in range(run_start, run_end - win + 1, hop):
            end = start + win
            vchunk = valid[start:end]
            if not vchunk.any():
                continue
            good = x_tc[start:end][vchunk]
            row = {
                "t_start_ns": int(t[start]),
                "t_end_ns": int(t[end - 1]) + round(1e9 / fs),
                "rate_hz": float(fs),
                "sample_count": win,
                "valid_sample_count": int(vchunk.sum()),
                "gap_fraction": float(1.0 - vchunk.mean()),
            }
            for i, name in enumerate(loaded.channel_ids):
                col = good[:, i].astype(np.float64, copy=False)
                scale = float(np.max(np.abs(col)))
                # Scaling prevents overflow/underflow in squares and sums for
                # finite float64 recordings without discarding their magnitude.
                normalized = col / scale if scale else col
                row[f"{name}_rms"] = scale * float(np.sqrt(np.mean(normalized * normalized)))
                row[f"{name}_mean"] = scale * float(np.mean(normalized))
            rows.append(row)

    meta = []
    columns = [
        ("t_start_ns", "ns"),
        ("t_end_ns", "ns"),
        ("rate_hz", "Hz"),
        ("sample_count", "samples"),
        ("valid_sample_count", "samples"),
        ("gap_fraction", "1"),
    ]
    for name in loaded.channel_ids:
        columns.extend([(f"{name}_rms", loaded.units), (f"{name}_mean", loaded.units)])
    descriptions = {
        "t_start_ns": "First retained sample timestamp in the window, in session nanoseconds.",
        "t_end_ns": (
            "Last retained sample timestamp plus the rounded nominal sample period; "
            "this interval is not a claim of continuous measured coverage."
        ),
        "rate_hz": "Stream sample rate used to choose sample slots, not measured coverage.",
        "sample_count": "Retained sample slots in this window, including masked slots.",
        "valid_sample_count": "Samples actually used in the mean and RMS after gap masking.",
        "gap_fraction": "Fraction of retained sample slots excluded by declared gaps.",
    }
    for name, units in columns:
        description = descriptions.get(name)
        if description is None:
            description = (
                "Arithmetic mean of valid retained samples with equal sample weights."
                if name.endswith("_mean")
                else "Root mean square of valid retained samples with equal sample weights."
            )
        meta.append(
            {
                "name": name,
                "units": units,
                "description": description,
                "id": "numeric.basic.v1",
                "provisional": True,
                "calibrated": False,
                "timestampMethod": "mcap-first-datum+device-delta-or-nominal-rate",
                "interpolatedTimestamps": any(
                    flag & (1 << 3) for flag in loaded.batch_quality_flags
                ),
            }
        )
    return pd.DataFrame(rows), meta, vf
