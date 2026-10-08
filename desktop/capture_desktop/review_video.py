# SPDX-License-Identifier: GPL-3.0-only
"""Read-only identities for recorded video segments; no session-time mapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from capture_analysis.discover import discover_streams


@dataclass(frozen=True)
class RecordedVideoSegment:
    source_id: str
    stream_id: str
    relative_path: str

    @property
    def label(self) -> str:
        return f"{self.source_id} / {self.stream_id} / {self.relative_path}"


def recorded_video_segments(package_root: str | Path) -> tuple[RecordedVideoSegment, ...]:
    """Keep the native discovery order and every separate segment occurrence."""
    root = Path(package_root).absolute()
    return tuple(
        RecordedVideoSegment(ref.source_id, ref.stream_id, path.relative_to(root).as_posix())
        for ref in discover_streams(root)
        for path in ref.mkv_paths
    )


def local_video_path(package_root: str | Path, segment: RecordedVideoSegment) -> Path:
    """Resolve an explicitly selected existing, package-contained regular file."""
    root = Path(package_root).resolve(strict=True)
    path = (root / segment.relative_path).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("The selected segment is not a regular file inside this package.")
    return path


def media_time(milliseconds: int) -> str:
    """Format the player's segment-local milliseconds without rounding to seconds."""
    milliseconds = max(0, int(milliseconds))
    seconds, fraction = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{fraction:03d}"
