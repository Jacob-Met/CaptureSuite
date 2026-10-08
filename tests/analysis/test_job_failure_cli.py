# SPDX-License-Identifier: GPL-3.0-only
"""Real CLI failures retain the job runner's recovery notes."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_analysis.py"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_cli_reports_retained_failed_replacement(tmp_path: Path) -> None:
    package = tmp_path / "session with spaces.mmsession"
    shutil.copytree(FIXTURE, package)
    successful = _cli("qc", str(package), "--overwrite-job-id", "previous")
    assert successful.returncode == 0, successful.stdout + successful.stderr
    assert "job_id=previous" in successful.stdout

    failed = _cli(
        "kinematics",
        str(package),
        "--pose-job",
        "missing-pose-job",
        "--overwrite-job-id",
        "previous",
    )
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "FAIL: analysis job not found: missing-pose-job" in failed.stderr
    attempts = list((package / "processing" / "jobs").glob(".attempt_*"))
    assert len(attempts) == 1
    attempt = attempts[0]
    assert str(attempt) in failed.stderr, "CLI must expose the retained failure location"
    manifest = json.loads((attempt / "job_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["jobId"] == attempt.name
    assert not failed.stdout


def test_cli_plain_failure_keeps_exit_status(tmp_path: Path) -> None:
    package = tmp_path / "missing.mmsession"
    failed = _cli("qc", str(package))
    assert failed.returncode == 1
    assert failed.stderr.startswith("FAIL: ")
    assert str(package) in failed.stderr
    assert not failed.stdout
