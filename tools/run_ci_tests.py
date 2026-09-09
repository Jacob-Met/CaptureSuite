#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Run the existing Python CI suite and retain exit-aware, hash-bound evidence.

Progress reaching 100% is not success: both process exit and JUnit must agree.
Outputs use a fresh run directory. No real device, user data, or cloud action is
added by this wrapper; the suite's existing daemon availability rules still apply.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_XML_BYTES = 8 * 1024 * 1024
GITHUB_CONTEXT_KEYS = (
    "GITHUB_ACTIONS",
    "GITHUB_EVENT_NAME",
    "GITHUB_SHA",
    "GITHUB_REF",
    "GITHUB_HEAD_REF",
    "GITHUB_BASE_REF",
    "GITHUB_RUN_ID",
    "GITHUB_WORKFLOW_REF",
)


def github_context(env: dict[str, str] | None = None) -> dict[str, str]:
    """Record public Actions ref provenance without environment/token sprawl."""
    source = os.environ if env is None else env
    return {key: source[key] for key in GITHUB_CONTEXT_KEYS if source.get(key)}


def summarize(junit: Path, process_exit: int | None) -> dict:
    report = {
        "schema": "capturesuite.test-receipt.v1",
        "accepted": False,
        "process_exit": process_exit,
        "counts": None,
        "junit_sha256": None,
        "problems": [],
        "scope": "Process and test-evidence consistency, not clinical validation",
    }
    problems = report["problems"]
    if type(process_exit) is not int or process_exit != 0:
        problems.append("Test process did not exit successfully")
    try:
        with junit.open("rb") as stream:
            raw = stream.read(MAX_XML_BYTES + 1)
        if len(raw) > MAX_XML_BYTES:
            raise ValueError("JUnit exceeds the supported size limit")
        report["junit_sha256"] = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8-sig")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("DTD/entity declarations are not supported")
        root = ET.fromstring(text)
        if root.tag == "testsuite":
            suites = [root]
        elif root.tag == "testsuites":
            suites = list(root.findall("testsuite"))
        else:
            raise ValueError("Unrecognized JUnit root")
        if not suites or any(s.find("testsuite") is not None for s in suites):
            raise ValueError("Expected non-nested test suites")
        totals = dict(tests=0, passed=0, failures=0, errors=0, skipped=0)
        for suite in suites:
            cases = suite.findall("testcase")
            local = dict(tests=len(cases), passed=0, failures=0, errors=0, skipped=0)
            for case in cases:
                failure = case.find("failure") is not None
                error = case.find("error") is not None
                skipped = case.find("skipped") is not None
                local["failures"] += int(failure)
                local["errors"] += int(error)
                local["skipped"] += int(skipped)
                local["passed"] += int(not (failure or error or skipped))
            for key in ("tests", "failures", "errors", "skipped"):
                declared = suite.get(key)
                if declared is not None and int(declared) != local[key]:
                    raise ValueError(f"JUnit {key} count disagrees with case evidence")
            for key in totals:
                totals[key] += local[key]
        report["counts"] = totals
        if totals["tests"] == 0 or totals["passed"] == 0:
            problems.append("No executed passing test cases")
        if totals["failures"] or totals["errors"]:
            problems.append("JUnit contains failing or errored cases")
    except (OSError, ET.ParseError, ValueError, TypeError) as exc:
        problems.append(f"JUnit unavailable or invalid: {type(exc).__name__}")
    report["accepted"] = not problems
    return report


def source_snapshot(root: Path) -> dict:
    """Bind the working bytes, including uncommitted edits, not just HEAD's label."""
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=10
    ).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=root, text=True, timeout=10
        ).strip()
    )
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        text=True,
        encoding="utf-8",
        timeout=10,
    ).split("\0")
    files = {}
    for name in sorted(set(n for n in names if n)):
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Source snapshot does not follow symbolic or escaping paths")
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {
        "commit": commit,
        "worktree_dirty": dirty,
        "tree_sha256": hashlib.sha256(canonical).hexdigest(),
        "files": files,
    }


def main() -> int:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "build/evidence" / f"python-{stamp}-{uuid.uuid4().hex[:8]}"
    out.mkdir(parents=True, exist_ok=False)
    junit = out / "pytest.xml"
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    before = source_snapshot(ROOT)
    started = time.perf_counter()
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-q",
        "-ra",
        "--ignore=tests/kill_tests",
        f"--junitxml={junit}",
    ]
    with (out / "pytest.log").open("w", encoding="utf-8") as log:
        try:
            result = subprocess.run(
                command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300
            )
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = None
    print((out / "pytest.log").read_text(encoding="utf-8", errors="replace"))
    report = summarize(junit, code)
    report["seconds"] = time.perf_counter() - started
    report["created_at"] = datetime.now(UTC).isoformat()
    report["run_directory"] = out.relative_to(ROOT).as_posix()
    report["log_sha256"] = hashlib.sha256((out / "pytest.log").read_bytes()).hexdigest()
    after = source_snapshot(ROOT)
    report["source_commit"] = before["commit"]
    report["source_worktree_dirty"] = before["worktree_dirty"]
    report["source_tree_sha256"] = before["tree_sha256"]
    report["source_file_count"] = len(before["files"])
    report["github"] = github_context(env)
    report["source_unchanged_during_test"] = before == after
    if before != after:
        report["problems"].append("Source changed while tests were running")
        report["accepted"] = False
    (out / "source-manifest.json").write_text(
        json.dumps(before, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (out / "receipt.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
