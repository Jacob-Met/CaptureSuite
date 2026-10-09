# SPDX-License-Identifier: GPL-3.0-only
"""Media interval boundaries independent of a decoder or session clock."""

import pytest
from capture_desktop.review_video_interval import ReviewInterval


def test_explicit_enable_and_half_open_playback_interval():
    interval = ReviewInterval()
    interval.set_start(400, 2000)
    interval.set_end(1200, 2000)
    assert interval.valid(2000) and not interval.enabled
    assert interval.target(1600, 2000) == 1600
    interval.set_enabled(True, 2000)
    assert [interval.target(p, 2000) for p in [0, 399, 400, 1199, 1200, 2000]] == [
        400,
        400,
        400,
        1199,
        400,
        400,
    ]


@pytest.mark.parametrize("position", [-1, 0, 399, 400, 2001])
def test_invalid_b_preserves_previous_enabled_interval(position):
    interval = ReviewInterval(400, 1200, True)
    with pytest.raises(ValueError):
        interval.set_end(position, 2000)
    assert interval == ReviewInterval(400, 1200, True)


def test_replacing_an_endpoint_requires_explicit_reenable():
    interval = ReviewInterval(400, 1200, True)
    interval.set_end(1600, 2000)
    assert interval == ReviewInterval(400, 1600, False)
    interval.set_enabled(True, 2000)
    interval.set_start(600, 2000)
    assert interval == ReviewInterval(600, None, False)


@pytest.mark.parametrize("position", [-1, 2000, 2001])
def test_invalid_a_preserves_whole_interval(position):
    interval = ReviewInterval(400, 1200, True)
    with pytest.raises(ValueError):
        interval.set_start(position, 2000)
    assert interval == ReviewInterval(400, 1200, True)


def test_clear_and_disable_do_not_rewrite_requested_positions():
    interval = ReviewInterval(0, 2000, True)
    interval.set_enabled(False, 2000)
    assert interval.target(2000, 2000) == 2000
    interval.clear()
    assert interval == ReviewInterval()
    assert interval.target(123, 2000) == 123


def test_incomplete_or_newly_short_duration_cannot_enable():
    interval = ReviewInterval()
    with pytest.raises(ValueError):
        interval.set_end(200, 2000)
    with pytest.raises(ValueError):
        interval.set_enabled(True, 2000)
    interval = ReviewInterval(400, 1200)
    assert not interval.valid(1000)
    with pytest.raises(ValueError):
        interval.set_enabled(True, 1000)
