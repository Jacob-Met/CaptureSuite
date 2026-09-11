# SPDX-License-Identifier: GPL-3.0-only
"""Provisional real-time motion inference seed for FMCW range-Doppler previews.

This module does *not* claim full-body pose recovery from radar.  It provides:

1. A deterministic, low-cost descriptor from a range-Doppler magnitude matrix.
2. Temporal feature stacking suitable for the existing CaptureSuite ML-bundle path.
3. A tiny ridge-regression artifact format that can be trained on aligned
   radar/kinematics windows when real paired data exists.
4. Synthetic fixtures used only to qualify mechanics, latency, and negative controls.

Live descriptor values are unitless/normalized unless the preview carries calibrated
axes.  Learned outputs inherit the model artifact's provenance and are blocked from
being presented as hardware-validated when trained on synthetic fixtures alone.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

FEATURE_NAMES = (
    "log_energy",
    "peak_value",
    "active_fraction",
    "range_centroid_norm",
    "range_spread_norm",
    "doppler_centroid_norm",
    "doppler_spread_norm",
    "signed_doppler_balance",
    "zero_doppler_fraction",
    "spectral_entropy_norm",
    "peak_range_norm",
    "peak_doppler_norm",
    "temporal_l1_norm",
    "temporal_corr",
)

_EPS = 1e-12


@dataclass(frozen=True)
class MotionDescriptor:
    """One physically interpretable descriptor extracted from an RD matrix."""

    feature_vector: np.ndarray
    motion_energy: float
    peak_range_norm: float
    peak_doppler_norm: float
    radial_direction: str
    confidence_proxy: float

    def as_dict(self) -> dict[str, object]:
        return {
            "feature_names": list(FEATURE_NAMES),
            "features": [float(x) for x in self.feature_vector],
            "motion_energy": float(self.motion_energy),
            "peak_range_norm": float(self.peak_range_norm),
            "peak_doppler_norm": float(self.peak_doppler_norm),
            "radial_direction": self.radial_direction,
            "confidence_proxy": float(self.confidence_proxy),
            "calibrated": False,
            "provisional": True,
        }


class RadarMotionFeaturizer:
    """Extract stable descriptors and a temporal stack from range-Doppler frames."""

    def __init__(self, history: int = 8) -> None:
        if history < 1:
            raise ValueError("history must be >= 1")
        self.history = int(history)
        self._vectors: deque[np.ndarray] = deque(maxlen=self.history)
        self._previous_matrix: np.ndarray | None = None

    @property
    def feature_dim(self) -> int:
        return len(FEATURE_NAMES) * self.history

    def reset(self) -> None:
        self._vectors.clear()
        self._previous_matrix = None

    def describe(self, matrix: np.ndarray | Sequence[Sequence[float]]) -> MotionDescriptor:
        x = np.asarray(matrix, dtype=np.float64)
        if x.ndim != 2 or x.size == 0:
            raise ValueError("range-Doppler matrix must be non-empty and 2-D")
        if not np.isfinite(x).all():
            raise ValueError("range-Doppler matrix contains NaN or Inf")

        # Preview matrices are expected to be magnitude-like.  Guard any tiny negative
        # renderer/transform noise, then remove a robust frame floor so stationary DC
        # clutter does not dominate centroids.
        mag = np.maximum(x, 0.0)
        floor = float(np.quantile(mag, 0.50))
        signal = np.maximum(mag - floor, 0.0)
        total = float(signal.sum())
        rows, cols = signal.shape

        r_axis = np.linspace(0.0, 1.0, rows, dtype=np.float64)
        d_axis = np.linspace(-1.0, 1.0, cols, dtype=np.float64)
        r_profile = signal.sum(axis=1)
        d_profile = signal.sum(axis=0)

        if total <= _EPS:
            r_centroid = 0.0
            r_spread = 0.0
            d_centroid = 0.0
            d_spread = 0.0
            balance = 0.0
            entropy = 0.0
            peak_r = 0.0
            peak_d = 0.0
            peak = float(mag.max(initial=0.0))
            active_fraction = 0.0
        else:
            r_centroid = float(np.dot(r_profile, r_axis) / total)
            r_spread = float(np.sqrt(np.dot(r_profile, (r_axis - r_centroid) ** 2) / total))
            d_centroid = float(np.dot(d_profile, d_axis) / total)
            d_spread = float(np.sqrt(np.dot(d_profile, (d_axis - d_centroid) ** 2) / total))
            pos = float(d_profile[d_axis > 0].sum())
            neg = float(d_profile[d_axis < 0].sum())
            balance = (pos - neg) / max(pos + neg, _EPS)
            p = signal.ravel() / total
            nz = p[p > 0]
            entropy = float(-(nz * np.log(nz)).sum() / max(np.log(signal.size), _EPS))
            pr, pd = np.unravel_index(int(np.argmax(signal)), signal.shape)
            peak_r = float(r_axis[pr])
            peak_d = float(d_axis[pd])
            peak = float(signal[pr, pd])
            threshold = max(float(signal.mean() + signal.std()), _EPS)
            active_fraction = float(np.mean(signal > threshold))

        zero_band = np.abs(d_axis) <= max(2.0 / max(cols - 1, 1), 0.05)
        zero_fraction = float(d_profile[zero_band].sum() / max(total, _EPS)) if total > _EPS else 0.0
        mean_energy = float(signal.mean())

        if self._previous_matrix is None or self._previous_matrix.shape != mag.shape:
            temporal_l1 = 0.0
            temporal_corr = 0.0
        else:
            prev = self._previous_matrix
            scale = max(float(np.mean(np.abs(prev))), float(np.mean(np.abs(mag))), _EPS)
            temporal_l1 = float(np.mean(np.abs(mag - prev)) / scale)
            a = mag.ravel() - float(mag.mean())
            b = prev.ravel() - float(prev.mean())
            denom = float(np.linalg.norm(a) * np.linalg.norm(b))
            temporal_corr = float(np.dot(a, b) / denom) if denom > _EPS else 0.0
        self._previous_matrix = mag.copy()

        vec = np.asarray(
            [
                np.log1p(mean_energy),
                peak,
                active_fraction,
                r_centroid,
                r_spread,
                d_centroid,
                d_spread,
                balance,
                zero_fraction,
                entropy,
                peak_r,
                peak_d,
                temporal_l1,
                temporal_corr,
            ],
            dtype=np.float64,
        )
        self._vectors.append(vec)

        # Confidence is deliberately named a proxy: it says the RD frame contains a
        # localized non-zero signal, not that any inferred body pose is correct.
        localization = max(0.0, 1.0 - min(1.0, entropy))
        confidence_proxy = float(np.clip((1.0 - zero_fraction) * 0.6 + localization * 0.4, 0.0, 1.0))
        if abs(d_centroid) < 0.08:
            direction = "stationary_or_transverse"
        elif d_centroid > 0:
            direction = "positive_radial"
        else:
            direction = "negative_radial"

        return MotionDescriptor(
            feature_vector=vec,
            motion_energy=mean_energy,
            peak_range_norm=peak_r,
            peak_doppler_norm=peak_d,
            radial_direction=direction,
            confidence_proxy=confidence_proxy,
        )

    def push(self, matrix: np.ndarray | Sequence[Sequence[float]]) -> tuple[MotionDescriptor, np.ndarray]:
        descriptor = self.describe(matrix)
        vectors = list(self._vectors)
        if len(vectors) < self.history:
            pad = [vectors[0]] * (self.history - len(vectors))
            vectors = pad + vectors
        stacked = np.concatenate(vectors, dtype=np.float64)
        return descriptor, stacked


@dataclass(frozen=True)
class LinearKinematicsModel:
    """Tiny model artifact for low-latency feasibility work, not a final ML choice."""

    mean: np.ndarray
    scale: np.ndarray
    coef: np.ndarray
    intercept: np.ndarray
    target_names: tuple[str, ...]
    history: int
    training_evidence: str
    calibrated: bool = False

    def predict(self, stacked_features: np.ndarray | Sequence[float]) -> dict[str, float]:
        x = np.asarray(stacked_features, dtype=np.float64).reshape(-1)
        if x.size != self.mean.size:
            raise ValueError(f"model expects {self.mean.size} features, got {x.size}")
        z = (x - self.mean) / self.scale
        y = z @ self.coef + self.intercept
        return {name: float(value) for name, value in zip(self.target_names, y, strict=True)}

    @property
    def hardware_validated(self) -> bool:
        return self.training_evidence == "hardware_validated" and self.calibrated

    def save(self, path: Path) -> None:
        meta = {
            "schema_id": "capture.radar_motion_linear/1",
            "target_names": list(self.target_names),
            "history": self.history,
            "training_evidence": self.training_evidence,
            "calibrated": self.calibrated,
            "feature_names_per_frame": list(FEATURE_NAMES),
            "provisional": not self.hardware_validated,
        }
        np.savez_compressed(
            path,
            mean=self.mean,
            scale=self.scale,
            coef=self.coef,
            intercept=self.intercept,
            metadata=np.asarray(json.dumps(meta, sort_keys=True)),
        )

    @classmethod
    def load(cls, path: Path) -> "LinearKinematicsModel":
        with np.load(path, allow_pickle=False) as doc:
            meta = json.loads(str(doc["metadata"].item()))
            return cls(
                mean=np.asarray(doc["mean"], dtype=np.float64),
                scale=np.asarray(doc["scale"], dtype=np.float64),
                coef=np.asarray(doc["coef"], dtype=np.float64),
                intercept=np.asarray(doc["intercept"], dtype=np.float64),
                target_names=tuple(meta["target_names"]),
                history=int(meta["history"]),
                training_evidence=str(meta["training_evidence"]),
                calibrated=bool(meta.get("calibrated", False)),
            )


def fit_ridge_model(
    features: np.ndarray,
    targets: np.ndarray,
    *,
    target_names: Sequence[str],
    history: int,
    alpha: float = 1e-2,
    training_evidence: str = "synthetic_only",
    calibrated: bool = False,
) -> LinearKinematicsModel:
    """Fit deterministic multi-output ridge regression with explicit provenance."""
    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(targets, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 2 or x.shape[0] != y.shape[0] or x.shape[0] < 2:
        raise ValueError("features/targets must be 2-D with matching sample count >= 2")
    if len(target_names) != y.shape[1]:
        raise ValueError("target_names length does not match targets")
    if alpha < 0:
        raise ValueError("alpha must be >= 0")
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-9] = 1.0
    z = (x - mean) / scale
    y_mean = y.mean(axis=0)
    yc = y - y_mean
    gram = z.T @ z
    reg = np.eye(gram.shape[0], dtype=np.float64) * float(alpha)
    coef = np.linalg.solve(gram + reg, z.T @ yc)
    return LinearKinematicsModel(
        mean=mean,
        scale=scale,
        coef=coef,
        intercept=y_mean,
        target_names=tuple(str(v) for v in target_names),
        history=int(history),
        training_evidence=str(training_evidence),
        calibrated=bool(calibrated),
    )


@dataclass(frozen=True)
class SyntheticSequence:
    frames: np.ndarray
    targets: np.ndarray
    target_names: tuple[str, ...]


def _gaussian_2d(rows: int, cols: int, r0: float, d0: float, sr: float, sd: float) -> np.ndarray:
    rr = np.linspace(0.0, 1.0, rows, dtype=np.float64)[:, None]
    dd = np.linspace(-1.0, 1.0, cols, dtype=np.float64)[None, :]
    return np.exp(-0.5 * (((rr - r0) / sr) ** 2 + ((dd - d0) / sd) ** 2))


def generate_synthetic_sequence(
    n_frames: int = 240,
    *,
    rows: int = 32,
    cols: int = 32,
    phase: float = 0.0,
    range_bias: float = 0.0,
    noise: float = 0.02,
    seed: int = 0,
) -> SyntheticSequence:
    """Create an RD fixture with known latent motion for mechanics-only qualification."""
    if n_frames < 8 or rows < 8 or cols < 8:
        raise ValueError("fixture dimensions too small")
    rng = np.random.default_rng(seed)
    t = np.arange(n_frames, dtype=np.float64) / 20.0
    angle = 55.0 + 30.0 * np.sin(2 * np.pi * 0.42 * t + phase)
    angular_velocity = 30.0 * 2 * np.pi * 0.42 * np.cos(2 * np.pi * 0.42 * t + phase)
    r = np.clip(0.45 + range_bias + 0.10 * np.sin(2 * np.pi * 0.16 * t + phase * 0.3), 0.12, 0.88)
    d = np.clip(angular_velocity / 120.0, -0.82, 0.82)

    frames = np.empty((n_frames, rows, cols), dtype=np.float64)
    for i in range(n_frames):
        target = 1.8 * _gaussian_2d(rows, cols, r[i], d[i], 0.055, 0.08)
        micro = 0.55 * _gaussian_2d(rows, cols, np.clip(r[i] + 0.08, 0.0, 1.0), -0.6 * d[i], 0.08, 0.15)
        dc = 0.35 * _gaussian_2d(rows, cols, 0.20, 0.0, 0.16, 0.055)
        jitter = rng.normal(0.0, noise, size=(rows, cols))
        frames[i] = np.maximum(target + micro + dc + jitter, 0.0)

    targets = np.column_stack([angle, angular_velocity, r, d])
    return SyntheticSequence(
        frames=frames,
        targets=targets,
        target_names=(
            "synthetic_joint_angle_deg",
            "synthetic_joint_velocity_deg_s",
            "synthetic_range_norm",
            "synthetic_radial_velocity_norm",
        ),
    )


def iter_stacked_features(frames: Iterable[np.ndarray], history: int) -> np.ndarray:
    f = RadarMotionFeaturizer(history=history)
    return np.vstack([f.push(frame)[1] for frame in frames])
