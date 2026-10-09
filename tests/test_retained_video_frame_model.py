# SPDX-License-Identifier: GPL-3.0-only
"""Retained-image admission and real Qt pixel/orientation regression cases."""

from __future__ import annotations

import pytest
from capture_desktop.review_video import RecordedVideoSegment
from capture_desktop.review_video_frames import _admit_size, retain_video_frame
from PySide6.QtGui import QColor, QImage
from PySide6.QtMultimedia import QVideoFrame
from PySide6.QtWidgets import QApplication

SEGMENT = RecordedVideoSegment("left <literal>", "front & camera", "sources/left/0001.mkv")


@pytest.fixture(scope="module", autouse=True)
def application():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.parametrize(
    ("angle", "expected"),
    [
        (0, [[1, 2], [3, 4], [5, 6]]),
        (90, [[5, 3, 1], [6, 4, 2]]),
        (180, [[6, 5], [4, 3], [2, 1]]),
        (270, [[2, 4, 6], [1, 3, 5]]),
    ],
)
@pytest.mark.parametrize("mirror", [False, True])
def test_native_pixel_copy_and_presentation(angle, expected, mirror):
    image = QImage(2, 3, QImage.Format.Format_ARGB32)
    for y in range(3):
        for x in range(2):
            image.setPixelColor(x, y, QColor(1 + x + 2 * y, 0, 0))
    frame = QVideoFrame(image)
    frame.setRotationAngle(QVideoFrame.RotationAngle(angle))
    frame.setMirrored(mirror)
    frame.setStartTime(123_456)
    kept = retain_video_frame(frame, SEGMENT, 999)
    image.fill(QColor(99, 0, 0))
    frame.swap(QVideoFrame())
    actual = [
        [kept.image.pixelColor(x, y).red() for x in range(kept.image.width())]
        for y in range(kept.image.height())
    ]
    assert actual == ([row[::-1] for row in expected] if mirror else expected)
    assert kept.segment == SEGMENT
    assert kept.frame_start_us == 123_456 and kept.player_position_ms == 999
    assert (kept.decoded_width, kept.decoded_height) == (2, 3)
    assert kept.rotation_degrees == angle and kept.mirrored == mirror


def test_missing_timestamp_stays_unavailable():
    image = QImage(1, 1, QImage.Format.Format_ARGB32)
    image.fill(QColor("red"))
    kept = retain_video_frame(QVideoFrame(image), SEGMENT, 43)
    assert kept.frame_start_us is None
    assert kept.player_position_ms == 43


@pytest.mark.parametrize(("width", "height"), [(4097, 4096), (16_777_217, 1), (0, 1), (-1, 2)])
def test_size_refusals(width, height):
    with pytest.raises(ValueError):
        _admit_size(width, height)


def test_exact_retained_pixel_budget_boundary():
    _admit_size(4096, 4096)
    _admit_size(16_777_216, 1)


def test_oversized_decode_refused_before_conversion():
    class Oversized:
        def isValid(self):  # noqa: N802
            return True

        def width(self):
            return 16_777_217

        def height(self):
            return 1

        def toImage(self):  # noqa: N802
            raise AssertionError("Oversized frame must refuse before conversion")

    with pytest.raises(ValueError, match="16,777,216"):
        retain_video_frame(Oversized(), SEGMENT, 0)


def test_invalid_frame_refuses():
    with pytest.raises(ValueError, match="No decoded frame"):
        retain_video_frame(QVideoFrame(), SEGMENT, 0)
