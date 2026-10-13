# SPDX-License-Identifier: GPL-3.0-only
"""Exact signed-nanosecond timestamps through the public IMU extractor."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from capture_analysis.features.imu import extract_imu_features
from capture_analysis.types import GapInterval, GapMask, LoadedImu, StreamRef, TimeWindow


class ImuFeatureTimestampTests(unittest.TestCase):
    def extract(self, timestamps, *, gaps=(), policy="mask", window_s=None, hop_s=None):
        times = np.asarray(timestamps, dtype=np.int64)
        count = len(times)
        accel = np.arange(count * 6, dtype=np.float32).reshape(count, 2, 3)
        gyro = accel / 2
        quat = np.ones((count, 2, 4), dtype=np.float32)
        loaded = LoadedImu(["left", "right"], times, accel, gyro, quat, "a.u.")
        window = TimeWindow(int(times.min()), int(times.max())) if count else TimeWindow(0, 0)
        mask = GapMask(
            StreamRef("source", "imu", "imu", "imu.frame/1", 1.0, "a.u."),
            window,
            list(gaps),
            policy,
        )
        originals = [array.copy() for array in (times, accel, gyro, quat)]
        result = extract_imu_features(
            loaded,
            mask,
            window_s=max(count, 1) if window_s is None else window_s,
            hop_s=max(count, 1) if hop_s is None else hop_s,
            nominal_rate_hz=1.0,
        )
        for original, current in zip(originals, (times, accel, gyro, quat), strict=True):
            np.testing.assert_array_equal(current, original)
        return result

    def test_odd_medians_keep_exact_recorded_integers(self):
        high = 1 << 53
        cases = [
            ([high + 1], high + 1),
            ([-high - 1], -high - 1),
            ([high + 1, high + 3, high + 5], high + 3),
            ([high + 5, high + 1, high + 3], high + 3),
            ([high + 3, high + 3, high + 1], high + 3),
            ([(1 << 63) - 1], (1 << 63) - 1),
            ([-(1 << 63)], -(1 << 63)),
            ([0], 0),
        ]
        for timestamps, expected in cases:
            with self.subTest(timestamps=timestamps):
                frame, _, _ = self.extract(timestamps)
                self.assertEqual(int(frame.at[0, "t_mid_ns"]), expected)
                self.assertEqual(frame["t_mid_ns"].dtype, np.dtype("int64"))

    def test_even_medians_average_without_float_or_int64_overflow(self):
        high = 1 << 53
        low = -(1 << 63)
        top = (1 << 63) - 1
        cases = [
            ([high + 1, high + 2], high + 1),
            ([high + 5, high + 3, high + 2, high + 1], high + 2),
            ([-high - 2, -high - 1], -high - 1),
            ([top - 1, top], top - 1),
            ([low, low + 1], low + 1),
            ([low, top], 0),
            ([-3, -2], -2),
            ([-1, 0], 0),
            ([0, 1], 0),
            ([10, 20, 30, 40], 25),
        ]
        for timestamps, expected in cases:
            with self.subTest(timestamps=timestamps):
                frame, _, _ = self.extract(timestamps)
                self.assertEqual(int(frame.at[0, "t_mid_ns"]), expected)
                self.assertEqual(frame["t_mid_ns"].dtype, np.dtype("int64"))

    def test_window_and_hop_selection_keep_feature_values(self):
        local = [0, 2, 4, 6, 8, 10, 12]
        offset = (1 << 53) + 1
        expected, expected_meta, expected_fraction = self.extract(local, window_s=3, hop_s=2)
        actual, actual_meta, actual_fraction = self.extract(
            [offset + value for value in local], window_s=3, hop_s=2
        )
        self.assertEqual([int(value) for value in actual["t_mid_ns"]],
                         [offset + 2, offset + 6, offset + 10])
        pd.testing.assert_frame_equal(
            actual.drop(columns="t_mid_ns"), expected.drop(columns="t_mid_ns")
        )
        self.assertEqual(actual_meta, expected_meta)
        self.assertEqual(actual_fraction, expected_fraction)
        self.assertEqual(actual_fraction, 1.0)

    def test_gap_mask_uses_only_valid_frames_and_keeps_statistics(self):
        offset = 1 << 53
        local_times = [1, 2, 3, 4, 5]
        local_gap = GapInterval("source", "imu", "disconnect", 3, 3, True)
        gap = GapInterval("source", "imu", "disconnect", offset + 3, offset + 3, True)
        expected, expected_meta, expected_fraction = self.extract(local_times, gaps=[local_gap])
        actual, actual_meta, actual_fraction = self.extract(
            [offset + value for value in local_times], gaps=[gap]
        )
        self.assertEqual(int(actual.at[0, "t_mid_ns"]), offset + 3)
        self.assertEqual(float(actual.at[0, "valid_fraction"]), 0.8)
        self.assertEqual(actual_fraction, 0.8)
        pd.testing.assert_frame_equal(
            actual.drop(columns="t_mid_ns"), expected.drop(columns="t_mid_ns")
        )
        self.assertEqual(actual_meta, expected_meta)
        self.assertEqual(actual_fraction, expected_fraction)

    def test_gap_fail_policy_still_refuses(self):
        gap = GapInterval("source", "imu", "disconnect", 2, 2, True)
        with self.assertRaisesRegex(RuntimeError, "gap_policy=fail"):
            self.extract([1, 2, 3], gaps=[gap], policy="fail")

    def test_empty_and_all_invalid_inputs_keep_existing_empty_results(self):
        empty, meta, fraction = self.extract([])
        self.assertTrue(empty.empty)
        self.assertEqual(meta, [])
        self.assertEqual(fraction, 0.0)
        gap = GapInterval("source", "imu", "disconnect", 1, 3, True)
        invalid, invalid_meta, invalid_fraction = self.extract([1, 2, 3], gaps=[gap])
        self.assertTrue(invalid.empty)
        self.assertEqual(invalid_fraction, 0.0)
        self.assertEqual(invalid_meta[0], {"name": "t_mid_ns", "units": "ns", "calibrated": True})

    def test_short_input_keeps_existing_partial_window(self):
        offset = (1 << 53) + 1
        frame, _, fraction = self.extract([offset, offset + 2], window_s=5, hop_s=2)
        self.assertEqual(len(frame), 1)
        self.assertEqual(int(frame.at[0, "t_mid_ns"]), offset + 1)
        self.assertEqual(fraction, 1.0)


if __name__ == "__main__":
    unittest.main()
