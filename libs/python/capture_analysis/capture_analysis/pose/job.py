# SPDX-License-Identifier: GPL-3.0-only
"""Phase 5 body pose job — sim teacher from sealed video timing (+ MKV path recorded)."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from capture_session.package_reader import ReviewSummary

from capture_analysis.discover import discover_streams
from capture_analysis.loaders.video import load_video_timing
from capture_analysis.types import StreamRef, TimeWindow
from capture_analysis.windows import build_gap_mask, gaps_to_intervals, validity_mask

BODY_JOINT_COUNT = 25
DEFAULT_MODEL_ID = "sim_teacher_v1"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _video_streams(
    package_root: Path,
    sources_filter: list[str],
) -> list[StreamRef]:
    refs = [
        r
        for r in discover_streams(package_root)
        if r.modality == "video" or r.data_schema_id.startswith("video.")
    ]
    if sources_filter:
        allowed = set(sources_filter)
        refs = [r for r in refs if r.source_id in allowed]
    return refs


def _sim_landmarks_from_timing(
    t_frame_ns: np.ndarray,
    *,
    model_id: str,
    source_id: str,
) -> Any:
    import pandas as pd

    if t_frame_ns.size == 0:
        return pd.DataFrame(
            columns=[
                "session_time_ns",
                "frame_index",
                "joint_index",
                "x",
                "y",
                "z",
                "confidence",
                "source_model",
                "source_id",
            ]
        )

    rows: list[dict[str, Any]] = []
    for fi, t_ns in enumerate(t_frame_ns):
        phase = float(t_ns) / 1e9
        for joint in range(BODY_JOINT_COUNT):
            rows.append(
                {
                    "session_time_ns": int(t_ns),
                    "frame_index": int(fi),
                    "joint_index": int(joint),
                    "x": float(0.5 + 0.08 * math.sin(phase + joint * 0.25)),
                    "y": float(0.5 + 0.08 * math.cos(phase * 1.1 + joint * 0.15)),
                    "z": float(0.02 * math.sin(joint * 0.4)),
                    "confidence": 0.85,
                    "source_model": model_id,
                    "source_id": source_id,
                }
            )
    return pd.DataFrame(rows)


def run_pose_job(
    package_root: Path,
    work: Path,
    summary: ReviewSummary,
    *,
    window: TimeWindow,
    gap_policy: str = "mask",
    sources_filter: list[str] | None = None,
    model_id: str = DEFAULT_MODEL_ID,
    outputs: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    """Write pose/landmarks.parquet + pose/model_card.json for each video stream."""
    sources_filter = list(sources_filter or [])
    streams = _video_streams(package_root, sources_filter)
    if not streams:
        raise RuntimeError("pose job requires at least one video.timing stream in the package")

    all_gaps = gaps_to_intervals(summary)
    tables: list[dict[str, Any]] = []
    total_frames = 0

    for ref in streams:
        gap_mask = build_gap_mask(ref, window, all_gaps, policy=gap_policy)
        loaded = load_video_timing(ref, window)
        warnings.extend(loaded.warnings)
        t_arr = loaded.t_frame_ns
        if t_arr.size:
            valid = validity_mask(t_arr, gap_mask)
            t_arr = t_arr[valid]
        if t_arr.size == 0:
            warnings.append(
                f"{ref.source_id}/{ref.stream_id}: no timing frames in window after gap mask"
            )
            continue
        if not loaded.mkv_paths:
            warnings.append(
                f"{ref.source_id}: no sealed MKV segment — sim teacher uses timing only"
            )
        else:
            for mkv in loaded.mkv_paths:
                if not mkv.is_file() or mkv.stat().st_size == 0:
                    warnings.append(
                        f"{ref.source_id}: MKV {mkv.name} missing or empty — "
                        "decode deferred; sim teacher from timing"
                    )

        df = _sim_landmarks_from_timing(t_arr, model_id=model_id, source_id=ref.source_id)
        rel = f"pose/{ref.source_id}/landmarks.parquet"
        out_path = work / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path, index=False)

        card = {
            "model_id": model_id,
            "role": "body",
            "provisional": True,
            "joint_count": BODY_JOINT_COUNT,
            "source_id": ref.source_id,
            "stream_id": ref.stream_id,
            "frame_count": int(t_arr.size),
            "mkv_segments": [p.name for p in loaded.mkv_paths],
            "teacher": "sim_timing_synthetic",
            "note": "Fixture/sim teacher — not GPU inference. Hand bake-off deferred.",
        }
        card_rel = f"pose/{ref.source_id}/model_card.json"
        card_path = work / card_rel
        card_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        outputs.append(
            {
                "relativePath": rel.replace("\\", "/"),
                "bytes": out_path.stat().st_size,
                "sha256": _sha256_file(out_path),
                "kind": "pose_landmarks",
            }
        )
        outputs.append(
            {
                "relativePath": card_rel.replace("\\", "/"),
                "bytes": card_path.stat().st_size,
                "sha256": _sha256_file(card_path),
                "kind": "pose_model_card",
            }
        )
        tables.append(
            {
                "relativePath": rel,
                "rows": int(len(df)),
                "frameCount": int(t_arr.size),
                "modelId": model_id,
            }
        )
        total_frames += int(t_arr.size)

    if not tables:
        raise RuntimeError("pose job produced no landmark tables (check timing MCAP + window)")

    return {
        "poseModelId": model_id,
        "poseTables": tables,
        "poseFrameCount": total_frames,
        "provisional": True,
    }
