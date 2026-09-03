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


def _joint_xyz(frame_df: Any, joint_index: int) -> np.ndarray | None:
    row = frame_df.loc[frame_df["joint_index"] == joint_index]
    if row.empty:
        return None
    r = row.iloc[0]
    if float(r.get("confidence", 0) or 0) < 0.25:
        return None
    return np.array([float(r["x"]), float(r["y"]), float(r.get("z", 0) or 0)])


def _landmarks_wide_enough(landmarks_df: Any) -> bool:
    idx = set(int(x) for x in landmarks_df["joint_index"].unique())
    needed = {_MP["L_shoulder"], _MP["L_elbow"], _MP["L_wrist"], _MP["L_hip"]}
    return needed.issubset(idx)


def _compute_frame_angles(frame_df: Any) -> dict[str, float]:
    if not _landmarks_wide_enough(frame_df):
        return {}

    ls = _joint_xyz(frame_df, _MP["L_shoulder"])
    le = _joint_xyz(frame_df, _MP["L_elbow"])
    lw = _joint_xyz(frame_df, _MP["L_wrist"])
    lh = _joint_xyz(frame_df, _MP["L_hip"])
    rs = _joint_xyz(frame_df, _MP["R_shoulder"])
    re = _joint_xyz(frame_df, _MP["R_elbow"])
    rw = _joint_xyz(frame_df, _MP["R_wrist"])
    rh = _joint_xyz(frame_df, _MP["R_hip"])
    if any(v is None for v in (ls, le, lw, lh, rs, re, rw, rh)):
        return {}

    out: dict[str, float] = {}
    out["theta_elbow_flex_L"] = _angle_deg(ls, le, lw)  # type: ignore[arg-type]
    out["theta_elbow_flex_R"] = _angle_deg(rs, re, rw)  # type: ignore[arg-type]
    out["theta_shoulder_elev_L"] = _angle_deg(le, ls, lh)  # type: ignore[arg-type]
    out["theta_shoulder_elev_R"] = _angle_deg(re, rs, rh)  # type: ignore[arg-type]
    # Sagittal flexion proxy: angle between shoulder-elbow vector and vertical.
    for side, elbow, shoulder in (("L", le, ls), ("R", re, rs)):
        vec = elbow - shoulder  # type: ignore[operator]
        vertical = np.array([0.0, -1.0, 0.0])
        nv = float(np.linalg.norm(vec))
        if nv < 1e-9:
            out[f"theta_shoulder_flex_{side}"] = float("nan")
        else:
            cos = float(np.clip(np.dot(vec, vertical) / nv, -1.0, 1.0))
            out[f"theta_shoulder_flex_{side}"] = math.degrees(math.acos(cos))
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

    use_sim = pose_model_id.startswith("sim_") or not _landmarks_wide_enough(landmarks_df)
    frames = landmarks_df.groupby(["session_time_ns", "frame_index"], sort=True)

    rows: list[dict[str, Any]] = []
    for (t_ns, fi), frame_df in frames:
        mean_conf = float(frame_df["confidence"].mean()) if "confidence" in frame_df else 0.0
        if use_sim:
            angles = _sim_angles(int(t_ns))
            valid_elbow = mean_conf >= min_confidence
            valid_shoulder = valid_elbow
        else:
            angles = _compute_frame_angles(frame_df)
            valid_elbow = bool(angles) and mean_conf >= min_confidence
            valid_shoulder = valid_elbow and _landmarks_wide_enough(frame_df)

        row: dict[str, Any] = {
            "session_time_ns": int(t_ns),
            "frame_index": int(fi),
            "teacher_source": teacher_source,
            "pose_model_id": pose_model_id,
            "valid_elbow_L": valid_elbow,
            "valid_elbow_R": valid_elbow,
            "valid_shoulder_L": valid_shoulder,
            "valid_shoulder_R": valid_shoulder,
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
        df[col] = omega

    # Rolling AFR on elbow angles (11-frame window when enough samples).
    win = min(11, max(3, len(df) // 2))
    for side in ("L", "R"):
        col = f"theta_elbow_flex_{side}"
        afr = f"afr_elbow_{side}_deg"
        if col in df.columns and len(df) >= win:
            roll = df[col].rolling(win, center=True, min_periods=1)
            df[afr] = roll.max() - roll.min()

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
