# SPDX-License-Identifier: GPL-3.0-only
"""Tier A kinematics from pose landmarks (sim + future GPU teachers)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .registry import load_registry

# MediaPipe body indices for real landmark teachers (Phase D GPU path).
_MP = {
    "L_shoulder": 11,
    "R_shoulder": 12,
    "L_elbow": 13,
    "R_elbow": 14,
    "L_wrist": 15,
    "R_wrist": 16,
    "L_hip": 23,
    "R_hip": 24,
}


def _angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ba = a - b
    bc = c - b
    na = float(np.linalg.norm(ba))
    nc = float(np.linalg.norm(bc))
    if na < 1e-9 or nc < 1e-9:
        return float("nan")
    cos = float(np.clip(np.dot(ba, bc) / (na * nc), -1.0, 1.0))
    return math.degrees(math.acos(cos))


def _joint_xyz(
    frame_df: Any, joint_index: int, *, min_confidence: float
) -> np.ndarray | None:
    row = frame_df.loc[frame_df["joint_index"] == joint_index]
    if row.empty:
        return None
    r = row.iloc[0]
    confidence = float(r.get("confidence", 0) or 0)
    if not math.isfinite(confidence) or not confidence >= min_confidence:
        return None
    xyz = np.array([float(r["x"]), float(r["y"]), float(r.get("z", 0) or 0)])
    return xyz if np.isfinite(xyz).all() else None


def _compute_frame_angles(frame_df: Any, *, min_confidence: float) -> dict[str, float]:
    out: dict[str, float] = {}
    for side in ("L", "R"):
        joints = {
            name: _joint_xyz(
                frame_df, _MP[f"{side}_{name}"], min_confidence=min_confidence
            )
            for name in ("shoulder", "elbow", "wrist", "hip")
        }
        shoulder, elbow = joints["shoulder"], joints["elbow"]
        if shoulder is None or elbow is None:
            continue

        wrist = joints["wrist"]
        if wrist is not None:
            angle = _angle_deg(shoulder, elbow, wrist)
            if math.isfinite(angle):
                out[f"theta_elbow_flex_{side}"] = angle

        hip = joints["hip"]
        if hip is None:
            continue
        elevation = _angle_deg(elbow, shoulder, hip)
        # Sagittal flexion proxy: shoulder-elbow vector versus vertical.
        vec = elbow - shoulder
        vertical = np.array([0.0, -1.0, 0.0])
        nv = float(np.linalg.norm(vec))
        if nv < 1e-9:
            flexion = float("nan")
        else:
            cos = float(np.clip(np.dot(vec, vertical) / nv, -1.0, 1.0))
            flexion = math.degrees(math.acos(cos))
        if math.isfinite(elevation) and math.isfinite(flexion):
            out[f"theta_shoulder_elev_{side}"] = elevation
            out[f"theta_shoulder_flex_{side}"] = flexion
    return out


def _sim_angles(session_time_ns: int) -> dict[str, float]:
    phase = float(session_time_ns) / 1e9
    return {
        "theta_elbow_flex_L": 90.0 + 15.0 * math.sin(phase * 1.3),
        "theta_elbow_flex_R": 88.0 + 12.0 * math.cos(phase * 1.1),
        "theta_shoulder_elev_L": 45.0 + 10.0 * math.sin(phase * 0.9),
        "theta_shoulder_elev_R": 43.0 + 9.0 * math.cos(phase * 0.85),
        "theta_shoulder_flex_L": 30.0 + 8.0 * math.sin(phase * 1.05),
        "theta_shoulder_flex_R": 28.0 + 7.0 * math.cos(phase * 0.95),
    }


def landmarks_to_kinematics(
    landmarks_df: Any,
    *,
    pose_model_id: str,
    teacher_source: str = "video",
    min_confidence: float = 0.25,
) -> Any:
    """Build one row per frame with registry Tier A columns."""
    import pandas as pd

    reg = load_registry()
    col_order = [str(c["name"]) for c in reg.get("columns") or []]

    use_sim = pose_model_id.startswith("sim_")
    frames = landmarks_df.groupby(["session_time_ns", "frame_index"], sort=True)

    rows: list[dict[str, Any]] = []
    for (t_ns, fi), frame_df in frames:
        if use_sim:
            mean_conf = float(frame_df["confidence"].mean()) if "confidence" in frame_df else 0.0
            angles = _sim_angles(int(t_ns))
            validity = {
                f"valid_{joint}_{side}": mean_conf >= min_confidence
                for joint in ("elbow", "shoulder") for side in ("L", "R")
            }
        else:
            angles = _compute_frame_angles(frame_df, min_confidence=min_confidence)
            validity = {
                f"valid_{joint}_{side}": f"theta_{joint}_{kind}_{side}" in angles
                for joint, kind in (("elbow", "flex"), ("shoulder", "elev"))
                for side in ("L", "R")
            }

        row: dict[str, Any] = {
            "session_time_ns": int(t_ns),
            "frame_index": int(fi),
            "teacher_source": teacher_source,
            "pose_model_id": pose_model_id,
            **validity,
        }
        for name in col_order:
            if name in row:
                continue
            if name in angles:
                row[name] = float(angles[name])
            elif name == "activity_id":
                row[name] = None
            elif name == "px_per_cm":
                row[name] = float("nan")
            elif name.startswith(("theta_", "omega_", "v_radial_", "afr_")):
                row[name] = float("nan")
            else:
                row[name] = None

        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df.reindex(columns=col_order)

    # Angular velocity via central difference on smoothed angles (sim: direct gradient).
    dt_ns = np.diff(df["session_time_ns"].to_numpy(dtype=np.int64))
    if dt_ns.size:
        dt_s = np.median(dt_ns) / 1e9
    else:
        dt_s = 1.0 / 30.0
    for col in [c for c in col_order if c.startswith("omega_")]:
        theta_col = col.replace("omega_", "theta_", 1)
        if theta_col not in df.columns:
            continue
        theta = df[theta_col].to_numpy(dtype=np.float64)
        omega = np.gradient(theta, dt_s)
        if not use_sim:
            # A central difference can be finite even when its center is missing.
            omega[~np.isfinite(theta)] = float("nan")
        df[col] = omega

    # Rolling AFR on elbow angles (11-frame window when enough samples).
    win = min(11, max(3, len(df) // 2))
    for side in ("L", "R"):
        col = f"theta_elbow_flex_{side}"
        afr = f"afr_elbow_{side}_deg"
        if col in df.columns and len(df) >= win:
            roll = df[col].rolling(win, center=True, min_periods=1)
            df[afr] = roll.max() - roll.min()
            if not use_sim:
                df.loc[df[col].isna(), afr] = float("nan")

    return df[col_order]


def detection_rate(kin_df: Any) -> dict[str, float]:
    if kin_df.empty:
        return {"elbow_L": 0.0, "elbow_R": 0.0, "shoulder_L": 0.0, "shoulder_R": 0.0}
    n = len(kin_df)
    return {
        "elbow_L": float(kin_df["valid_elbow_L"].sum()) / n,
        "elbow_R": float(kin_df["valid_elbow_R"].sum()) / n,
        "shoulder_L": float(kin_df["valid_shoulder_L"].sum()) / n,
        "shoulder_R": float(kin_df["valid_shoulder_R"].sum()) / n,
    }
