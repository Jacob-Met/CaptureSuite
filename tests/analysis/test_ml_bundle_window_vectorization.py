# SPDX-License-Identifier: GPL-3.0-only
"""The fast ML bundle window median must retain the original inclusive-window values."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest
from capture_analysis.ml_bundle.job import (
    DEFAULT_TARGET_COLUMNS,
    _window_target_medians,
)


def _pandas_reference(frame: pd.DataFrame, centers: list[int], half_window_ns: int):
    times = frame["session_time_ns"].to_numpy(dtype=np.int64)
    expected_valid = []
    expected_targets = []
    for center in centers:
        selected = frame.loc[
            (times >= center - half_window_ns) & (times <= center + half_window_ns)
        ]
        if selected.empty:
            expected_valid.append(False)
            expected_targets.append([float("nan")] * len(DEFAULT_TARGET_COLUMNS))
        else:
            expected_valid.append(
                bool(selected["valid_elbow_L"].all() and selected["valid_elbow_R"].all())
            )
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="All-NaN slice encountered", category=RuntimeWarning
                )
                warnings.filterwarnings(
                    "ignore", message="Mean of empty slice", category=RuntimeWarning
                )
                expected_targets.append(
                    [float(selected[c].median()) for c in DEFAULT_TARGET_COLUMNS]
                )
    return np.asarray(expected_valid, dtype=np.bool_), np.asarray(
        expected_targets, dtype=np.float64
    )


def _check(frame: pd.DataFrame, centers: list[int], half_window_ns: int):
    original = frame.copy(deep=True)
    times = frame["session_time_ns"].to_numpy(dtype=np.int64)
    actual_valid, actual_targets = _window_target_medians(
        frame, times, centers, half_window_ns, DEFAULT_TARGET_COLUMNS
    )
    expected_valid, expected_targets = _pandas_reference(frame, centers, half_window_ns)
    np.testing.assert_array_equal(actual_valid, expected_valid)
    np.testing.assert_array_equal(actual_targets, expected_targets)
    pd.testing.assert_frame_equal(frame, original, check_exact=True)


@pytest.mark.parametrize("seed", range(32))
def test_randomized_out_of_order_duplicates_gaps_and_missing_values(seed):
    rng = np.random.default_rng(seed)
    count = int(rng.integers(2, 110))
    # Duplicate and irregular intervals; permute to exercise slow input import.
    times = np.cumsum(rng.integers(0, 7, size=count, dtype=np.int64))
    if seed % 2:
        times = rng.permutation(times)
    frame = pd.DataFrame(
        {
            "session_time_ns": times,
            "valid_elbow_L": pd.array(
                rng.choice([True, False, None], size=count, p=[0.7, 0.2, 0.1]),
                dtype="boolean",
            ),
            "valid_elbow_R": pd.array(
                rng.choice([True, False, None], size=count, p=[0.7, 0.2, 0.1]),
                dtype="boolean",
            ),
        }
    )
    for col in DEFAULT_TARGET_COLUMNS:
        values = rng.normal(0, 200, count)
        values[rng.random(count) < 0.18] = np.nan
        frame[col] = values
    centers = rng.integers(-3, int(times.max()) + 5, size=95).tolist()
    for half in (0, 1, 2, 5, 12):
        _check(frame, centers, half)


@pytest.mark.parametrize("edge", ["minimum", "maximum"])
def test_int64_boundaries_do_not_overflow_inclusive_time_windows(edge):
    bound = np.iinfo(np.int64).min if edge == "minimum" else np.iinfo(np.int64).max
    anchor = int(bound) + 10 if edge == "minimum" else int(bound) - 10
    frame = pd.DataFrame(
        {
            "session_time_ns": np.asarray([anchor - 7, anchor, anchor + 7], dtype=np.int64),
            "valid_elbow_L": [True, False, True],
            "valid_elbow_R": [True, True, True],
        }
    )
    for ci, col in enumerate(DEFAULT_TARGET_COLUMNS):
        frame[col] = np.asarray([ci + 1.0, ci + 2.0, np.nan])
    _check(frame, [anchor - 7, anchor, anchor + 7], 20)


def test_all_nan_target_and_missing_flags_keep_window_semantics():
    frame = pd.DataFrame(
        {
            "session_time_ns": np.asarray([0, 0, 5, 10, 40], dtype=np.int64),
            "valid_elbow_L": pd.array([True, None, True, True, False], dtype="boolean"),
            "valid_elbow_R": pd.array([None, True, True, False, True], dtype="boolean"),
        }
    )
    for ci, col in enumerate(DEFAULT_TARGET_COLUMNS):
        frame[col] = [np.nan, np.nan, np.nan, ci + 5.0, ci + 10.0]
    _check(frame, [-1, 0, 1, 5, 10, 11, 20, 39, 40, 41], 1)
