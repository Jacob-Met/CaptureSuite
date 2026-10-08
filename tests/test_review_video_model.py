# SPDX-License-Identifier: GPL-3.0-only
"""Recorded video identities and exact local-media clock behavior."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from capture_desktop.review_video import (
    RecordedVideoSegment,
    local_video_path,
    media_time,
    recorded_video_segments,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "review_video"


def test_inventory_keeps_source_stream_path_and_duplicate_names() -> None:
    rows = recorded_video_segments(FIXTURE)
    assert [(r.source_id, r.stream_id, r.relative_path) for r in rows] == [
        (
            "sim.left <literal>",
            "front & camera",
            "sources/sim.left/streams/front/segments/0001.mkv",
        ),
        (
            "sim.left <literal>",
            "front & camera",
            "sources/sim.left/streams/front/segments/0002.mkv",
        ),
        (
            "sim.right <literal>",
            "front & camera",
            "sources/sim.right/streams/front/segments/0001.mkv",
        ),
        (
            "sim.right <literal>",
            "front & camera",
            "sources/sim.right/streams/front/segments/invalid.mkv",
        ),
    ]
    assert rows[0].label != rows[2].label
    assert local_video_path(FIXTURE, rows[0]).is_file()


def test_selection_checks_current_availability_and_package_boundary(tmp_path: Path) -> None:
    package = tmp_path / "package"
    shutil.copytree(FIXTURE, package)
    row = recorded_video_segments(package)[0]
    local_video_path(package, row).unlink()
    with pytest.raises(FileNotFoundError):
        local_video_path(package, row)
    outside = tmp_path / "outside.mkv"
    outside.write_bytes(b"outside")
    before = hashlib.sha256(outside.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="inside this package"):
        local_video_path(package, RecordedVideoSegment("source", "stream", "../outside.mkv"))
    assert hashlib.sha256(outside.read_bytes()).hexdigest() == before


def test_segment_must_be_regular_file(tmp_path: Path) -> None:
    (tmp_path / "folder.mkv").mkdir()
    with pytest.raises(ValueError, match="regular file"):
        local_video_path(tmp_path, RecordedVideoSegment("source", "stream", "folder.mkv"))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "00:00:00.000"),
        (1, "00:00:00.001"),
        (999, "00:00:00.999"),
        (1000, "00:00:01.000"),
        (86_399_999, "23:59:59.999"),
        (86_400_000, "24:00:00.000"),
    ],
)
def test_media_clock_preserves_milliseconds_without_wrapping_days(
    value: int, expected: str
) -> None:
    assert media_time(value) == expected
