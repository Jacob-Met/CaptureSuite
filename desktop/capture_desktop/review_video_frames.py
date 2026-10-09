# SPDX-License-Identifier: GPL-3.0-only
"""Bounded detached images from an explicitly chosen decoded video frame."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QImage, QTransform
from PySide6.QtMultimedia import QVideoFrame

from .review_video import RecordedVideoSegment

MAX_FRAME_PIXELS = 16_777_216
MAX_FRAME_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class RetainedVideoFrame:
    image: QImage
    segment: RecordedVideoSegment
    frame_start_us: int | None
    player_position_ms: int
    decoded_width: int
    decoded_height: int
    rotation_degrees: int
    mirrored: bool


def _admit_size(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("No decoded image is available. Play the segment, then pause.")
    if width * height > MAX_FRAME_PIXELS or width * height * 4 > MAX_FRAME_BYTES:
        raise ValueError(
            "This decoded frame exceeds the comparison limit of 16,777,216 pixels "
            "(64 MiB per retained image). The existing frames are unchanged."
        )


def retain_video_frame(
    frame: QVideoFrame, segment: RecordedVideoSegment, player_position_ms: int
) -> RetainedVideoFrame:
    """Copy pixels only on request; never retain the decoder's shared frame buffer."""
    if not frame.isValid():
        raise ValueError("No decoded frame is available. Play the segment, then pause.")
    width, height = frame.width(), frame.height()
    _admit_size(width, height)
    image = frame.toImage()
    if image.isNull():
        raise ValueError("The decoder could not copy this frame. Play and pause to retry.")
    _admit_size(image.width(), image.height())
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    if image.isNull() or image.sizeInBytes() > MAX_FRAME_BYTES:
        raise ValueError("The decoded image could not be retained within the 64 MiB limit.")
    # Qt's toImage includes surface-format conversion but excludes these
    # presentation transforms. The older spelling supports the project's Qt 6.6 floor.
    rotation = frame.rotation().value if hasattr(frame, "rotation") else frame.rotationAngle().value
    mirrored = frame.mirrored()
    if rotation:
        image = image.transformed(QTransform().rotate(rotation))
    if mirrored:
        image = image.mirrored(True, False)
    image = image.copy()
    if image.isNull() or image.sizeInBytes() > MAX_FRAME_BYTES:
        raise ValueError("The transformed image could not be retained within the 64 MiB limit.")
    stamp = frame.startTime()
    return RetainedVideoFrame(
        image=image,
        segment=segment,
        frame_start_us=stamp if stamp >= 0 else None,
        player_position_ms=player_position_ms,
        decoded_width=width,
        decoded_height=height,
        rotation_degrees=rotation,
        mirrored=mirrored,
    )
