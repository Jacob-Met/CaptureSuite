#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Discover retained analysis jobs and their measured-table handoff paths."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs/python" / name)
    for name in ("capture_analysis", "capture_session", "capture_protocol")
]

from capture_analysis.retained_jobs import list_retained_jobs  # noqa: E402


def main(
    argv: list[str] | None = None,
    *,
    prog: str | None = None,
    export_command: list[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Find saved analysis jobs without rerunning the recording",
        epilog="Exit 2 indicates unreadable saved metadata; failed historical jobs remain visible.",
    )
    parser.add_argument(
        "package", type=Path, help="session package directory, including relocated ones"
    )
    parser.add_argument(
        "--limit", type=int, default=20, help="newest jobs to show (default 20; 0 all)"
    )
    parser.add_argument("--json", action="store_true", help="print structured job/table inventory")
    parser.add_argument(
        "--columns", action="store_true", help="show exact table column names and units"
    )
    args = parser.parse_args(argv)
    export_command = export_command or [sys.executable, str(ROOT / "tools/export_feature_table.py")]
    try:
        result = list_retained_jobs(args.package, limit=args.limit)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Saved analysis: {result['packagePath']}")
        print(f"Showing {result['shownJobs']} of {result['totalJobs']} jobs, newest first")
        print("Read-only retained metadata; raw sources are not required or validated.")
        if not result["totalJobs"]:
            print("No saved analysis jobs found. Run features, qc or all to create results.")
        for job in result["jobs"]:
            state = job["recordedStatus"] or "unknown recorded status"
            print(f"\n{job['jobId']} | {state} | {job['createdUtc'] or 'date unavailable'}")
            print(f"  Saved directory: {job['jobPath']}")
            for key, label in (
                ("warnings", "Warning"),
                ("errors", "Error"),
                ("problems", "UNREADABLE"),
            ):
                for message in job[key]:
                    print(f"  {label}: {message}")
            print(f"  Saved feature tables: {len(job['tables'])}")
            for table in job["tables"]:
                print(
                    f"    {table['sourceId'] or '?'} / {table['streamId'] or '?'} "
                    f"| {table['rows']} rows | {len(table['columns'])} columns"
                )
                print(f"    {table['relativePath']}")
                if args.columns:
                    for column in table["columns"]:
                        print(f"      {column['name']} [{column['units']}]")
            if job["tables"]:
                command = shlex.join([*export_command, job["jobPath"], "--list"])
                print(f"  Inspect/select: {command}")
        if result["hiddenInternalEntries"]:
            print(
                f"\nInternal attempt/backup entries not listed: {result['hiddenInternalEntries']}"
            )
        if result["shownJobs"] < result["totalJobs"]:
            print("Use --limit 0 to list the complete retained history.")
    return 2 if any(job["readStatus"] == "unreadable" for job in result["jobs"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
