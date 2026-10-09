# SPDX-License-Identifier: GPL-3.0-only
"""Prepare editable, source-bound placeholders for the maintained evaluator."""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
from capture_session.package_reader import load_review_summary

from capture_analysis.eval import predictions
from capture_analysis.kinematics.job import resolve_job_dir


def prepare_prediction_template(
    package_root: str | Path,
    bundle_job_id: str,
    model_id: str,
    output_path: str | Path,
) -> dict[str, Any]:
    """Publish a new external JSON template after maintained evaluator admission.

    All values are unavailable (null); this does not run a model or evaluation.
    Publication requires same-directory hard-link support and never replaces an
    existing destination. It is not a package transaction or power-loss guarantee.
    """
    package = Path(package_root).resolve()
    destination = Path(output_path).absolute()
    if os.path.lexists(destination):
        raise FileExistsError(f"prediction output already exists: {destination}")
    parent = destination.parent.resolve(strict=True)
    if not parent.is_dir():
        raise NotADirectoryError(f"prediction output parent is not a directory: {parent}")
    if parent.is_relative_to(package):
        raise ValueError("prediction output must be outside the selected package")
    destination = parent / destination.name
    if os.path.lexists(destination):
        raise FileExistsError(f"prediction output already exists: {destination}")

    summary = load_review_summary(package)
    bundle = resolve_job_dir(package, bundle_job_id).resolve()
    if not bundle.is_relative_to((package / "processing" / "jobs").resolve()):
        raise ValueError("prediction template requires a bundle inside this package's jobs")

    windows_bytes = predictions._snapshot(bundle / "ml_bundle" / "windows.parquet")
    manifest_bytes = predictions._snapshot(bundle / "ml_bundle" / "manifest.json")
    manifest = predictions._json(manifest_bytes, "bundle manifest")
    frame = pd.read_parquet(io.BytesIO(windows_bytes))
    targets = manifest.get("targetColumns")
    if not isinstance(targets, list) or not all(isinstance(c, str) for c in targets):
        raise ValueError("bundle targetColumns must be a list of names")
    if "window_id" not in frame or "session_time_ns" not in frame:
        raise ValueError("bundle needs window_id and session_time_ns columns")

    doc = {
        "schemaId": predictions.SCHEMA_ID,
        "modelId": model_id,
        "windowsSha256": hashlib.sha256(windows_bytes).hexdigest(),
        "manifestSha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "predictions": [
            {
                "window_id": window_id,
                "session_time_ns": int(stamp),
                "values": dict.fromkeys(targets),
            }
            for window_id, stamp in zip(
                frame["window_id"].tolist(), frame["session_time_ns"].tolist(), strict=True
            )
        ],
    }
    content = (json.dumps(doc, indent=2, allow_nan=False) + "\n").encode("utf-8")
    if len(content) > predictions.MAX_INPUT_BYTES:
        raise ValueError("prediction template exceeds the evaluator's 64 MiB file limit")

    staged: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".capture-predictions-", suffix=".tmp", dir=parent, delete=False
        ) as stream:
            staged = Path(stream.name)
            stream.write(content)
        # Use the existing consumer as the admission authority. Its reread must
        # agree with the exact source bytes used to construct this template.
        predictions._load_inputs(package, bundle_job_id, staged, summary.session_id)
        # Atomic exclusive publication: a late-created destination also survives.
        os.link(staged, destination)
    except BaseException as exc:
        if staged is not None:
            try:
                staged.unlink(missing_ok=True)
            except OSError as cleanup:
                exc.add_note(f"Could not remove owned temporary file {staged}: {cleanup}")
        raise

    try:
        staged.unlink()
    except OSError as exc:
        raise OSError(
            f"Template was published at {destination}, but owned temporary cleanup failed: {staged}"
        ) from exc
    return {
        "output": str(destination),
        "windowCount": len(doc["predictions"]),
        "targetCount": len(targets),
    }
