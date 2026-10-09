# SPDX-License-Identifier: GPL-3.0-only
"""An in-memory media-clock interval; never a session or scientific time scope."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReviewInterval:
    start_ms: int | None = None
    end_ms: int | None = None
    enabled: bool = False

    def clear(self) -> None:
        self.start_ms = self.end_ms = None
        self.enabled = False

    def valid(self, duration_ms: int) -> bool:
        return (
            self.start_ms is not None
            and self.end_ms is not None
            and 0 <= self.start_ms < self.end_ms <= duration_ms
        )

    def set_start(self, position_ms: int, duration_ms: int) -> None:
        if not 0 <= position_ms < duration_ms:
            raise ValueError("A must be before the end of this seekable segment.")
        self.start_ms = position_ms
        self.end_ms = None
        self.enabled = False

    def set_end(self, position_ms: int, duration_ms: int) -> None:
        if self.start_ms is None:
            raise ValueError("Set A before setting B.")
        if not 0 <= self.start_ms < position_ms <= duration_ms:
            raise ValueError("B must be after A and within this segment.")
        self.end_ms = position_ms
        self.enabled = False

    def set_enabled(self, enabled: bool, duration_ms: int) -> None:
        if enabled and not self.valid(duration_ms):
            raise ValueError("Set a valid A and B before enabling Repeat.")
        self.enabled = enabled

    def target(self, position_ms: int, duration_ms: int) -> int:
        if self.enabled and self.valid(duration_ms):
            assert self.start_ms is not None and self.end_ms is not None
            if not self.start_ms <= position_ms < self.end_ms:
                return self.start_ms
        return position_ms
