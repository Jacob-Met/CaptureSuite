#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Independent public-extractor witness using an exact rational oracle."""
from __future__ import annotations

import hashlib
import json
import random
import sys
from fractions import Fraction
from pathlib import Path

root = Path(sys.argv[1]).resolve()
for package in ('capture_protocol', 'capture_session', 'capture_analysis'):
    sys.path.insert(0, str(root / 'libs/python' / package))

import numpy as np
from capture_analysis.features.imu import extract_imu_features
from capture_analysis.types import GapMask, LoadedImu, StreamRef, TimeWindow

def median(values):
    ordered = sorted(int(value) for value in values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return int(Fraction(ordered[middle - 1] + ordered[middle], 2))

rng = random.Random(20261012)
extremes = [-(1 << 63), -(1 << 63) + 1, -(1 << 53) - 1,
            -(1 << 53), -3, -2, -1, 0, 1, 2, 3, (1 << 53),
            (1 << 53) + 1, (1 << 63) - 2, (1 << 63) - 1]
cases = [[value] for value in extremes]
cases.extend([[a, b] for a in extremes for b in extremes])
for trial in range(272):
    count = 1 + trial % 64
    values = [rng.choice(extremes) if rng.randrange(2) else
              rng.randrange(-(1 << 63), 1 << 63) for _ in range(count)]
    rng.shuffle(values)
    cases.append(values)

failures = []
for case, values in enumerate(cases):
    # A strided source detects accidental in-place selection as well.
    storage = np.empty(len(values) * 2, dtype=np.int64)
    storage[::2] = values
    storage[1::2] = 317
    times = storage[::2]
    count = len(values)
    before = storage.copy()
    vector = np.ones((count, 1, 3), dtype=np.float32)
    quat = np.ones((count, 1, 4), dtype=np.float32)
    loaded = LoadedImu(['sensor'], times, vector, vector.copy(), quat, 'a.u.')
    gap = GapMask(StreamRef('source', 'imu', 'imu', 'imu.frame/1', 1.0, 'a.u.'),
                  TimeWindow(min(values), max(values)), [], 'mask')
    frame, metadata, fraction = extract_imu_features(
        loaded, gap, window_s=count, hop_s=count, nominal_rate_hz=1.0)
    actual = int(frame.at[0, 't_mid_ns'])
    expected = median(values)
    if actual != expected or frame['t_mid_ns'].dtype != np.dtype('int64'):
        failures.append({'case': case, 'actual': actual, 'expected': expected,
                         'dtype': str(frame['t_mid_ns'].dtype)})
    if not np.array_equal(before, storage):
        raise RuntimeError(f'case {case}: source timestamps changed')
    if fraction != 1.0 or float(frame.at[0, 'sensor_acc_x_mean']) != 1.0:
        raise RuntimeError(f'case {case}: unchanged feature contract violated')

source = root / 'libs/python/capture_analysis/capture_analysis/features/imu.py'
print(json.dumps({'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                  'python': sys.version, 'numpy': np.__version__, 'oracle': 'sorted Python integers and Fraction, truncation toward zero',
                  'seed': 20261012, 'cases': len(cases), 'failures': len(failures),
                  'examples': failures[:8], 'input_unchanged': True,
                  'features_unchanged': True, 'optimized': not __debug__}, indent=2))
sys.exit(bool(failures))
