# IMU feature timestamps

Each row returned by `extract_imu_features` keeps the existing `t_mid_ns`
window marker: the median of frame timestamps admitted by that window's gap
and time-window mask. This marker is stored as integer nanoseconds.

The calculation preserves the full signed 64-bit timestamp range used by the
recorded timing header. An odd frame count uses the exact central timestamp.
An even count uses the exact arithmetic mean of the two central timestamps,
truncating a fractional nanosecond toward zero. For example, `[-3, -2]`
produces `-2`, and `[0, 1]` produces `0`. The two central values are added as
Python integers, avoiding both signed-int64 overflow and float64 rounding.

The median remains a window marker. With an even count it can fall between
recorded frames or inside a masked gap, as it did before this precision repair.
Window and hop selection, gap policy, valid fractions, sensor statistics and
feature metadata are unchanged. The calculation leaves input arrays intact.
Previously retained results stay unchanged; rerun an analysis explicitly to
produce new feature results with the repaired calculation.

## Focused verification

From a configured CaptureSuite development environment:

```console
python -m pytest tests/analysis/test_imu_feature_timestamps.py -q
```

The test file is also a standard-library `unittest` suite. With the repository's
Python package paths set, it runs without pytest:

```console
python -m unittest discover -s tests/analysis -p test_imu_feature_timestamps.py -v
```

The suite calls the public extractor and covers odd and even medians, duplicate
and unsorted timestamp inputs, signed limits, negative pre-T0 times, short
windows, gaps, empty inputs and unchanged non-time feature values. Numerical
tests inspect the timestamp column directly, preserving its integer dtype.

Source and original/candidate receiving details are in
[the precision receiving record](receiving/imu-timestamps-d788ccfb3bfe/README.md).
