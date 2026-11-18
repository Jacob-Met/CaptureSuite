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


def _include_subtests(root: ET.Element, path: Path, xml_sha256: str) -> tuple[str, dict[str, int]]:
    """Expand folded cases in memory using independently observed pytest events."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_XML_BYTES + 1)
    if len(raw) > MAX_XML_BYTES:
        raise ValueError("Subtest evidence exceeds the supported size limit")
    evidence = json.loads(raw)
    if (evidence["schema"] != "capturesuite.pytest-subtests.v1"
            or evidence["junit_sha256"] != xml_sha256
            or not isinstance(evidence["parents"], list)):
        raise ValueError("Unrecognized or mismatched subtest evidence")
    sha256 = hashlib.sha256(raw).hexdigest()
    observed = dict(passed=0, failed=0, skipped=0)
    if not evidence["parents"]:
        return sha256, observed
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    if len(suites) != 1:
        raise ValueError("Expected one pytest suite for subtest evidence")
    suite = suites[0]
    parents = {}
    for case in suite.findall("testcase"):
        key = (case.get("classname"), case.get("name"))
        parents.setdefault(key, []).append(case)
    tags = {"passed": None, "failed": "failure", "skipped": "skipped"}
    for group in evidence["parents"]:
        key = (group["classname"], group["name"])
        matches = parents.pop(key, [])
        events = group["events"]
        if len(matches) != 1 or not isinstance(events, list) or not events:
            raise ValueError("Missing or ambiguous JUnit parent for subtest events")
        parent = matches[0]
        # Pytest appends failing/skipped subtests in event order, then the parent's outcome.
        outcomes = [tags[event["outcome"]] for event in events] + [tags[group["parent_outcome"]]]
        children = [child for child in parent if child.tag in ("error", "failure", "skipped")]
        if [child.tag for child in children] != [outcome for outcome in outcomes if outcome]:
            raise ValueError("JUnit and recorded subtest outcomes disagree")
        # Same-status siblings and a failed parent must retain their own native traceback.
        expected_failures = [
            event["failure_sha256"] for event in events if event["outcome"] == "failed"
        ]
        if group["parent_outcome"] == "failed":
            expected_failures.append(group["parent_failure_sha256"])
        actual_failures = [
            hashlib.sha256((child.text or "").encode("utf-8")).hexdigest()
            for child in children if child.tag == "failure"
        ]
        if expected_failures != actual_failures:
            raise ValueError("Recorded failure tracebacks disagree with native JUnit")
        children = iter(children)
        for index, (event, outcome) in enumerate(zip(events, outcomes[:-1], strict=True), 1):
            if type(event["ordinal"]) is not int or event["ordinal"] != index:
                raise ValueError("Missing or duplicate subtest event ordinal")
            if not isinstance(event["description"], str):
                raise ValueError("Missing subtest description")
            case = ET.SubElement(suite, "testcase", {
                "classname": key[0], "name": f"{key[1]} [subtest {index}]",
            })
            observed[event["outcome"]] += 1
            if outcome:
                child = next(children)
                parent.remove(child)
                case.append(child)
    return sha256, observed


def summarize(junit: Path, process_exit: int | None, *, subtests: Path | None = None) -> dict:
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
        if subtests is not None:
            report["subtests_sha256"], report["subtest_counts"] = _include_subtests(
                root, subtests, report["junit_sha256"]
            )
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
        if root.tag == "testsuites":
            for key in ("tests", "failures", "errors", "skipped"):
                declared = root.get(key)
                if declared is not None and int(declared) != totals[key]:
                    raise ValueError(f"JUnit aggregate {key} count disagrees with case evidence")
        report["counts"] = totals
        if totals["tests"] == 0 or totals["passed"] == 0:
            problems.append("No executed passing test cases")
        if totals["failures"] or totals["errors"]:
            problems.append("JUnit contains failing or errored cases")
    except (OSError, ET.ParseError, ValueError, TypeError, KeyError) as exc:
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
        "-p",
        "tools.ci_subtest_evidence",
        "tests",
        "-vv",
        "--durations=20",
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
    report = summarize(junit, code, subtests=junit.with_suffix(".subtests.json"))
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
