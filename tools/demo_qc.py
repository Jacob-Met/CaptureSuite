#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Run the existing QC engine on a COPY of the bundled synthetic mini-session.

No daemon, GUI, physical device, account, patient data or acquisition required.
A new output directory is required; existing output is never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

# Reuse the established CLI's package seating; do not install global modules.
from run_analysis import ROOT, JobParams, run

FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def create_demo(output: Path) -> dict[str, Any]:
    from capture_analysis import hash_sources_tree

    output = output.resolve()
    fixture = FIXTURE.resolve()
    if output == fixture or output.is_relative_to(fixture):
        raise ValueError("Output cannot be inside the original fixture")
    before = tree_hashes(fixture)
    if not before:
        raise FileNotFoundError("Bundled synthetic fixture is missing or empty")
    output.mkdir(parents=False, exist_ok=False)
    package = output / "synthetic-demo.mmsession"
    try:
        shutil.copytree(fixture, package)
        copied_before = hash_sources_tree(package)
        result = run(package, JobParams(command="qc", overwrite_job_id="demo-qc"))
        if hash_sources_tree(package) != copied_before:
            raise RuntimeError("QC changed copied raw sources; output is not accepted")
        if result.status not in ("completed", "completed_with_warnings"):
            raise RuntimeError(f"QC did not complete: {result.status}")
        reports = [
            result.job_dir / "reports" / "qc.html",
            result.job_dir / "reports" / "qc.json",
            result.job_dir / "job_manifest.json",
        ]
        receipt = {
            "classification": "synthetic_fixture_demonstration",
            "status": result.status,
            "original_fixture_sha256": before,
            "copied_raw_source_sha256": copied_before,
            "reports_sha256": {
                f.relative_to(output).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
                for f in reports
            },
            "limitations": (
                "No hardware capture, clinical accuracy, or whole-application qualification."
            ),
        }
        (output / "DEMO-RECEIPT.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
        return receipt
    finally:
        if tree_hashes(fixture) != before:
            raise RuntimeError(
                "Original fixture changed during execution; investigate concurrent mutation"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory under an existing parent")
    args = parser.parse_args(argv)
    try:
        result = create_demo(args.output)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Demo not accepted: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
