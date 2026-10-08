# SPDX-License-Identifier: GPL-3.0-only
"""Source-bound external prediction evaluation for the existing offline job runner."""

from __future__ import annotations

import hashlib
import io
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from capture_session.package_reader import ReviewSummary

from capture_analysis.kinematics.job import resolve_job_dir
from capture_analysis.kinematics.registry import REGISTRY_PATH

SCHEMA_ID = "capture.eval_predictions/1"
MAX_INPUT_BYTES = 64 * 1024 * 1024


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _snapshot(path: Path) -> bytes:
    if not path.is_file():
        raise ValueError(f"evaluation input is not a file: {path}")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError(f"evaluation input exceeds 64 MiB: {path}")
    data = path.read_bytes()
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError(f"evaluation input exceeds 64 MiB: {path}")
    return data


def _json(data: bytes, label: str) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError(
            f"{label}: non-finite JSON number {value!r}; use null for missing predictions"
        )

    try:
        doc = json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"{label}: invalid UTF-8 JSON") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"{label}: expected a JSON object")
    return doc


def _require_digest(doc: dict, key: str, expected: str) -> None:
    if doc.get(key) != expected:
        raise ValueError(f"prediction input {key} does not match the selected bundle bytes")


def _numeric_column(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame:
        raise ValueError(f"bundle missing target column {column!r}")
    series = frame[column]
    if (
        not pd.api.types.is_numeric_dtype(series)
        or pd.api.types.is_bool_dtype(series)
        or pd.api.types.is_complex_dtype(series)
    ):
        raise ValueError(f"bundle target {column!r} must be numeric")
    return series.to_numpy(dtype=np.float64, na_value=np.nan)


def _load_inputs(package_root: Path, bundle_id: str, prediction_path: Path,
                 session_id: str) -> tuple[pd.DataFrame, dict, dict, dict, bytes, bytes]:
    bundle = resolve_job_dir(package_root, bundle_id).resolve()
    try:
        bundle.relative_to((package_root / "processing" / "jobs").resolve())
    except ValueError as exc:
        raise ValueError(
            "external evaluation requires a bundle inside this package's jobs"
        ) from exc
    windows_bytes = _snapshot(bundle / "ml_bundle" / "windows.parquet")
    manifest_bytes = _snapshot(bundle / "ml_bundle" / "manifest.json")
    prediction_bytes = _snapshot(prediction_path)
    # Decode precisely the bytes whose digests are checked and reported.
    manifest = _json(manifest_bytes, "bundle manifest")
    doc = _json(prediction_bytes, "prediction input")
    required = {"schemaId", "modelId", "windowsSha256", "manifestSha256", "predictions"}
    if set(doc) != required or doc.get("schemaId") != SCHEMA_ID:
        raise ValueError("prediction input must follow capture.eval_predictions/1")
    model_id = doc["modelId"]
    if (
        not isinstance(model_id, str)
        or not model_id.strip()
        or len(model_id) > 120
        or any(ord(c) < 32 for c in model_id)
    ):
        raise ValueError(
            "prediction modelId must be a nonempty, single-line label of at most 120 chars"
        )
    windows_digest = _sha(windows_bytes)
    _require_digest(doc, "windowsSha256", windows_digest)
    _require_digest(doc, "manifestSha256", _sha(manifest_bytes))
    if manifest.get("schemaId") != "capture.ml_bundle/1":
        raise ValueError("selected source is not a capture.ml_bundle/1 manifest")
    if not session_id or manifest.get("sessionIds") != [session_id]:
        raise ValueError("bundle sessionIds do not identify this selected session")
    source_digests = manifest.get("sha256")
    if (
        not isinstance(source_digests, dict)
        or source_digests.get("windows.parquet") != windows_digest
    ):
        raise ValueError("bundle manifest windows.parquet digest does not match the source bytes")
    columns = manifest.get("targetColumns")
    if (
        not isinstance(columns, list) or not columns
        or not all(isinstance(c, str) and c for c in columns)
        or len(set(columns)) != len(columns)
    ):
        raise ValueError("bundle targetColumns must be a nonempty list of distinct names")

    registry_bytes = _snapshot(REGISTRY_PATH)
    registry = _json(registry_bytes, "kinematics registry")
    units = {c["name"]: c["units"] for c in registry["columns"]
             if c.get("tier") != "metadata" and c.get("arrowType") == "float64"}
    if any(c not in units for c in columns):
        raise ValueError("external evaluation targets must be numeric kinematics registry columns")

    windows = pd.read_parquet(io.BytesIO(windows_bytes))
    if windows.empty:
        raise ValueError("bundle windows.parquet is empty")
    for name in ("window_id", "session_time_ns", "valid_mask"):
        if name not in windows:
            raise ValueError(f"bundle is missing {name}")
    identifiers = windows["window_id"].tolist()
    if (
        not all(isinstance(w, str) and w for w in identifiers)
        or len(set(identifiers)) != len(identifiers)
    ):
        raise ValueError("bundle window_id values must be distinct nonempty strings")
    time_column = windows["session_time_ns"]
    if (
        not pd.api.types.is_integer_dtype(time_column)
        or pd.api.types.is_bool_dtype(time_column)
        or time_column.isna().any()
    ):
        raise ValueError("bundle session_time_ns must contain exact integers")
    times = [int(t) for t in time_column]
    if any(t < -(2**63) or t >= 2**63 for t in times):
        raise ValueError("bundle session_time_ns is outside signed int64")
    validity = windows["valid_mask"]
    if not pd.api.types.is_bool_dtype(validity) or validity.isna().any():
        raise ValueError("bundle valid_mask must be Boolean and cannot contain missing values")
    for column in columns:
        _numeric_column(windows, column)

    rows = doc["predictions"]
    if not isinstance(rows, list) or len(rows) != len(windows):
        raise ValueError("predictions must contain exactly one row for every bundle window")
    by_id = {}
    expected_times = dict(zip(identifiers, times, strict=True))
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"window_id", "session_time_ns", "values"}:
            raise ValueError("each prediction row needs only window_id, session_time_ns and values")
        window_id = row["window_id"]
        if not isinstance(window_id, str) or window_id not in expected_times:
            raise ValueError("prediction references a foreign or invalid window_id")
        if window_id in by_id:
            raise ValueError(f"duplicate prediction window_id: {window_id}")
        stamp = row["session_time_ns"]
        if type(stamp) is not int or stamp != expected_times[window_id]:
            raise ValueError(f"prediction session_time_ns does not match window {window_id}")
        values = row["values"]
        if not isinstance(values, dict) or set(values) != set(columns):
            raise ValueError(f"prediction targets do not exactly match bundle window {window_id}")
        parsed = {}
        for name, value in values.items():
            if value is None:
                parsed[name] = float("nan")
                continue
            if type(value) not in (float, int):
                raise ValueError(f"prediction {name} must be a finite number or null")
            try:
                numeric = float(value)
            except OverflowError as exc:
                raise ValueError(f"prediction {name} is outside finite float64") from exc
            if not math.isfinite(numeric):
                raise ValueError(f"prediction {name} must be finite; use null when unavailable")
            parsed[name] = numeric
        by_id[window_id] = parsed
    prediction_values = {c: np.asarray([by_id[w][c] for w in identifiers]) for c in columns}
    provenance = {
        "windowsSha256": windows_digest,
        "manifestSha256": _sha(manifest_bytes),
        "predictionsSha256": _sha(prediction_bytes),
        "kinematicsRegistrySha256": _sha(registry_bytes),
        "predictionSchemaId": SCHEMA_ID,
    }
    return windows, doc, prediction_values, {
        "columns": columns, "units": units, "provenance": provenance,
    }, prediction_bytes, manifest_bytes


