# SPDX-License-Identifier: GPL-3.0-only
"""Phase 6 ML bundle — aligned radar/feature windows + kinematics targets."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from capture_session.package_reader import ReviewSummary

from capture_analysis.kinematics.job import resolve_job_dir

ML_BUNDLE_SCHEMA = (
    Path(__file__).resolve().parents[5]
    / "schemas"
    / "ml_bundle"
    / "ml_bundle.manifest.schema.json"
)

DEFAULT_TARGET_COLUMNS = [
    "theta_elbow_flex_L",
    "theta_elbow_flex_R",
    "omega_elbow_flex_L",
    "omega_elbow_flex_R",
]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_feature_series(features_job_dir: Path) -> tuple[np.ndarray, np.ndarray, str, list[str]]:
    """Return (t_ns, values, stream_id, warnings) from first usable feature parquet."""
    import pandas as pd

    warnings: list[str] = []
    candidates = sorted(features_job_dir.glob("features/**/*.parquet"))
    if not candidates:
        raise FileNotFoundError(f"no feature parquet under {features_job_dir}")

    # Prefer radar feature tables for Phase 6 radar→teacher gate.
    candidates = sorted(
        candidates,
        key=lambda p: (0 if "radar" in p.as_posix().lower() else 1, p.as_posix()),
    )

    for path in candidates:
        if path.name == "_schema.json" or "timing_qc" in path.as_posix():
            continue
        try:
            df = pd.read_parquet(path)
        except Exception:  # noqa: BLE001
            continue
        if df.empty:
            continue
        t_col = None
        for name in (
            "session_time_ns",
            "t_ns",
            "t_mid_ns",
            "t_start_ns",
            "window_start_ns",
        ):
            if name in df.columns:
                t_col = name
                break
        if t_col is None:
            warnings.append(f"{path.name}: no time column — skipped")
            continue
        if "energy" in df.columns and pd.api.types.is_numeric_dtype(df["energy"]):
            values = df["energy"].to_numpy(dtype=np.float64)
        else:
            numeric = [
                c
                for c in df.columns
                if c not in (t_col, "window_end_ns", "valid_fraction", "valid")
                and pd.api.types.is_numeric_dtype(df[c])
            ]
            if not numeric:
                warnings.append(f"{path.name}: no numeric feature columns")
                continue
            values = df[numeric].mean(axis=1).to_numpy(dtype=np.float64)
        t_ns = df[t_col].to_numpy(dtype=np.int64)
        parts = path.relative_to(features_job_dir).parts
        stream_id = parts[2] if len(parts) >= 3 else path.stem
        return t_ns, values, stream_id, warnings

    raise RuntimeError("no usable feature parquet for ml_bundle alignment")


def _nearest_indices(query_ns: np.ndarray, series_ns: np.ndarray) -> np.ndarray:
    if series_ns.size == 0:
        return np.zeros(len(query_ns), dtype=np.int64)
    idx = np.searchsorted(series_ns, query_ns)
    idx = np.clip(idx, 0, len(series_ns) - 1)
    for i, q in enumerate(query_ns):
        if idx[i] > 0:
            left = series_ns[idx[i] - 1]
            right = series_ns[idx[i]]
            if abs(int(q) - int(left)) < abs(int(q) - int(right)):
                idx[i] -= 1
    return idx


def _validate_manifest(doc: dict[str, Any]) -> list[str]:
    if not ML_BUNDLE_SCHEMA.is_file():
        return []
    try:
        import jsonschema

        schema = json.loads(ML_BUNDLE_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.validate(doc, schema)
    except Exception as exc:  # noqa: BLE001
        return [f"ml_bundle manifest schema: {exc}"]
    return []


def run_ml_bundle_job(
    package_root: Path,
    work: Path,
    summary: ReviewSummary,
    *,
    kinematics_job_id: str,
    features_job_id: str,
    window_sec: float = 1.0,
    hop_sec: float = 0.05,
    grid_rate_hz: float = 20.0,
    target_columns: list[str] | None = None,
    outputs: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    """Build ml_bundle/manifest.json + windows.parquet."""
    import pandas as pd

    kin_dir = resolve_job_dir(package_root, kinematics_job_id)
    feat_dir = resolve_job_dir(package_root, features_job_id)
    kin_path = kin_dir / "kinematics" / "kinematics.parquet"
    if not kin_path.is_file():
        raise FileNotFoundError(f"missing kinematics.parquet in job {kinematics_job_id}")

    kin_df = pd.read_parquet(kin_path)
    if kin_df.empty:
        raise RuntimeError("kinematics.parquet is empty")

    y_cols = list(target_columns or DEFAULT_TARGET_COLUMNS)
    for col in y_cols:
        if col not in kin_df.columns:
            raise RuntimeError(f"kinematics missing target column {col!r}")

    feat_t, feat_v, feat_stream, feat_warn = _load_feature_series(feat_dir)
    warnings.extend(feat_warn)

    t0 = int(kin_df["session_time_ns"].min())
    t1 = int(kin_df["session_time_ns"].max())
    hop_ns = int(hop_sec * 1e9)
    win_ns = int(window_sec * 1e9)
    if hop_ns <= 0 or win_ns <= 0:
        raise ValueError("window_sec and hop_sec must be positive")

    centers: list[int] = []
    t = t0 + win_ns // 2
    while t <= t1 - win_ns // 2:
        centers.append(int(t))
        t += hop_ns
    if not centers:
        centers = [int(kin_df["session_time_ns"].median())]

    kin_t = kin_df["session_time_ns"].to_numpy(dtype=np.int64)
    feat_idx = _nearest_indices(np.asarray(centers, dtype=np.int64), feat_t)

    rows: list[dict[str, Any]] = []
    for wi, center_ns in enumerate(centers):
        lo = center_ns - win_ns // 2
        hi = center_ns + win_ns // 2
        mask = (kin_t >= lo) & (kin_t <= hi)
        if not mask.any():
            valid = False
            y_row = {c: float("nan") for c in y_cols}
        else:
            sub = kin_df.loc[mask]
            valid = bool(sub["valid_elbow_L"].all() and sub["valid_elbow_R"].all())
            y_row = {c: float(sub[c].median()) for c in y_cols}

        row: dict[str, Any] = {
            "window_id": f"w{wi:05d}",
            "session_time_ns": int(center_ns),
            "valid_mask": valid,
            "motion_energy": float(feat_v[feat_idx[wi]]),
            "feature_stream_id": feat_stream,
        }
        row.update(y_row)
        rows.append(row)

    win_df = pd.DataFrame(rows)
    bundle_dir = work / "ml_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    win_path = bundle_dir / "windows.parquet"
    win_df.to_parquet(win_path, index=False)

    session_id = getattr(summary, "session_id", None) or ""
    manifest: dict[str, Any] = {
        "schemaId": "capture.ml_bundle/1",
        "bundleVersion": "1.0.0",
        "createdUtc": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sourceJobIds": {
            "kinematics": kinematics_job_id,
            "features": features_job_id,
        },
        "sessionIds": [session_id] if session_id else [],
        "analysisGrids": [
            {
                "gridId": "radar_kinematics_v1",
                "rateHz": float(grid_rate_hz),
                "method": "linear_interp_labels",
                "sourceStreams": [feat_stream, "kinematics.teacher"],
                "params": {
                    "windowSec": window_sec,
                    "windowHopSec": hop_sec,
                    "featureKind": "motion_energy",
                },
            }
        ],
        "window": {
            "windowSec": window_sec,
            "hopSec": hop_sec,
            "targetTime": "center",
        },
        "targetColumns": y_cols,
        "inputFeatures": {
            "kind": "motion_energy",
            "shape": [1],
            "radarStreamIds": [feat_stream],
        },
        "normalization": {
            "input": "per_session_zscore",
            "target": "raw_degrees",
        },
        "tensorFormat": "parquet_blob",
        "provisional": True,
        "sha256": {},
    }
    manifest["sha256"]["windows.parquet"] = _sha256_file(win_path)
    schema_warnings = _validate_manifest(manifest)
    warnings.extend(schema_warnings)

    man_path = bundle_dir / "manifest.json"
    man_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    man_path.write_bytes(man_bytes)
    manifest["sha256"]["manifest.json"] = _sha256_bytes(man_bytes)
    man_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for rel, kind in (
        ("ml_bundle/windows.parquet", "ml_bundle_windows"),
        ("ml_bundle/manifest.json", "ml_bundle_manifest"),
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
        "mlBundleWindowCount": int(len(win_df)),
        "kinematicsJobId": kinematics_job_id,
        "featuresJobId": features_job_id,
        "targetColumns": y_cols,
        "schemaWarnings": schema_warnings,
    }
