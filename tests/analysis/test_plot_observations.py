# SPDX-License-Identifier: GPL-3.0-only
"""Observe exact figure coordinates and visible, disconnected sample marks."""

from fractions import Fraction

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
import pytest
from capture_analysis.plots import modality, style, sync_dashboard
from capture_analysis.types import GapInterval, TimeWindow


@pytest.mark.parametrize("origin", [0, 2**60, -(2**60), 2**63 - 301, -(2**63)])
def test_short_integer_offsets_survive_translation(origin):
    times = np.array([origin, origin + 100, origin + 200], dtype=np.int64)
    before = times.copy()
    expected = np.array([0.0, 1e-7, 2e-7])
    np.testing.assert_array_equal(style.to_seconds(times, origin), expected)
    np.testing.assert_array_equal(times, before)


@pytest.mark.parametrize(
    ("values", "origin", "dtype"),
    [
        ([-(2**63), -1, 0, 2**63 - 1], -(2**63), np.int64),
        ([-(2**63), -1, 0, 2**63 - 1], 2**63 - 1, np.int64),
        ([2**64 - 301, 2**64 - 201, 2**64 - 101], 2**64 - 301, np.uint64),
        ([0, 1, 2], -(2**63) - 5, np.int64),
        ([-128, 0, 127], 127, np.int8),
    ],
)
def test_integer_offsets_match_arbitrary_precision(values, origin, dtype):
    times = np.array(values, dtype=dtype)
    expected = np.array([float(Fraction(int(value) - origin, 10**9)) for value in times])
    np.testing.assert_array_max_ulp(style.to_seconds(times, origin), expected, maxulp=1)


def test_matrix_shape_and_empty_integer_input_are_retained():
    origin = 2**60
    matrix = np.array([[origin, origin + 100], [origin + 200, origin + 300]], dtype=np.int64)
    np.testing.assert_array_equal(style.to_seconds(matrix, origin), [[0, 1e-7], [2e-7, 3e-7]])
    empty = style.to_seconds(np.empty((2, 0), dtype=np.int64), origin)
    assert empty.shape == (2, 0)
    assert empty.dtype == np.float64


def test_existing_float_timestamp_route_is_unchanged():
    values = np.array([12.5, np.nan, np.inf, -9.25])
    with np.errstate(invalid="raise"):
        actual = style.to_seconds(values, 0.5)
    np.testing.assert_array_equal(actual, (values.astype(np.float64) - 0.5) / 1e9)


def _receive_figures(monkeypatch, module):
    received = []
    original_save = module.save_fig

    def save(fig, path):
        received.append(fig)
        original_save(fig, path)

    monkeypatch.setattr(module, "save_fig", save)
    return received


def _blue_pixels(path):
    rgba = mpimg.imread(path)
    return int(((rgba[:, :, 2] > 0.8) & (rgba[:, :, 0] < 0.35)
                & (rgba[:, :, 1] > 0.4) & (rgba[:, :, 1] < 0.65)).sum())


@pytest.mark.parametrize("dashboard", [False, True], ids=["series", "dashboard"])
@pytest.mark.parametrize(
    ("values", "marks"),
    [([10.0], [0]), ([10.0, np.nan, 10.0], [0, 2]),
     ([np.nan, 10.0, np.inf, 11.0, 12.0, np.nan, 9.0], [1, 6])],
    ids=["single", "separated", "mixed_runs"],
)
def test_isolated_observations_are_visible_without_joining_missing_data(
    tmp_path, monkeypatch, dashboard, values, marks
):
    module = sync_dashboard if dashboard else modality
    figures = _receive_figures(monkeypatch, module)
    times = np.arange(len(values), dtype=np.int64) * 100_000_000 + 2**60
    samples = np.array(values)
    before_times, before_samples = times.copy(), samples.copy()
    window = TimeWindow(int(times[0]), int(times[-1]))
    output = tmp_path / "observations.png"
    if dashboard:
        module.plot_sync_dashboard(output, window=window, gaps=[],
                                   series=[{"label": "FPS", "t_ns": times, "y": samples}],
                                   title="Observed cadence")
    else:
        module.plot_series(output, times, samples, window=window, gaps=[],
                           ylabel="FPS", title="Observed cadence")
    line = figures[0].axes[0].lines[0]
    assert line.get_marker() not in (None, "None", "", " ")
    assert list(line.get_markevery()) == marks
    np.testing.assert_array_equal(line.get_ydata(), samples)
    expected_time = np.array([float(Fraction(int(t) - int(times[0]), 10**9)) for t in times])
    np.testing.assert_array_equal(line.get_xdata(), expected_time)
    assert _blue_pixels(output) >= 8
    np.testing.assert_array_equal(times, before_times)
    np.testing.assert_array_equal(samples, before_samples)
    assert not plt.fignum_exists(figures[0].number)


