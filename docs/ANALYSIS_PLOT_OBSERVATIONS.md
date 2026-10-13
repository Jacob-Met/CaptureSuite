# Observations in offline analysis figures

An isolated finite observation is still measured data. The generic series figure
and synchronization dashboard now show it as a small point when neither adjacent
observation is finite. Continuous runs keep their existing lines. Missing or
infinite observations remain breaks; the renderer does not interpolate across
them, replace them, or invent endpoint connections.

For example, the video cadence series `[10, NaN, 10]` has two valid observations.
Both appear as individual points, with no line through the missing middle value.
A single observed value is also visible. A wholly unavailable series creates no
data marks. A mixture of a continuous run and isolated values keeps the line for
the run and points for the isolated values. Existing colors, titles, units,
linewidths, gap shading, output paths and figure closing remain unchanged.

The change applies to `plot_series` and `plot_sync_dashboard`. It does not change
the separate EMG-channel or IMU-magnitude drawing conventions, feature extraction,
saved synchronization data, raw sessions, or desktop gallery behavior.

## Precise offsets on a relative time axis

All shared figure time conversion now subtracts an integer origin from integer
timestamps before conversion to floating-point seconds. Previously, conversion
of each absolute timestamp to float could erase short differences: near `2**60`
nanoseconds, offsets of 0, 100 and 200 ns became 0, 0 and 256 ns on the axis.
They now remain 0, 100 and 200 ns.

The common signed-int64 case uses a vectorized subtraction after checking that
both the inputs and their differences fit. Integer inputs or origins that need
more range use Python integer arithmetic before the final float conversion.
This also avoids wrapping an offset across the signed-int64 boundary. Empty
arrays retain their shape; existing floating-point timestamp inputs keep the
previous conversion route. Seconds retain ordinary floating-point rounding.

The origin convention is unchanged. Each ordinary figure uses its existing
origin; the synchronization dashboard shares the earliest series timestamp
across panels. Gap shading already subtracts integer timestamps and stays aligned
with the corrected plotted coordinates. This does not add or infer hardware
synchronization or change recorded clock identities.

## Verification

`tests/analysis/test_plot_observations.py` contains 24 cases for positive and
negative large origins, int64 extrema, uint64 offsets, an origin outside int64,
narrow integer types, matrix/empty shapes, floating values, isolated/continuous/
unavailable series, multiple columns, shared dashboard origins and gap shading.
The figure tests save actual PNG files and check visible colored data marks,
retained sample coordinates and missing values, and figure closure.

The corrected original-source fixture fails 13 of its first 23 cases while ten
compatibility controls pass. After the change, the 24 new cases and 74 neighboring
video, feature, pipeline, gap and CSV-path cases form the focused receiving gate.
The actual four-frame MCAP example now visibly shows both retained FPS points.
Its saved feature table remains the independently received video timing result.

Source review, final test counts, native receiving and artifact delivery are
tracked in [issue 128](https://github.com/Jacob-Met/CaptureSuite/issues/128).
