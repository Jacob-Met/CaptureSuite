# SPDX-License-Identifier: GPL-3.0-only
"""Elapsed-session-time windows for retained signal samples.

A missing interval must not disappear when batches are concatenated. Window
bounds are half-open; raw sample timestamps and values are never resampled.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from capture_analysis.types import GapMask


@dataclass(frozen=True)
class SampleWindow:
    start_ns: int
    end_ns: int
    first: int
    stop: int
    grid_origin_ns: int


def expected_samples(
    start_ns: int,
    end_ns: int,
    rate_hz: float,
    *,
    origin_ns: int | None = None,
) -> int:
    """Count nominal positions on the same phase/period as the EMG loader.

    Counting positions, rather than rounding duration * rate independently for
    each row, preserves full coverage for clean non-integer window sample counts.
    This is a nominal availability estimate, not device-clock calibration.
    """
    origin = start_ns if origin_ns is None else origin_ns
    period = max(1, int(round(1e9 / rate_hz)))
    first = (start_ns - origin + period - 1) // period
    stop = (end_ns - origin + period - 1) // period
    return max(1, stop - first)


def sample_coverage(
    times: np.ndarray,
    valid: np.ndarray,
    rate_hz: float,
) -> float:
    """Valid retained samples / nominal positions across the observed time span."""
    if not len(times):
        return 0.0
    end = int(times[-1]) + max(1, int(round(1e9 / rate_hz)))
    expected = expected_samples(int(times[0]), end, rate_hz)
    return float(np.count_nonzero(valid) / max(expected, len(times)))


def elapsed_sample_windows(
    times: np.ndarray,
    valid: np.ndarray,
    gap_mask: GapMask,
    *,
    rate_hz: float,
    window_s: float,
    hop_s: float,
    include_short: bool = True,
) -> Iterator[SampleWindow]:
    """Yield time-bounded sample slices, omitting windows with no valid samples.

    Mask keeps a fixed elapsed-time grid anchored to the first retained sample.
    Split restarts that grid in each declared gap-free span. A span shorter than
    one window is retained only when include_short is requested, with its actual
    bounds. Long empty intervals are jumped over, not expanded sample by sample.
    """
    if not all(math.isfinite(v) and v > 0 for v in (rate_hz, window_s, hop_s)):
        raise ValueError("rate, window_s and hop_s must be finite and positive")
    t = np.asarray(times, dtype=np.int64)
    if t.size == 0:
        return
    if valid.shape != t.shape or np.any(t[1:] < t[:-1]):
        raise ValueError("feature timestamps must be ordered and match the validity mask")
    width = max(1, int(round(window_s * 1e9)))
    hop = max(1, int(round(hop_s * 1e9)))
    period = max(1, int(round(1e9 / rate_hz)))
    first_time, final_time = int(t[0]), int(t[-1]) + period
    spans = [(first_time, final_time)]
    if gap_mask.policy == "split":
        spans = []
        cursor = first_time
        for gap in sorted(gap_mask.overlaps_window(), key=lambda g: g.start_session_ns):
            stop = gap.end_session_ns
            if stop is None:
                stop = gap_mask.window.end_session_ns
            # Gap endpoints are inclusive, as in validity_mask.
            left, right = max(first_time, gap.start_session_ns), min(final_time, stop + 1)
            if right <= cursor or left >= final_time:
                continue
            if left > cursor:
                spans.append((cursor, left))
            cursor = max(cursor, right)
        if cursor < final_time:
            spans.append((cursor, final_time))

    good_times = t[valid]
    if not len(good_times):
        return
    for span_start, span_end in spans:
        first = int(np.searchsorted(t, span_start, side="left"))
        stop = int(np.searchsorted(t, span_end, side="left"))
        if first >= stop:
            continue
        anchor = int(t[first])
        end = min(span_end, int(t[stop - 1]) + period)
        if end - anchor < width:
            if include_short and np.any(valid[first:stop]):
                yield SampleWindow(anchor, end, first, stop, anchor)
            continue
        last_k = (end - anchor - width) // hop
        k = 0
        while k <= last_k:
            left = anchor + k * hop
            right = left + width
            good_first = int(np.searchsorted(good_times, left, side="left"))
            good_stop = int(np.searchsorted(good_times, right, side="left"))
            if good_first == good_stop:
                if good_first == len(good_times):
                    break
                # Find the first later window that could contain the next datum.
                next_time = int(good_times[good_first])
                k = max(k + 1, (next_time - anchor - width) // hop + 1)
                continue
            yield SampleWindow(
                left,
                right,
                int(np.searchsorted(t, left, side="left")),
                int(np.searchsorted(t, right, side="left")),
                anchor,
            )
            k += 1