def _scores(teacher: np.ndarray, predicted: np.ndarray) -> tuple[dict, np.ndarray]:
    n = len(teacher)
    empty = {"mae": None, "rmse": None, "pearsonR": None,
             "pearsonReason": "insufficient_pairs", "n": n}
    if n == 0:
        return empty, np.empty(0, dtype=np.float64)
    try:
        with np.errstate(over="raise", invalid="raise"):
            residual = predicted - teacher
    except FloatingPointError as exc:
        raise ValueError("prediction residual cannot be represented as finite float64") from exc
    if not np.isfinite(residual).all():
        raise ValueError("prediction residual cannot be represented as finite float64")
    scale = float(np.max(np.abs(residual)))
    if scale:
        scaled = residual / scale
        mae = float(scale * np.mean(np.abs(scaled)))
        rmse = float(scale * np.sqrt(np.mean(scaled * scaled)))
    else:
        mae = rmse = 0.0
    if not math.isfinite(mae) or not math.isfinite(rmse):
        raise ValueError("prediction error metric cannot be represented as finite float64")
    correlation = None
    reason = "insufficient_pairs"
    if n >= 2:
        # Scaling before centering avoids overflowing a mean/covariance of finite inputs.
        x_scale = float(np.max(np.abs(teacher))) or 1.0
        y_scale = float(np.max(np.abs(predicted))) or 1.0
        x = teacher / x_scale
        y = predicted / y_scale
        # Translate first so averaging near 1 cannot erase half-ULP offsets.
        x = x - x[0]
        y = y - y[0]
        x = x - np.mean(x)
        y = y - np.mean(y)
        x_norm = float(np.linalg.norm(x))
        y_norm = float(np.linalg.norm(y))
        if x_norm == 0.0 or y_norm == 0.0:
            reason = "constant_series"
        else:
            correlation = float(np.clip(np.dot(x / x_norm, y / y_norm), -1.0, 1.0))
            reason = None
    return {"mae": mae, "rmse": rmse, "pearsonR": correlation,
            "pearsonReason": reason, "n": n}, residual


