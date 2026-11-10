# SPDX-License-Identifier: GPL-3.0-only
"""Saved analyst reports must show the actual job outcome without changing QC."""

from __future__ import annotations

import json
from html import escape
from html.parser import HTMLParser
from pathlib import Path

import pytest
from capture_analysis import JobParams, hash_sources_tree, jobs, run
from test_job_output_provenance import _assert_inventory
from test_phase_b_features import _write_emg_imu_package


class _JobSection(HTMLParser):
    def __init__(self, page: str):
        super().__init__()
        self.state = None
        self.feed(page)

    def handle_starttag(self, _tag, attrs):
        values = dict(attrs)
        if values.get("id") == "analysis-job":
            self.state = values.get("data-job-status")


def _saved(job_dir: Path) -> tuple[dict, dict, str]:
    manifest = json.loads((job_dir / "job_manifest.json").read_text())
    qc = json.loads((job_dir / "reports/qc.json").read_text())
    page = (job_dir / "reports/qc.html").read_text()
    _assert_inventory(job_dir, manifest)
    return manifest, qc, page


def test_real_imu_feature_warning_is_visible_beside_unchanged_qc(tmp_path: Path) -> None:
    package = _write_emg_imu_package(tmp_path / "partial.mmsession", second_sensor_frames=15)
    before = hash_sources_tree(package)
    result = run(package, JobParams(command="features", overwrite_job_id="partial"))
    manifest, qc, page = _saved(result.job_dir)
    assert result.status == manifest["status"] == "completed_with_warnings"
    assert qc["warnings"] == []
    assert set(qc["trafficLights"].values()) == {"ok"}
    warning = next(w for w in manifest["warnings"] if "IMU feature support incomplete" in w)
    assert escape(warning) in page
    assert _JobSection(page).state == result.status
    assert hash_sources_tree(package) == before


def test_actual_manifest_validation_warning_is_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _write_emg_imu_package(tmp_path / "validation.mmsession")
    schema_dir = tmp_path / "future-schema"
    schema_dir.mkdir()
    (schema_dir / "analysis_job.schema.json").write_text(
        json.dumps({"type": "object", "required": ["requiredByFutureSchema"]})
    )
    monkeypatch.setattr(jobs, "SCHEMA_DIR", schema_dir)
    result = run(package, JobParams(command="qc", overwrite_job_id="validation"))
    manifest, qc, page = _saved(result.job_dir)
    assert qc["warnings"] == []
    assert result.status == "completed_with_warnings"
    warning = next(w for w in manifest["warnings"] if "manifest schema validation" in w)
    assert "requiredByFutureSchema" in warning
    assert escape(warning) in page
    assert _JobSection(page).state == result.status


@pytest.mark.parametrize("failure_stage", ["processing", "done"])
def test_failed_job_replaces_running_or_completed_report(
    tmp_path: Path, failure_stage: str
) -> None:
    package = _write_emg_imu_package(tmp_path / "failed.mmsession", second_sensor_frames=15)

    def late_failure(stage, _fraction):
        if stage == "done":
            raise RuntimeError("late analysis publication callback failed")

    params = JobParams(
        command="kinematics" if failure_stage == "processing" else "features",
        overwrite_job_id="failure",
    )
    with pytest.raises(
        (ValueError, RuntimeError),
        match="requires extra.pose_job_id|late analysis publication callback failed",
    ):
        run(package, params, progress=late_failure if failure_stage == "done" else None)
    job_dir = package / "processing/jobs/failure"
    manifest, qc, page = _saved(job_dir)
    assert manifest["status"] == "failed"
    assert _JobSection(page).state == "failed"
    assert all(escape(error) in page for error in manifest["errors"])
    assert qc["warnings"] == []
    if failure_stage == "done":
        assert any("IMU feature support incomplete" in w for w in manifest["warnings"])
        assert all(escape(warning) in page for warning in manifest["warnings"])


def test_report_failure_does_not_mask_original_processing_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _write_emg_imu_package(tmp_path / "two-failures.mmsession")
    renderer = jobs.render_qc_html

    def fail_failed_report(qc, *, job=None):
        if job is not None and job["status"] == "failed":
            raise OSError("secondary report write failure")
        return renderer(qc, job=job)

    monkeypatch.setattr(jobs, "render_qc_html", fail_failed_report)
    with pytest.raises(ValueError, match="requires extra.pose_job_id") as raised:
        run(package, JobParams(command="kinematics", overwrite_job_id="two-failures"))
    assert any("secondary report write failure" in note for note in raised.value.__notes__)
    manifest, _qc, page = _saved(package / "processing/jobs/two-failures")
    assert manifest["status"] == "failed"
    assert "requires extra.pose_job_id" in manifest["errors"][0]
    assert _JobSection(page).state == "running"  # never a falsely completed report
