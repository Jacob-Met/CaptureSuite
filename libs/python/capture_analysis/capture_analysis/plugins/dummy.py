# SPDX-License-Identifier: GPL-3.0-only
"""Dummy manifest plugin for registry tests (no pipeline.py edits required)."""

from __future__ import annotations

from typing import Any

import numpy as np

from capture_analysis.features.io import write_feature_table
from capture_analysis.plugins.handlers import HandlerContext
from capture_analysis.types import GapMask, LoadedEmg, StreamRef


def extract_dummy_features(
    loaded: LoadedEmg, gap_mask: GapMask, **_params: Any
) -> tuple[Any, dict[str, Any], float]:
    import numpy as np
    import pandas as pd

    _ = gap_mask
    arr = np.asarray(loaded.X, dtype=np.float64)
    value = float(np.mean(arr)) if arr.size else 0.0
    df = pd.DataFrame([{"mean": value}])
    meta = {"mean": {"units": loaded.units, "calibrated": False}}
    return df, meta, 1.0


def handle_dummy(ref: StreamRef, gap_mask: GapMask, ctx: HandlerContext) -> None:
    if not ctx.do_features:
        return
    loaded = LoadedEmg(
        channel_ids=["dummy"],
        t_sample_ns=np.array([0], dtype=np.int64),
        X=np.array([[1.0]], dtype=np.float32),
        fs_hz=1.0,
        units="a.u.",
    )
    df, meta, vf = extract_dummy_features(loaded, gap_mask)
    ctx.valid_fractions[ref.source_id] = vf
    rel = f"features/dummy/{ref.source_id}/probe.parquet"
    write_feature_table(
        ctx.work,
        rel,
        df,
        feature_schema_version=1,
        columns_meta=meta,
        schema_doc=ctx.schema_doc,
        outputs=ctx.outputs,
    )
    ctx.feature_tables.append(
        {"relativePath": rel, "featureSchemaVersion": 1, "rows": int(len(df))}
    )
