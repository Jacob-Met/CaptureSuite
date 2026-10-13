#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Repeat the exact public-extractor receiving courses from an unpacked kit."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    bundle = Path(sys.argv[1] if len(sys.argv) > 1 else __file__).resolve()
    if bundle.is_file():
        bundle = bundle.parent
    manifest = json.loads((bundle / "manifest.json").read_text())
    entries = manifest["files"]
    expected = {entry["path"] for entry in entries}
    actual = {path.relative_to(bundle).as_posix() for path in bundle.rglob("*")
              if path.is_file()}
    require(actual == expected | {"manifest.json"}, "Bundle file inventory changed")
    for entry in entries:
        relative = Path(entry["path"])
        require(not relative.is_absolute() and ".." not in relative.parts,
                "Manifest path must remain within the bundle")
        path = bundle / relative
        require(not any(part.is_symlink() for part in [path, *path.parents]),
                "Bundle paths must be ordinary files/directories")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"],
                f"Bundle file differs: {relative}")

    candidate = bundle / "candidate"
    oracle = candidate / "docs/receiving/imu-timestamps-d788ccfb3bfe/check_public_median.py"

    def run(command: list[str], source: Path) -> subprocess.CompletedProcess:
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(
            str(source / "libs/python" / package)
            for package in ("capture_analysis", "capture_session", "capture_protocol"))
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(command, cwd=source, env=environment,
                              capture_output=True, text=True, timeout=60)

    tests = run([sys.executable, "-B", "-m", "unittest", "discover", "-s",
                 str(candidate / "tests/analysis"), "-p",
                 "test_imu_feature_timestamps.py", "-v"], candidate)
    require(tests.returncode == 0 and re.search(r"Ran 7 tests\b", tests.stderr),
            "Maintained public-extractor tests failed:\n" + tests.stdout + tests.stderr)
    courses = []
    for version in ("base", "candidate"):
        for optimized in (False, True):
            command = [sys.executable, "-B"] + (["-O"] if optimized else [])
            course = run(command + [str(oracle), str(bundle / version)], bundle / version)
            require(course.returncode in (0, 1), "Oracle could not run: " + course.stderr)
            try:
                result = json.loads(course.stdout)
            except ValueError as exc:
                raise RuntimeError("Oracle did not return a result: " + course.stderr) from exc
            require(result["cases"] == 512 and result["input_unchanged"]
                    and result["features_unchanged"], "Oracle course was incomplete")
            require(result["source_sha256"] == manifest[version + "_source_sha256"],
                    "Oracle imported a different production source")
            if version == "base":
                require(course.returncode == 1 and result["failures"] > 0,
                        "Original-source defect was not reproduced")
            else:
                require(course.returncode == 0 and result["failures"] == 0,
                        "Candidate failed the independent oracle")
            courses.append({"version": version, "optimized": optimized, **result})
    print(json.dumps({"status": "passed", "verified_files": len(entries),
                      "maintained_test_methods": 7, "courses": courses}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"Receiving failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
