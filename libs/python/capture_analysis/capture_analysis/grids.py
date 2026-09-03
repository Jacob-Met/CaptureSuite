# SPDX-License-Identifier: GPL-3.0-only
"""AnalysisGrid helpers — resampling provenance only (never mutates raw)."""

from __future__ import annotations

from capture_analysis.types import AnalysisGrid


def make_grid(
    *,
    grid_id: str,
    rate_hz: float,
    start_ns: int,
    end_ns: int,
    method: str,
    source_stream_ids: list[str],
    params: dict | None = None,
    valid_fraction_by_source: dict[str, float] | None = None,
) -> AnalysisGrid:
    if method not in ("linear", "previous", "window_mean"):
        raise ValueError(f"unsupported AnalysisGrid method: {method}")
    if rate_hz <= 0:
        raise ValueError("AnalysisGrid rate_hz must be > 0")
    return AnalysisGrid(
        grid_id=grid_id,
        rate_hz=float(rate_hz),
        start_ns=int(start_ns),
        end_ns=int(end_ns),
        method=method,
        source_stream_ids=list(source_stream_ids),
        params=dict(params or {}),
        valid_fraction_by_source=dict(valid_fraction_by_source or {}),
    )
