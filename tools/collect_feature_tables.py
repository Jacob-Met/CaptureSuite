#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Collect labeled saved measurements for an external analysis tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / name)
    for name in ("capture_analysis", "capture_session", "capture_protocol")
]

from capture_analysis.feature_collection import (  # noqa: E402
    FeatureTableInput,
    collect_feature_tables,
)


def main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Collect saved measurements across labeled conditions or sessions.",
        epilog=(
            "Find table paths and column names with export-table JOB_DIR --list. "
            "Rows retain their original values and session clocks; no statistical test is implied."
        ),
    )
    parser.add_argument(
        "--input",
        nargs=3,
        action="append",
        required=True,
        metavar=("CONDITION", "JOB_DIR", "TABLE"),
        help="repeat for each saved table, in desired row order; quote paths or labels with spaces",
    )
    parser.add_argument(
        "--column",
        action="append",
        dest="columns",
        help="exact measurement column; repeat in order (default: all, requiring matching inputs)",
    )
    parser.add_argument("--format", choices=("csv", "parquet", "both"), default="both")
    parser.add_argument(
        "--output", type=Path, required=True, help="new folder outside all sessions"
    )
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="exit 2 if source warnings, missing context or differing settings require review",
    )
    args = parser.parse_args(argv)
    try:
        result = collect_feature_tables(
            [FeatureTableInput(label, Path(job), table) for label, job, table in args.input],
            args.output,
            columns=args.columns,
            output_format=args.format,
        )
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        for note in getattr(exc, "__notes__", ()):
            print(note, file=sys.stderr)
        return 1
    print(f"status={result['status']}")
    print(f"dir={args.output.resolve()}")
    print(f"inputs={len(result['inputs'])}")
    print(f"rows={result['selection']['rows']}")
    for item in result["inputs"]:
        print(
            f"input[{item['input']}]={item['condition']!r} "
            f"session={item['sessionId']} job={item['jobId']} "
            f"rows={item['rows']} status={item['jobStatus']} "
            f"warnings={len(item['warnings'])}"
        )
    for notice in result["notices"]:
        print(f"NOTICE: {notice}", file=sys.stderr)
    print("Collected feature windows are not independent experimental replicates.")
    return 2 if args.strict_warnings and result["status"] == "completed_with_warnings" else 0


if __name__ == "__main__":
    raise SystemExit(main())
