#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Run the built daemon/recovery integration tests with zero-skip evidence.

The C++ build and CTest run first. This runner then exercises the actual built
CaptureSuite daemon and session doctor in isolated per-test state. It does not
use physical capture devices or the operator's saved application state.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from run_ci_tests import github_context, source_snapshot, summarize

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_BINARIES = (
    Path("daemon/capture_daemon.exe"),
    Path("tools/session_doctor/session_doctor.exe"),
)
NATIVE_TESTS = (
    "tests/protocol/test_daemon_e2e.py::test_multi_modality_record_with_disconnect",
    "tests/protocol/test_daemon_e2e.py::test_bad_stop_token_rejected",
    "tests/protocol/test_daemon_e2e.py::test_config_schema_and_apply",
    "tests/protocol/test_daemon_e2e.py::test_start_all_ready_and_acknowledge_alert",
    "tests/protocol/test_daemon_e2e.py::test_concurrent_clients_served",
    "tests/kill_tests/test_kill_preserves_sealed.py::test_kill_preserves_sealed_segment",
)


def resolve_build(root: Path, raw: str | None) -> tuple[Path | None, list[str]]:
    errors: list[str] = []
    if not raw:
        return None, ["CAPTURE_TEST_BUILD_DIR must name the exact native build"]
    build = Path(raw)
    if not build.is_absolute():
        build = root / build
    try:
        build = build.resolve()
        build.relative_to(root.resolve())
    except (OSError, ValueError):
        return None, ["Native CI build must resolve inside the repository"]
    if not build.is_dir():
        return build, [f"Native CI build directory missing: {build}"]
    return build, errors


def inspect_binaries(build: Path | None) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []
    if build is None:
        return records, errors
    for relative in REQUIRED_BINARIES:
        path = build / relative
        if path.is_symlink() or not path.is_file():
            errors.append(f"Required native binary missing: {relative.as_posix()}")
            continue
        raw = path.read_bytes()
        records.append(
            {
                "path": relative.as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return records, errors


def evaluate(junit: Path, process_exit: int | None) -> dict:
    report = summarize(junit, process_exit)
    counts = report.get("counts") or {}
    if counts.get("skipped", 0):
        report["problems"].append("Native integration tests were skipped")
    report["accepted"] = not report["problems"]
    return report


def main() -> int:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "build/evidence" / f"native-{stamp}-{uuid.uuid4().hex[:8]}"
    out.mkdir(parents=True, exist_ok=False)
    junit = out / "pytest.xml"
    build, errors = resolve_build(ROOT, os.environ.get("CAPTURE_TEST_BUILD_DIR"))
    binaries, binary_errors = inspect_binaries(build)
    errors.extend(binary_errors)
    before = source_snapshot(ROOT)
    started = time.perf_counter()
    code: int | None = None
    log_path = out / "pytest.log"
    if not errors:
        env = dict(os.environ)
        env["QT_QPA_PLATFORM"] = "offscreen"
        command = [
            sys.executable,
            "-m",
            "pytest",
            *NATIVE_TESTS,
            "-q",
            "-ra",
            f"--junitxml={junit}",
        ]
        with log_path.open("w", encoding="utf-8") as log:
            try:
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=300,
                )
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = None
    else:
        log_path.write_text("\n".join(errors) + "\n", encoding="utf-8")
    report = evaluate(junit, code)
    report["schema"] = "capturesuite.native-test-receipt.v1"
    report["seconds"] = time.perf_counter() - started
    report["created_at"] = datetime.now(UTC).isoformat()
    report["run_directory"] = out.relative_to(ROOT).as_posix()
    report["binary_build"] = build.relative_to(ROOT).as_posix() if build else None
    report["binaries"] = binaries
    report["test_scope"] = list(NATIVE_TESTS)
    report["problems"] = errors + report["problems"]
    after = source_snapshot(ROOT)
    report["source_commit"] = before["commit"]
    report["source_worktree_dirty"] = before["worktree_dirty"]
    report["github"] = github_context()
    report["source_tree_sha256"] = before["tree_sha256"]
    report["source_unchanged_during_test"] = before == after
    if before != after:
        report["problems"].append("Source changed while native tests were running")
    report["accepted"] = not report["problems"]
    report["log_sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
    (out / "source-manifest.json").write_text(
        json.dumps(before, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (out / "receipt.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(log_path.read_text(encoding="utf-8", errors="replace"))
    print(json.dumps(report, indent=2))
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
