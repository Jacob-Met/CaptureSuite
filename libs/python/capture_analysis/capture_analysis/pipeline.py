# SPDX-License-Identifier: GPL-3.0-only
"""Feature + plot pipeline shared by jobs.run commands."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from capture_session.package_reader import ReviewSummary

from capture_analysis.discover import discover_streams
from capture_analysis.plots.sync_dashboard import plot_sync_dashboard
from capture_analysis.plugins.handlers import HandlerContext
from capture_analysis.plugins.registry import get_registry
from capture_analysis.types import TimeWindow
from capture_analysis.windows import build_gap_mask, gaps_to_intervals


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def run_features_and_plots(
    root: Path,
    work: Path,
    summary: ReviewSummary,
    window: TimeWindow,
    *,
    gap_policy: str,
    max_ram_bytes: int,
    sources_filter: list[str],
    do_features: bool,
    do_plots: bool,
    outputs: list[dict[str, Any]],
    warnings: list[str],
    feature_tables: list[dict[str, Any]],
    registry=None,
) -> dict[str, Any]:
    """Returns context used for sync dashboard / gap summary extras."""
    reg = registry or get_registry()
    refs = discover_streams(root)
    if sources_filter:
        refs = [r for r in refs if r.source_id in sources_filter]
    all_gaps = gaps_to_intervals(summary)
    schema_doc: dict[str, Any] = {"schemaId": "capture.analysis_feature_schema/1", "tables": {}}
    sync_series: list[dict[str, Any]] = []
    valid_fractions: dict[str, float] = {}

    ctx = HandlerContext(
        root=root,
        work=work,
        summary=summary,
        window=window,
        gap_policy=gap_policy,
        max_ram_bytes=max_ram_bytes,
        do_features=do_features,
        do_plots=do_plots,
        all_gaps=all_gaps,
        outputs=outputs,
        warnings=warnings,
        schema_doc=schema_doc,
        feature_tables=feature_tables,
        sync_series=sync_series,
        valid_fractions=valid_fractions,
    )

    for ref in refs:
        handler = reg.stream_handler_for(ref)
        if handler is None:
            continue
        gap_mask = build_gap_mask(ref, window, all_gaps, policy=gap_policy)
        try:
            handler(ref, gap_mask, ctx)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{ref.source_id}/{ref.stream_id}: {exc}")

    if do_features and schema_doc["tables"]:
        schema_path = work / "features" / "_schema.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(schema_doc, indent=2, sort_keys=True).encode("utf-8")
        schema_path.write_bytes(data)
        outputs.append(
            {
                "relativePath": "features/_schema.json",
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "kind": "feature_schema",
            }
        )

    if do_plots and sync_series:
        fig_path = work / "figures" / "sync_dashboard.png"
        plot_sync_dashboard(
            fig_path,
            window=window,
            gaps=all_gaps,
            series=sync_series[:4],
            title=f"{summary.session_id} · gap_policy={gap_policy}",
        )
        outputs.append(
            {
                "relativePath": "figures/sync_dashboard.png",
                "bytes": fig_path.stat().st_size,
                "sha256": _hash_file(fig_path),
                "kind": "figure",
            }
        )
        series_doc = {
            "schemaId": "capture.sync_dashboard_series/1",
            "title": f"{summary.session_id} · gap_policy={gap_policy}",
            "window": {
                "startSessionNs": window.start_session_ns,
                "endSessionNs": window.end_session_ns,
                "label": window.label,
            },
            "gaps": [
                {
                    "sourceId": g.source_id,
                    "streamId": g.stream_id,
                    "cause": g.cause,
                    "startSessionNs": g.start_session_ns,
                    "endSessionNs": g.end_session_ns,
                    "closed": g.closed,
                }
                for g in all_gaps
            ],
            "series": [
                {
                    "label": item["label"],
                    "t_ns": [int(x) for x in np.asarray(item["t_ns"]).tolist()],
                    "y": [float(x) for x in np.asarray(item["y"]).tolist()],
                    "color": item.get("color", "#3d8bfd"),
                }
                for item in sync_series[:4]
            ],
        }
        series_path = work / "figures" / "sync_dashboard_series.json"
        series_bytes = json.dumps(series_doc, indent=2, sort_keys=True).encode("utf-8")
        series_path.write_bytes(series_bytes)
        outputs.append(
            {
                "relativePath": "figures/sync_dashboard_series.json",
                "bytes": len(series_bytes),
                "sha256": hashlib.sha256(series_bytes).hexdigest(),
                "kind": "sync_series",
            }
        )

    return {"valid_fractions": valid_fractions, "pluginManifestVersion": reg.manifest_version}