def _register(work: Path, relative: str, kind: str, outputs: list[dict[str, Any]]) -> None:
    path = work / relative
    data = path.read_bytes()
    outputs.append(
        {"relativePath": relative, "bytes": len(data), "sha256": _sha(data), "kind": kind}
    )


def _figures(work: Path, frame: pd.DataFrame, columns: list[str], units: dict,
             model_id: str, metrics: dict, outputs: list[dict[str, Any]]) -> None:
    from capture_analysis.plots.style import plt

    times = [int(t) for t in frame["session_time_ns"]]
    origin = min(times)
    elapsed = np.asarray([t - origin for t in times], dtype=np.float64) / 1e9
    for column in columns:
        teacher = frame[f"y_teacher_{column}"].to_numpy()
        predicted = frame[f"y_hat_{column}"].to_numpy()
        residual = frame[f"err_{column}"].to_numpy()
        valid = frame[f"valid_{column}"].to_numpy(dtype=bool)
        unit = units[column]
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
        try:
            fig.suptitle(f"{column} — external prediction evaluation", fontsize=12)
            axes[0].set_title("Prediction versus teacher", fontsize=10)
            axes[0].set_xlabel(f"Teacher ({unit})")
            axes[0].set_ylabel(f"Prediction ({unit})")
            if valid.any():
                x, y = teacher[valid], predicted[valid]
                axes[0].scatter(x, y, s=20, color="#2878a8", label="Scored pair")
                low, high = float(min(x.min(), y.min())), float(max(x.max(), y.max()))
                axes[0].plot([low, high], [low, high], "--", color="#6b7280", label="Identity")
                axes[0].legend(fontsize=8)
            else:
                axes[0].text(0.5, 0.5, "No valid pairs", ha="center", transform=axes[0].transAxes)
            axes[1].set_title("Prediction minus teacher", fontsize=10)
            axes[1].axhline(0, color="#6b7280", linestyle="--", linewidth=0.8)
            # NaNs leave visible breaks rather than joining through excluded windows.
            axes[1].plot(elapsed, residual, ".-", color="#2878a8", linewidth=0.8)
            axes[1].set_xlabel(f"Elapsed session time (s)\nOrigin: {origin} ns")
            axes[1].set_ylabel(f"Residual ({unit})")
            for axis in axes:
                axis.grid(alpha=0.2)
            metric = metrics[column]
            fig.text(0.5, 0.055,
                     f"Provisional · {metric['n']}/{len(frame)} pairs scored · "
                     "Unavailable values are excluded",
                     ha="center", fontsize=9)
            fig.text(0.5, 0.02, f"Caller-supplied model label: {model_id}",
                     ha="center", fontsize=8, parse_math=False)
            fig.tight_layout(rect=(0, 0.1, 1, 0.91))
            for suffix, kind in (("png", "figure"), ("pdf", "figure_pdf")):
                relative = f"eval/figures/prediction_{column}.{suffix}"
                path = work / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                fig.savefig(path, dpi=150)
                _register(work, relative, kind, outputs)
        finally:
            plt.close(fig)


