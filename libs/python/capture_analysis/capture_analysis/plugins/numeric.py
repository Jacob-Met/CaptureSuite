# SPDX-License-Identifier: GPL-3.0-only
"""Generic numeric analysis outputs, independent of a sensor's modality label."""

from __future__ import annotations

import hashlib

from capture_analysis.features.io import write_feature_table
from capture_analysis.features.numeric_batch import extract_numeric_batch_features
from capture_analysis.loaders.numeric_batch import load_numeric_batch
from capture_analysis.plots.modality import plot_series
from capture_analysis.plugins.handlers import HandlerContext
from capture_analysis.types import GapMask, StreamRef


def handle_numeric(ref: StreamRef, gap_mask: GapMask, ctx: HandlerContext) -> None:
    loaded = load_numeric_batch(ref, ctx.window, max_ram_bytes=ctx.max_ram_bytes)
    # Exact UTF-8 hex is reversible and remains distinct on case-insensitive
    # filesystems, including separators, trailing dots and reserved device names.
    component = f"source-{ref.source_id.encode().hex()}/stream-{ref.stream_id.encode().hex()}"
    if ctx.do_features:
        df, meta, vf = extract_numeric_batch_features(loaded, gap_mask)
        # A healthy sibling must not hide a partially gapped numeric stream.
        # The pipeline's per-source map is the minimum observed stream fraction.
        ctx.valid_fractions[ref.source_id] = min(ctx.valid_fractions.get(ref.source_id, 1.0), vf)
        if not df.empty:
            rel = f"features/numeric/{component}/windows.parquet"
            write_feature_table(
                ctx.work,
                rel,
                df,
                feature_schema_version=1,
                columns_meta=meta,
                schema_doc=ctx.schema_doc,
                outputs=ctx.outputs,
            )
            ctx.schema_doc["tables"][rel].update(
                {"sourceId": ref.source_id, "streamId": ref.stream_id, "validFraction": vf}
            )
            ctx.feature_tables.append(
                {"relativePath": rel, "featureSchemaVersion": 1, "rows": int(len(df))}
            )
    if ctx.do_plots and loaded.X.size:
        step = max(1, loaded.t_sample_ns.size // 20000)
        for index, channel in enumerate(loaded.channel_ids):
            path = ctx.work / "figures" / "numeric" / component / f"channel_{index}.png"
            plot_series(
                path,
                loaded.t_sample_ns[::step],
                loaded.X[index, ::step],
                window=ctx.window,
                gaps=gap_mask.gaps,
                ylabel=loaded.units,
                title=(
                    f"Numeric {ref.source_id}/{ref.stream_id} · {channel} (provisional)\n"
                    f"First retained session_time_ns={int(loaded.t_sample_ns[0])}"
                ),
                xlabel="Time since first retained sample (s)",
            )
            ctx.outputs.append(
                {
                    "relativePath": path.relative_to(ctx.work).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "kind": "figure",
                }
            )
        ctx.sync_series.append(
            {
                "label": f"Numeric {ref.source_id}/{ref.stream_id} · {loaded.channel_ids[0]}",
                "t_ns": loaded.t_sample_ns[::step],
                "y": loaded.X[0, ::step],
                "color": "#3d8bfd",
            }
        )
