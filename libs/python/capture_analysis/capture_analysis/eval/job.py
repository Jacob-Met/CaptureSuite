# SPDX-License-Identifier: GPL-3.0-only
"""Phase 6/F eval reports from ml_bundle windows (sim baseline on fixtures)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from capture_session.package_reader import ReviewSummary

from capture_analysis.kinematics.job import resolve_job_dir


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_eval_job(
    package_root: Path,
    work: Path,
    summary: ReviewSummary,
    *,
    ml_bundle_job_id: str,
    outputs: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    """Write eval/eval_report.json + predictions.parquet (teacher vs sim baseline)."""
    import numpy as np
    import pandas as pd

    bundle_dir = resolve_job_dir(package_root, ml_bundle_job_id)
    win_path = bundle_dir / "ml_bundle" / "windows.parquet"
    man_path = bundle_dir / "ml_bundle" / "manifest.json"
    if not win_path.is_file():
        raise FileNotFoundError(f"missing ml_bundle/windows.parquet in job {ml_bundle_job_id}")

    windows = pd.read_parquet(win_path)
    if windows.empty:
        raise RuntimeError("ml_bundle windows.parquet is empty")

    manifest = {}
    if man_path.is_file():
        try:
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            warnings.append("ml_bundle manifest JSON invalid")

    target_cols = list(manifest.get("targetColumns") or [])
    if not target_cols:
        target_cols = [c for c in windows.columns if c.startswith("theta_")]

    preds = windows[["window_id", "session_time_ns"]].copy()
    for col in target_cols:
        if col not in windows.columns:
            continue
        y = windows[col].to_numpy(dtype=np.float64)
        # Sim baseline: identity teacher (sanity for fixture pipeline).
        preds[f"y_teacher_{col}"] = y
        preds[f"y_hat_{col}"] = y
        preds[f"err_{col}"] = 0.0

    pred_path = work / "eval" / "predictions.parquet"
    pred_path.parent.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(pred_path, index=False)

    metrics: dict[str, Any] = {}
    for col in target_cols:
        if f"err_{col}" in preds.columns:
            err = preds[f"err_{col}"].to_numpy(dtype=np.float64)
            metrics[col] = {
                "mae": float(np.mean(np.abs(err))),
                "rmse": float(np.sqrt(np.mean(err * err))),
                "n": int(len(err)),
            }

    if "valid_mask" in windows.columns:
        valid_count = int(windows["valid_mask"].sum())
    else:
        valid_count = int(len(windows))
    report = {
        "schemaId": "capture.eval_report/1",
        "createdUtc": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sessionId": summary.session_id,
        "mlBundleJobId": ml_bundle_job_id,
        "baseline": "identity_teacher_sim",
        "provisional": True,
        "metrics": metrics,
        "windowCount": int(len(windows)),
        "validWindowCount": valid_count,
        "notes": "Fixture eval — identity baseline until RadarKinematicsML artifact wired.",
    }
    report_path = work / "eval" / "eval_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for rel, kind in (
        ("eval/predictions.parquet", "eval_predictions"),
        ("eval/eval_report.json", "eval_report"),
    ):
        path = work / rel
        outputs.append(
            {
                "relativePath": rel,
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
                "kind": kind,
            }
        )

    return {
        "evalWindowCount": int(len(windows)),
        "mlBundleJobId": ml_bundle_job_id,
        "metrics": metrics,
    }