def run_external_eval(
    package_root: Path, work: Path, summary: ReviewSummary, *, ml_bundle_job_id: str,
    prediction_path: str | Path, outputs: list[dict[str, Any]], warnings: list[str],
) -> dict[str, Any]:
    """Evaluate admitted predictions; all input/scoring refusals precede eval output."""
    windows, doc, predictions, context, prediction_bytes, manifest_bytes = _load_inputs(
        package_root, ml_bundle_job_id, Path(prediction_path), summary.session_id,
    )
    columns = context["columns"]
    mask = windows["valid_mask"].to_numpy(dtype=bool)
    result = windows[["window_id", "session_time_ns", "valid_mask"]].copy()
    result["session_time_ns"] = result["session_time_ns"].astype("int64")
    metrics = {}
    for column in columns:
        teacher = _numeric_column(windows, column)
        predicted = predictions[column]
        finite_teacher = np.isfinite(teacher)
        finite_prediction = np.isfinite(predicted)
        valid = mask & finite_teacher & finite_prediction
        metric, errors = _scores(teacher[valid], predicted[valid])
        metric["units"] = context["units"][column]
        metric["excluded"] = {
            "invalidWindow": int((~mask).sum()),
            "nonfiniteTeacher": int((mask & ~finite_teacher).sum()),
            "missingPrediction": int((mask & finite_teacher & ~finite_prediction).sum()),
        }
        metrics[column] = metric
        residual = np.full(len(windows), np.nan)
        residual[valid] = errors
        result[f"y_teacher_{column}"] = teacher
        result[f"y_hat_{column}"] = predicted
        result[f"err_{column}"] = residual
        result[f"valid_{column}"] = valid

    report = {
        "schemaId": "capture.eval_report/1",
        "createdUtc": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sessionId": summary.session_id,
        "mlBundleJobId": ml_bundle_job_id,
        "evaluationMode": "external_predictions",
        "baseline": None,
        "modelId": doc["modelId"],
        "provisional": True,
        "heldOutValidation": "not_established",
        "inputProvenance": context["provenance"],
        "targetColumns": columns,
        "metrics": metrics,
        "windowCount": int(len(windows)),
        "validWindowCount": int(mask.sum()),
        "samplePolicy": (
            "Per target: valid_mask=true and finite teacher/prediction. "
            "Exclusion counts partition the unscored windows; null predictions stay unavailable."
        ),
        "notes": (
            "Evaluates supplied predictions, without running or validating a model. "
            "The model label is caller supplied; held-out design, teacher accuracy, calibration "
            "and clinical validity are not established."
        ),
    }
    folder = work / "eval"
    folder.mkdir(parents=True, exist_ok=True)
    result.to_parquet(folder / "predictions.parquet", index=False)
    (folder / "prediction_input.json").write_bytes(prediction_bytes)
    (folder / "source_bundle_manifest.json").write_bytes(manifest_bytes)
    (folder / "eval_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8",
    )
    for name, kind in (
        ("predictions.parquet", "eval_predictions"), ("prediction_input.json", "eval_input"),
        ("source_bundle_manifest.json", "eval_input"), ("eval_report.json", "eval_report"),
    ):
        _register(work, f"eval/{name}", kind, outputs)
    _figures(work, result, columns, context["units"], doc["modelId"], metrics, outputs)
    if any(metric["n"] < len(windows) for metric in metrics.values()):
        warnings.append("External evaluation excluded unavailable pairs; see per-target counts.")
    return {"evalWindowCount": int(len(windows)), "mlBundleJobId": ml_bundle_job_id,
            "metrics": metrics, "evaluationMode": "external_predictions"}
