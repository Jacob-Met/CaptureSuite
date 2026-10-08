#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Export a selected retained Analysis feature table into a new directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs/python/capture_analysis"))

from capture_analysis.feature_table_export import export_feature_table  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export selected feature columns from a completed retained analysis job"
    )
    parser.add_argument("job_dir", type=Path, help="PACKAGE/processing/jobs/JOB_ID")
    parser.add_argument("--table", required=True, help="exact feature_parquet relativePath")
    parser.add_argument(
        "--column", action="append", dest="columns",
        help="exact column name; repeat in export order (default: all retained columns)",
    )
    parser.add_argument("--format", choices=("csv", "parquet", "both"), default="both")
    parser.add_argument("--output", type=Path, required=True, help="new external destination")
    args = parser.parse_args(argv)
    try:
        result = export_feature_table(
            args.job_dir, args.table, args.output,
            columns=args.columns, output_format=args.format,
        )
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        for note in getattr(exc, "__notes__", ()):
            print(note, file=sys.stderr)
        return 1
    print("status=completed")
    print(f"dir={args.output.resolve()}")
    print(f"rows={result['selection']['rows']}")
    print(f"columns={len(result['selection']['columns'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
