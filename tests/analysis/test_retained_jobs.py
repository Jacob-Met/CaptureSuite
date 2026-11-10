# SPDX-License-Identifier: GPL-3.0-only
"""Saved history remains discoverable after relocation and mixed job failures."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from capture_analysis.retained_jobs import list_retained_jobs
from test_feature_table_export import ROOT, TABLE, inventory, make_job, write_json


def test_relocated_history_lists_tables_without_original_sources(tmp_path: Path) -> None:
    job, original = make_job(tmp_path)
    package = job.parents[2]
    moved = tmp_path / "moved package.mmsession"
    package.rename(moved)
    (moved / "raw.bin").unlink()
    before = inventory(moved)
    result = list_retained_jobs(moved)
    assert result["totalJobs"] == result["shownJobs"] == 1
    saved = result["jobs"][0]
    assert saved["readStatus"] == "ok"
    assert saved["recordedStatus"] == "completed_with_warnings"
    assert saved["warnings"] == ["synthetic provisional values"]
    assert saved["jobPath"] == str(moved / "processing/jobs/synthetic-job")
    assert saved["tables"][0]["relativePath"] == TABLE
    assert [c["name"] for c in saved["tables"][0]["columns"]] == original.column_names
    assert inventory(moved) == before


def test_mixed_history_preserves_failures_and_corrupt_metadata(tmp_path: Path) -> None:
    job, _ = make_job(tmp_path)
    jobs = job.parent
    failed = jobs / "failed-job"
    write_json(
        failed / "job_manifest.json",
        {
            "schemaId": "capture.analysis_job/1",
            "jobId": "failed-job",
            "status": "failed",
            "createdUtc": "2026-11-10T10:00:00Z",
            "errors": ["recording segment unavailable"],
        },
    )
    broken = jobs / "broken-job"
    broken.mkdir()
    (broken / "job_manifest.json").write_text("{ interrupted")
    (jobs / ".attempt-private").mkdir()
    result = list_retained_jobs(job.parents[2], limit=0)
    assert result["totalJobs"] == 3
    assert result["hiddenInternalEntries"] == 1
    assert result["jobs"][0]["jobId"] == "failed-job"
    by_id = {row["jobId"]: row for row in result["jobs"]}
    assert by_id["failed-job"]["errors"] == ["recording segment unavailable"]
    assert by_id["broken-job"]["readStatus"] == "unreadable"
    assert "invalid retained-job JSON" in by_id["broken-job"]["problems"][0]
    assert by_id["synthetic-job"]["tables"]
    assert list_retained_jobs(job.parents[2], limit=1)["shownJobs"] == 1


def test_changed_feature_metadata_is_reported_with_recorded_status(tmp_path: Path) -> None:
    job, _ = make_job(tmp_path)
    with (job / "features/_schema.json").open("a") as stream:
        stream.write(" ")
    row = list_retained_jobs(job.parents[2])["jobs"][0]
    assert row["recordedStatus"] == "completed_with_warnings"
    assert row["readStatus"] == "unreadable"
    assert "identity mismatch" in row["problems"][0]
    assert row["tables"] == []


def test_linked_job_is_visible_but_never_followed(tmp_path: Path) -> None:
    job, _ = make_job(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (job.parent / "linked-job").symlink_to(outside, target_is_directory=True)
    before = inventory(outside)
    result = list_retained_jobs(job.parents[2])
    linked = next(row for row in result["jobs"] if row["jobId"] == "linked-job")
    assert linked["readStatus"] == "unreadable"
    assert "without symlinks" in linked["problems"][0]
    assert inventory(outside) == before


def test_no_history_and_invalid_root_do_not_create_paths(tmp_path: Path) -> None:
    package = tmp_path / "empty"
    package.mkdir()
    assert list_retained_jobs(package)["jobs"] == []
    assert list(package.iterdir()) == []
    with pytest.raises(FileNotFoundError):
        list_retained_jobs(tmp_path / "absent")
    with pytest.raises(ValueError):
        list_retained_jobs(package, limit=-1)


def test_packaged_entry_exposes_readonly_history_and_errors(tmp_path: Path) -> None:
    job, _ = make_job(tmp_path)
    entry = [
        sys.executable,
        str(ROOT / "tools/analysis_bundle_entry.py"),
        "jobs",
        str(job.parents[2]),
    ]
    before = inventory(job.parents[2])
    result = subprocess.run([*entry, "--columns"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "synthetic provisional values" in result.stdout
    assert "t_ns [ns]" in result.stdout
    assert "Inspect/select:" in result.stdout
    assert str(ROOT / "tools/analysis_bundle_entry.py") in result.stdout
    assert "export-table" in result.stdout
    assert inventory(job.parents[2]) == before
    shutil.rmtree(job / "features")
    result = subprocess.run([*entry, "--json"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stdout)["jobs"][0]["readStatus"] == "unreadable"
