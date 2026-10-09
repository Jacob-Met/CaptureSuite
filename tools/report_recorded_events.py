#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Write a standalone HTML view of a retained package's reader-returned records.

Usage: python tools/report_recorded_events.py PACKAGE OUTPUT.html
The output must be a new file outside the package, under an existing parent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

# Match the existing offline CLI's checkout-local package seating.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs" / "python" / "capture_session"))

from capture_session.package_reader import load_review_summary  # noqa: E402
from capture_session.recorded_events_html import render_recorded_events_html  # noqa: E402


def create_report(package: Path, output: Path) -> dict[str, object]:
    """Read original metadata and exclusively create a complete new report."""
    package = package.resolve(strict=True)
    if not package.is_dir():
        raise ValueError(f"package is not a directory: {package}")
    output = output.parent.resolve(strict=True) / output.name
    if output == package or output.is_relative_to(package):
        raise ValueError("report output must be outside the original package")
    if os.path.lexists(output):
        raise FileExistsError(f"output already exists: {output}")

    summary = load_review_summary(package)
    if summary.state not in ("finalized", "finalized_recovered"):
        raise ValueError(
            f"reader reported state {summary.state!r}; "
            "a report requires finalized or finalized_recovered"
        )
    data = render_recorded_events_html(summary).encode("utf-8")
    try:
        # Exclusive creation also preserves an output created after our first check.
        with output.open("xb") as stream:
            if stream.write(data) != len(data):
                raise OSError("short report write")
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        raise
    except OSError as exc:
        raise OSError(
            f"could not finish report {output}; any new partial file is retained: {exc}"
        ) from exc

    return {
        "status": "written",
        "package": str(package),
        "output": str(output),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "reported_state": summary.state,
        "records_returned": {
            "checkpoints": len(summary.checkpoints),
            "annotations": len(summary.annotations),
            "sync_anchors": len(summary.sync_anchors),
            "normalized_gaps": len(summary.gaps),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Retained package directory")
    parser.add_argument("output", type=Path, help="New standalone HTML file")
    args = parser.parse_args(argv)
    try:
        result = create_report(args.package, args.output)
    except Exception as exc:  # noqa: BLE001
        print(f"Report not written: {exc}", file=sys.stderr)
        return 1
    # ASCII JSON keeps literal paths representable on Windows console encodings.
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
