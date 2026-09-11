# SPDX-License-Identifier: GPL-3.0-only
"""Qualify the radar motion inference seed on synthetic or live RD preview frames.

Synthetic mode proves only mechanics/latency/negative controls. Live mode is attach-only:
it does not create/stop a session, select sources, or apply radar configuration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / "capture_analysis"),
    str(ROOT / "libs" / "python" / "capture_protocol"),
]

from capture_analysis.radar_motion.seed import (  # noqa: E402
    LinearKinematicsModel,
    RadarMotionFeaturizer,
    fit_ridge_model,
    generate_synthetic_sequence,
    iter_stacked_features,
)


def _rmse(y: np.ndarray, yhat: np.ndarray) -> np.ndarray:
    return np.sqrt(np.mean((y - yhat) ** 2, axis=0))


def synthetic_gate(output_model: Path | None = None) -> int:
    history = 8
    train_parts = [
        generate_synthetic_sequence(260, phase=0.0, range_bias=-0.05, seed=1),
        generate_synthetic_sequence(260, phase=0.9, range_bias=0.02, seed=2),
        generate_synthetic_sequence(260, phase=1.8, range_bias=0.08, seed=3),
    ]
    x_train = np.vstack([iter_stacked_features(s.frames, history) for s in train_parts])
    y_train = np.vstack([s.targets for s in train_parts])
    target_names = train_parts[0].target_names
    model = fit_ridge_model(
        x_train,
        y_train,
        target_names=target_names,
        history=history,
        alpha=0.15,
        training_evidence="synthetic_only",
        calibrated=False,
    )

    test = generate_synthetic_sequence(320, phase=2.45, range_bias=-0.01, seed=44)
    x_test = iter_stacked_features(test.frames, history)
    yhat = np.vstack([list(model.predict(x).values()) for x in x_test])
    rmse = _rmse(test.targets, yhat)

    # Changed-input control: descriptor axes are normalized, so a different preview
    # matrix geometry should preserve the directly observable range/radial latents.
    geometry_test = generate_synthetic_sequence(
        280, rows=48, cols=64, noise=0.04, phase=2.1, range_bias=0.03, seed=51
    )
    x_geometry = iter_stacked_features(geometry_test.frames, history)
    geometry_hat = np.vstack([list(model.predict(x).values()) for x in x_geometry])
    geometry_rmse = _rmse(geometry_test.targets, geometry_hat)

    # Stress evidence, not a green gate: materially noisier input exposes how quickly
    # a synthetic kinematic prior becomes brittle even while direct motion proxies remain.
    noise_stress = generate_synthetic_sequence(
        280, rows=32, cols=32, noise=0.07, phase=1.1, range_bias=0.11, seed=53
    )
    x_stress = iter_stacked_features(noise_stress.frames, history)
    stress_hat = np.vstack([list(model.predict(x).values()) for x in x_stress])
    stress_rmse = _rmse(noise_stress.targets, stress_hat)

    # Negative control 1: destroy radar↔teacher correspondence.
    shuffled = y_train.copy()
    rng = np.random.default_rng(99)
    rng.shuffle(shuffled, axis=0)
    mutant = fit_ridge_model(
        x_train,
        shuffled,
        target_names=target_names,
        history=history,
        alpha=0.15,
        training_evidence="synthetic_only",
    )
    mutant_hat = np.vstack([list(mutant.predict(x).values()) for x in x_test])
    mutant_rmse = _rmse(test.targets, mutant_hat)

    # Negative control 2: flip Doppler columns at inference. Signed radial velocity
    # should degrade because the sign information was destroyed/reversed.
    x_flip = iter_stacked_features(test.frames[:, :, ::-1], history)
    flipped_hat = np.vstack([list(model.predict(x).values()) for x in x_flip])
    flipped_rmse = _rmse(test.targets, flipped_hat)

    # Benchmark end-to-end descriptor + model inference. The radar gate runs around
    # 20 Hz, so 50 ms/frame is the hard feasibility ceiling; we require ample margin.
    f = RadarMotionFeaturizer(history=history)
    lat_ms: list[float] = []
    for frame in test.frames:
        t0 = time.perf_counter_ns()
        _, stack = f.push(frame)
        model.predict(stack)
        lat_ms.append((time.perf_counter_ns() - t0) / 1e6)
    p95 = float(np.percentile(np.asarray(lat_ms), 95))
    median = float(statistics.median(lat_ms))

    # Gates focus on the directly observable synthetic latent variables. Angle is a
    # stand-in target to exercise the future kinematics interface, not a hardware claim.
    pass_mechanics = bool(rmse[2] < 0.08 and rmse[3] < 0.20)
    pass_shuffle = bool(mutant_rmse[0] > rmse[0] * 1.15)
    pass_flip = bool(flipped_rmse[3] > rmse[3] * 1.25)
    pass_latency = bool(p95 < 10.0)
    pass_geometry = bool(geometry_rmse[2] < 0.05 and geometry_rmse[3] < 0.08)

    result = {
        "schema": "capture.radar_motion_seed_qualification/1",
        "status": "PASS"
        if all([pass_mechanics, pass_shuffle, pass_flip, pass_latency, pass_geometry])
        else "FAIL",
        "evidence_ceiling": "SYNTHETIC_ONLY_NOT_HARDWARE_VALIDATION",
        "history_frames": history,
        "synthetic_holdout_rmse": dict(zip(target_names, [float(v) for v in rmse], strict=True)),
        "shuffled_label_rmse": dict(
            zip(target_names, [float(v) for v in mutant_rmse], strict=True)
        ),
        "doppler_flip_rmse": dict(
            zip(target_names, [float(v) for v in flipped_rmse], strict=True)
        ),
        "changed_geometry_holdout_rmse": dict(
            zip(target_names, [float(v) for v in geometry_rmse], strict=True)
        ),
        "high_noise_stress_rmse": dict(
            zip(target_names, [float(v) for v in stress_rmse], strict=True)
        ),
        "negative_controls": {
            "shuffled_labels_rejected": pass_shuffle,
            "doppler_sign_flip_rejected": pass_flip,
            "changed_geometry_direct_latents_pass": pass_geometry,
        },
        "latency_ms": {
            "median": median,
            "p95": p95,
            "20hz_budget": 50.0,
            "gate": 10.0,
        },
        "model": {
            "type": "ridge_seed",
            "training_evidence": model.training_evidence,
            "calibrated": model.calibrated,
            "hardware_validated": model.hardware_validated,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if output_model is not None:
        output_model.parent.mkdir(parents=True, exist_ok=True)
        model.save(output_model)
        print(f"wrote synthetic-only model: {output_model}", file=sys.stderr)
    return 0 if result["status"] == "PASS" else 1


def live_attach(model_path: Path | None, seconds: float) -> int:
    from capture_protocol.control_client import ControlClient
    from capture_protocol.generated.capture.v1 import preview_pb2
    from capture_protocol.generated.capture.v1.common_pb2 import MessageType

    model = LinearKinematicsModel.load(model_path) if model_path else None
    if model is not None and not model.hardware_validated:
        print(
            "MODEL GUARD: artifact is not hardware-validated; learned outputs will be labeled "
            "PROVISIONAL_MODEL_OUTPUT."
        )
    history = model.history if model is not None else 8
    featurizer = RadarMotionFeaturizer(history=history)

    client = ControlClient()
    client.connect()
    radars = [
        s
        for s in client.list_sources().sources
        if s.source_id.startswith("radar.")
        and (s.streams[0].modality if s.streams else "") != "radar_doppler"
    ]
    if not radars:
        print("no FMCW radar.* source")
        return 2
    sid = radars[0].source_id
    print(f"ATTACH_ONLY source={sid} alias={radars[0].alias!r}")
    print("No session/config/source-selection mutations will be made.")
    client.subscribe_status(include_preview=True, health_interval_ms=1000)

    deadline = time.monotonic() + seconds
    count = 0
    lat: list[float] = []
    while time.monotonic() < deadline:
        event = client.poll_event(timeout_s=0.3)
        if event is None:
            continue
        mt, payload = event
        if mt != int(MessageType.MESSAGE_TYPE_PREVIEW_FRAME):
            continue
        frame = preview_pb2.PreviewFrame()
        frame.ParseFromString(payload)
        if frame.source_id != sid or not frame.HasField("matrix"):
            continue
        m = frame.matrix
        if m.row_axis != "range" or m.col_axis != "doppler":
            continue
        matrix = np.asarray(m.values, dtype=np.float64).reshape(int(m.rows), int(m.cols))
        t0 = time.perf_counter_ns()
        desc, stack = featurizer.push(matrix)
        prediction = model.predict(stack) if model is not None else None
        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
        lat.append(elapsed_ms)
        count += 1
        out = {
            "frame": count,
            "latency_ms": elapsed_ms,
            "motion": desc.as_dict(),
        }
        if prediction is not None:
            out["kinematics"] = {
                "label": "HARDWARE_VALIDATED"
                if model.hardware_validated
                else "PROVISIONAL_MODEL_OUTPUT",
                "values": prediction,
            }
        print(json.dumps(out, sort_keys=True))

    if not count:
        print(
            "NO_RD_PREVIEW_FRAMES: attach-only mode requires an already-running range_doppler preview"
        )
        return 3
    print(
        json.dumps(
            {
                "frames": count,
                "latency_ms_median": float(np.median(lat)),
                "latency_ms_p95": float(np.percentile(lat, 95)),
                "learned_model_used": model is not None,
            },
            sort_keys=True,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--synthetic", action="store_true", help="run deterministic synthetic qualification"
    )
    mode.add_argument(
        "--live-attach", action="store_true", help="attach read-only to existing RD preview"
    )
    p.add_argument("--model", type=Path, help="optional ridge .npz model")
    p.add_argument(
        "--write-synthetic-model", type=Path, help="write synthetic-only fixture model"
    )
    p.add_argument("--seconds", type=float, default=10.0, help="live attach duration")
    args = p.parse_args(argv)
    if args.synthetic:
        return synthetic_gate(args.write_synthetic_model)
    return live_attach(args.model, max(0.5, args.seconds))


if __name__ == "__main__":
    raise SystemExit(main())