@pytest.mark.parametrize("dashboard", [False, True], ids=["series", "dashboard"])
@pytest.mark.parametrize("values", [[1.0, 2.0, 3.0], [np.nan, np.nan, np.nan]],
                         ids=["continuous", "unavailable"])
def test_continuous_and_fully_unavailable_series_keep_their_presentation(
    tmp_path, monkeypatch, dashboard, values
):
    module = sync_dashboard if dashboard else modality
    figures = _receive_figures(monkeypatch, module)
    times = np.array([0, 100_000_000, 200_000_000], dtype=np.int64)
    samples = np.array(values)
    window = TimeWindow(0, 200_000_000)
    output = tmp_path / "control.png"
    if dashboard:
        module.plot_sync_dashboard(output, window=window, gaps=[],
                                   series=[{"label": "value", "t_ns": times, "y": samples}],
                                   title="Control")
    else:
        module.plot_series(output, times, samples, window=window, gaps=[],
                           ylabel="value", title="Control")
    line = figures[0].axes[0].lines[0]
    assert line.get_marker() in (None, "None", "", " ")
    np.testing.assert_array_equal(line.get_ydata(), samples)
    assert (_blue_pixels(output) > 0) == bool(np.isfinite(samples).any())


def test_shared_dashboard_origin_and_gap_shading_keep_exact_offsets(tmp_path, monkeypatch):
    figures = _receive_figures(monkeypatch, sync_dashboard)
    origin = 2**60
    window = TimeWindow(origin, origin + 500)
    gap = GapInterval(source_id="sim", stream_id="frames", cause="test",
                      start_session_ns=origin + 150, end_session_ns=origin + 250, closed=True)
    sync_dashboard.plot_sync_dashboard(
        tmp_path / "translated.png", window=window, gaps=[gap], title="Short offsets",
        series=[
            {"label": "first", "t_ns": np.array([origin, origin + 100]), "y": [1.0, 2.0]},
            {"label": "later", "t_ns": np.array([origin + 300, origin + 400]), "y": [3.0, 4.0]},
        ],
    )
    axes = figures[0].axes
    np.testing.assert_array_equal(axes[0].lines[0].get_xdata(), [0, 1e-7])
    np.testing.assert_array_equal(axes[1].lines[0].get_xdata(), [3e-7, 4e-7])
    for ax in axes:
        patch = ax.patches[0]
        assert patch.get_x() == 1.5e-7
        assert patch.get_width() == pytest.approx(1e-7)


def test_existing_multiple_column_series_marks_each_observed_column(tmp_path, monkeypatch):
    figures = _receive_figures(monkeypatch, modality)
    samples = np.array([[1.0, np.nan], [np.nan, 2.0], [3.0, np.nan]])
    before = samples.copy()
    modality.plot_series(
        tmp_path / "columns.png", np.array([0, 100, 200], dtype=np.int64), samples,
        window=TimeWindow(0, 200), gaps=[], ylabel="value", title="Retained columns",
    )
    lines = figures[0].axes[0].lines
    assert len(lines) == 2
    assert list(lines[0].get_markevery()) == [0, 2]
    assert list(lines[1].get_markevery()) == [1]
    np.testing.assert_array_equal(lines[0].get_ydata(), samples[:, 0])
    np.testing.assert_array_equal(lines[1].get_ydata(), samples[:, 1])
    np.testing.assert_array_equal(samples, before)
