#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Inspect and export columns from a completed retained Analysis job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / name)
    for name in ("capture_analysis", "capture_session", "capture_protocol")
]

from capture_analysis.feature_table_export import (  # noqa: E402
    export_feature_table,
    list_feature_tables,
)


def main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Inspect and export selected feature columns from a completed analysis job",
        epilog=("Start with JOB_DIR --list to see saved tables and exact column names. "
                "Time selection filters existing rows by the chosen column; "
                "feature windows are not clipped or recomputed."),
    )
    parser.add_argument("job_dir", type=Path, help="PACKAGE/processing/jobs/JOB_ID")
    parser.add_argument("--list", action="store_true", help="list saved tables, columns and units")
    parser.add_argument("--json", action="store_true", help="print --list as machine-readable JSON")
    parser.add_argument("--table", help="exact feature_parquet relativePath shown by --list")
    parser.add_argument(
        "--column", action="append", dest="columns",
        help="exact column name; repeat in export order (default: all retained columns)",
    )
    parser.add_argument("--time-column", help="integer nanosecond column used for row selection")
    parser.add_argument("--start-ns", type=int, help="inclusive recorded time, integer nanoseconds")
    parser.add_argument("--end-ns", type=int, help="exclusive recorded time in integer nanoseconds")
    parser.add_argument("--format", choices=("csv", "parquet", "both"), default="both")
    parser.add_argument("--output", type=Path, help="new directory outside the session package")
    args = parser.parse_args(argv)
    if args.list:
        if (args.table or args.output or args.columns or args.time_column
                or args.start_ns is not None or args.end_ns is not None):
            parser.error("--list cannot be combined with export or time-selection flags")
    elif not args.table or not args.output:
        parser.error("export requires --table and --output; use --list to inspect saved tables")
    elif args.json:
        parser.error("--json is only available with --list")
    try:
        if args.list:
            listing = list_feature_tables(args.job_dir)
            if args.json:
                print(json.dumps(listing, ensure_ascii=False, indent=2))
            else:
                print(f"Job {listing['jobId']} ({listing['jobStatus']})")
                print(f"Saved feature tables: {len(listing['tables'])}")
                for table in listing["tables"]:
                    rows = table["rows"] if table["rows"] is not None else "not recorded"
                    print(f"\n{table['relativePath']}\n  Rows: {rows}")
                    if table["sourceId"] is not None:
                        print(f"  Source: {table['sourceId']}")
                    if table["streamId"] is not None:
                        print(f"  Stream: {table['streamId']}")
                    print("  Columns:")
                    for column in table["columns"]:
                        print(f"    {column['name']} [{column['units']}]")
                if listing["tables"]:
                    print("\nChoose --table PATH and repeat --column NAME in export order.")
                    print("Use --output NEW_DIRECTORY outside the session package.")
                else:
                    print("This saved job contains no feature tables. Run a features or all job.")
            return 0
        result = export_feature_table(
            args.job_dir, args.table, args.output,
            columns=args.columns, output_format=args.format,
            time_column=args.time_column, start_ns=args.start_ns, end_ns=args.end_ns,
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
    print(f"readme={args.output.resolve() / 'README.html'}")
    if "timeSelection" in result["selection"]:
        scope = result["selection"]["timeSelection"]
        print(f"time_region={scope['column']} [{scope['startNs']}, {scope['endNs']}) ns")
        print(f"source_rows={scope['sourceRows']}; existing rows selected, windows not recomputed")
    print(f"source_job_status={result['source']['jobStatus']}")
    if result["source"]["jobStatus"] == "completed_with_warnings":
        print("Source analysis has warnings; review source/job_manifest.json.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
