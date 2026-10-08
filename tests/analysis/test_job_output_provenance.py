# SPDX-License-Identifier: GPL-3.0-only
"""Finalized analysis artifacts must agree with the persisted output inventory."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from capture_analysis import JobParams, hash_sources_tree, run

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def package(tmp_path: Path) -> Path:
    destination = tmp_path / "provenance.mmsession"
    shutil.copytree(ROOT / "tests" / "fixtures" / "mini_session", destination)
    return destination


def _manifest(job_dir: Path) -> dict:
    return json.loads((job_dir / "job_manifest.json").read_text(encoding="utf-8"))


def _assert_inventory(job_dir: Path, manifest: dict) -> None:
    outputs = manifest["outputs"]
    listed = [row["relativePath"] for row in outputs]
    actual = {
        path.relative_to(job_dir).as_posix()
        for path in job_dir.rglob("*")
        if path.is_file() and path != job_dir / "job_manifest.json"
    }
    assert len(listed) == len(set(listed)), "Each output needs one final receipt"
    assert set(listed) == actual
    for row in outputs:
        content = (job_dir / row["relativePath"]).read_bytes()
        assert row["bytes"] == len(content), row["relativePath"]
        assert row["sha256"] == hashlib.sha256(content).hexdigest(), row["relativePath"]


def test_recorded_hashes_describe_final_output_bytes(package: Path) -> None:
    result = run(package, JobParams(command="qc", overwrite_job_id="hashes"))
    for row in _manifest(result.job_dir)["outputs"]:
        data = (result.job_dir / row["relativePath"]).read_bytes()
        assert row["sha256"] == hashlib.sha256(data).hexdigest(), row["relativePath"]
        assert row["bytes"] == len(data), row["relativePath"]


def test_persisted_manifest_matches_return_value(package: Path) -> None:
    result = run(package, JobParams(command="qc", overwrite_job_id="same-manifest"))
    assert _manifest(result.job_dir) == result.manifest


def test_completed_job_inventories_all_produced_artifacts(package: Path) -> None:
    before = hash_sources_tree(package)
    result = run(package, JobParams(command="qc", overwrite_job_id="complete"))
    _assert_inventory(result.job_dir, _manifest(result.job_dir))
    assert hash_sources_tree(package) == before


def test_overwrite_describes_replacement_artifacts(package: Path) -> None:
    run(package, JobParams(command="qc", overwrite_job_id="replace", extra={"revision": 1}))
    result = run(
        package,
        JobParams(command="qc", overwrite_job_id="replace", extra={"revision": 2}),
    )
    assert json.loads((result.job_dir / "params.json").read_text())["extra"] == {"revision": 2}
    assert _manifest(result.job_dir) == result.manifest
    _assert_inventory(result.job_dir, result.manifest)


def test_failed_job_inventories_diagnostic_log(package: Path) -> None:
    before = hash_sources_tree(package)
    with pytest.raises(ValueError, match="requires extra.pose_job_id"):
        run(package, JobParams(command="kinematics", overwrite_job_id="failed"))
    job_dir = package / "processing" / "jobs" / "failed"
    manifest = _manifest(job_dir)
    assert manifest["status"] == "failed"
    assert "ERROR:" in (job_dir / "logs" / "job.log").read_text()
    _assert_inventory(job_dir, manifest)
    assert hash_sources_tree(package) == before


def test_late_failure_records_final_diagnostic_bytes(package: Path) -> None:
    def fail_before_manifest(stage: str, _fraction: float) -> None:
        if stage == "manifest":
            raise RuntimeError("injected finalization failure")

    with pytest.raises(RuntimeError, match="injected finalization failure"):
        run(
            package,
            JobParams(command="qc", overwrite_job_id="late-failure"),
            progress=fail_before_manifest,
        )
    job_dir = package / "processing" / "jobs" / "late-failure"
    manifest = _manifest(job_dir)
    assert manifest["status"] == "failed"
    assert "injected finalization failure" in (job_dir / "logs" / "job.log").read_text()
    _assert_inventory(job_dir, manifest)


def test_done_callback_failure_preserves_prior_job_and_attempt_inventory(package: Path) -> None:
    before = hash_sources_tree(package)
    first = run(
        package, JobParams(command="qc", overwrite_job_id="retained", extra={"revision": 1})
    )
    previous_tree = {
        path.relative_to(first.job_dir).as_posix(): None if path.is_dir() else path.read_bytes()
        for path in first.job_dir.rglob("*")
    }

    def fail_before_publication(stage: str, _fraction: float) -> None:
        if stage == "done":
            raise RuntimeError("injected completion callback failure")

    with pytest.raises(RuntimeError, match="injected completion callback failure") as raised:
        run(
            package,
            JobParams(command="qc", overwrite_job_id="retained", extra={"revision": 2}),
            progress=fail_before_publication,
        )
    assert {
        path.relative_to(first.job_dir).as_posix(): None if path.is_dir() else path.read_bytes()
        for path in first.job_dir.rglob("*")
    } == previous_tree
    assert _manifest(first.job_dir)["status"] == first.status
    assert json.loads((first.job_dir / "params.json").read_text())["extra"] == {"revision": 1}
    _assert_inventory(first.job_dir, _manifest(first.job_dir))

    attempts = list(first.job_dir.parent.glob(".attempt_*"))
    assert len(attempts) == 1
    attempt = attempts[0]
    manifest = _manifest(attempt)
    assert manifest["jobId"] == attempt.name
    assert manifest["status"] == "failed"
    assert "injected completion callback failure" in (attempt / "logs" / "job.log").read_text()
    _assert_inventory(attempt, manifest)
    params = json.loads((attempt / "params.json").read_text())
    assert params["overwriteJobId"] == "retained"
    assert params["extra"] == {"revision": 2}
    assert any(str(attempt) in note for note in raised.value.__notes__)
    assert hash_sources_tree(package) == before
