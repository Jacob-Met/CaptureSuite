#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""CLI for offline CaptureSuite analysis jobs (Phase A: qc)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / "capture_analysis"),
    str(ROOT / "libs" / "python" / "capture_session"),
    str(ROOT / "libs" / "python" / "capture_protocol"),
]

from capture_analysis.jobs import JobParams, run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline analysis for .mmsession packages")
    sub = ap.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("package", type=Path, help="path to .mmsession package")
        p.add_argument("--gap-policy", choices=("mask", "split", "fail"), default="mask")
        p.add_argument("--max-ram-bytes", type=int, default=2 * 1024**3)
        p.add_argument("--start-ns", type=int, default=None)
        p.add_argument("--end-ns", type=int, default=None)
        p.add_argument("--sources", nargs="*", default=[], help="limit to source ids")
        p.add_argument("--checkpoint-section", default=None)
        p.add_argument("--overwrite-job-id", default=None)
        p.add_argument(
            "--strict-warnings",
            action="store_true",
            help="exit 2 when status is completed_with_warnings",
        )

    p_qc = sub.add_parser("qc", help="inventory + gap/integrity QC report")
    add_common(p_qc)

    for name, help_ in (
        ("features", "extract features (Phase B)"),
        ("plots", "render figures (Phase B)"),
        ("all", "qc + features + plots (Phase B)"),
        ("pose", "video pose job (Phase D)"),
    ):
        p = sub.add_parser(name, help=help_)
        add_common(p)

    p_kin = sub.add_parser("kinematics", help="Tier A kinematics from pose job (Phase D2)")
    add_common(p_kin)
    p_kin.add_argument("--pose-job", required=True, dest="pose_job")
    p_kin.add_argument("--imu-fusion", action="store_true")

    p_ml = sub.add_parser("ml_bundle", help="aligned training windows (Phase E)")
    add_common(p_ml)
    p_ml.add_argument("--kinematics-job", required=True, dest="kinematics_job")
    p_ml.add_argument("--features-job", required=True, dest="features_job")
    p_ml.add_argument("--window-sec", type=float, default=1.0)
    p_ml.add_argument("--hop-sec", type=float, default=0.05)
    p_ml.add_argument("--grid-rate-hz", type=float, default=20.0)

    p_eval = sub.add_parser("eval", help="eval report from ml_bundle (Phase F)")
    add_common(p_eval)
    p_eval.add_argument("--ml-bundle-job", required=True, dest="ml_bundle_job")

    args = ap.parse_args(argv)
    extra: dict = {}
    if args.command == "kinematics":
        extra["pose_job_id"] = args.pose_job
        extra["imu_fusion"] = bool(getattr(args, "imu_fusion", False))
    elif args.command == "ml_bundle":
        extra["kinematics_job_id"] = args.kinematics_job
        extra["features_job_id"] = args.features_job
        extra["window_sec"] = args.window_sec
        extra["hop_sec"] = args.hop_sec
        extra["grid_rate_hz"] = args.grid_rate_hz
    elif args.command == "eval":
        extra["ml_bundle_job_id"] = args.ml_bundle_job

    params = JobParams(
        command=args.command,
        gap_policy=args.gap_policy,
        max_ram_bytes=args.max_ram_bytes,
        start_session_ns=args.start_ns,
        end_session_ns=args.end_ns,
        sources=list(args.sources or []),
        checkpoint_section=args.checkpoint_section,
        overwrite_job_id=args.overwrite_job_id,
        extra=extra,
    )
    try:
        result = run(args.package, params)
    except NotImplementedError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"job_id={result.job_id}")
    print(f"status={result.status}")
    print(f"dir={result.job_dir}")
    if result.qc:
        print(
            f"streams={result.qc.get('streamCount')} "
            f"gaps_open={result.qc.get('openGapCount')} "
            f"gaps_closed={result.qc.get('closedGapCount')} "
            f"warnings={len(result.qc.get('warnings') or [])}"
        )
    if result.status == "failed":
        return 1
    if result.status == "completed_with_warnings" and args.strict_warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
