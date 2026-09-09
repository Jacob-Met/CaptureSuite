# SPDX-License-Identifier: GPL-3.0-only
"""Write feature tables as parquet (+ csv mirror)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def write_feature_table(
    job_dir: Path,
    relative: str,
    df: pd.DataFrame,
    *,
    feature_schema_version: int,
    columns_meta: list[dict[str, Any]],
    schema_doc: dict[str, Any],
    outputs: list[dict[str, Any]],
) -> None:
    rel = relative.replace("\\", "/")
    path = job_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    csv_rel = rel.replace(".parquet", ".csv")
    df.to_csv(job_dir / csv_rel, index=False)

    import hashlib

    def _add(rel_path: str, kind: str) -> None:
        p = job_dir / rel_path
        data = p.read_bytes()
        outputs.append(
            {
                "relativePath": rel_path.replace("\\", "/"),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "kind": kind,
            }
        )

    _add(rel, "feature_parquet")
    _add(csv_rel, "feature_csv")

    schema_doc.setdefault("schemaId", "capture.analysis_feature_schema/1")
    schema_doc.setdefault("tables", {})
    schema_doc["tables"][rel] = {
        "featureSchemaVersion": feature_schema_version,
        "columns": columns_meta,
        "rows": int(len(df)),
    }
