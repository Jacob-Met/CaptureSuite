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


@pytest.mark.parametrize("selection", ["custom", "checkpoint"])
def test_report_selection_matches_resolved_job_while_qc_stays_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selection: str
) -> None:
    import shutil

    import pandas as pd
    from capture_analysis import collect_qc
    from test_checkpoint_sections import _checkpoints, _write_imu_package

    package = _write_imu_package(tmp_path / "sections.mmsession", _checkpoints())
    # Add an unselected recorded source; QC must retain both sources while
    # the actual analysis selects one source over the resolved 2..5 s section.
    original = package / "sources/sim.imu.upper"
    other = package / "sources/sim.imu.reference"
    shutil.copytree(original, other)
    for descriptor in (other / "source.json", *other.rglob("stream.json")):
        doc = json.loads(descriptor.read_text())
        doc["sourceId"] = "sim.imu.reference"
        descriptor.write_text(json.dumps(doc))
    manifest_path = package / "manifest.json"
    package_manifest = json.loads(manifest_path.read_text())
    package_manifest["sourceIds"].append("sim.imu.reference")
    manifest_path.write_text(json.dumps(package_manifest))
    integrity_path = package / "integrity.json"
    integrity = json.loads(integrity_path.read_text())
    extra = dict(integrity["files"][0])
    extra["path"] = extra["path"].replace("/sim.imu.upper/", "/sim.imu.reference/")
    integrity["files"].append(extra)
    integrity_path.write_text(json.dumps(integrity))
    before = hash_sources_tree(package)
    recorded_contexts = []
    renderer = jobs.render_qc_html

    def record_context(qc, *, job=None):
        if job is not None:
            recorded_contexts.append(job)
        return renderer(qc, job=job)

    monkeypatch.setattr(jobs, "render_qc_html", record_context)
    params = JobParams(
        command="all", overwrite_job_id="selected",
        sources=["sim.imu.upper"], extra={"inspect_payloads": True},
        start_session_ns=2_000_000_000 if selection == "custom" else None,
        end_session_ns=5_000_000_000 if selection == "custom" else None,
        checkpoint_section="Reach – 左" if selection == "checkpoint" else None,
    )
    result = run(package, params)
    manifest, qc, page = _saved(result.job_dir)
    assert qc == collect_qc(package, inspect_payloads=True).to_dict()
    assert qc["streamCount"] == 2
    assert [row["payloadInspection"]["sampleFramesChecked"] for row in qc["streams"]] == [81, 81]
    assert set(qc["trafficLights"]) == {"sim.imu.upper", "sim.imu.reference"}
    assert manifest["timeRange"]["startSessionNs"] == 2_000_000_000
    assert manifest["timeRange"]["endSessionNs"] == 5_000_000_000
    final = recorded_contexts[-1]
    assert final["timeRange"] == manifest["timeRange"]
    assert final["sourcesSelected"] == manifest["sourcesSelected"] == ["sim.imu.upper"]
    assert final["checkpointSection"] == params.checkpoint_section
    assert recorded_contexts[0]["timeRange"] is None
    assert "2.000000000" in page and "5.000000000" in page
    if selection == "checkpoint":
        assert "Reach – 左" in page
    assert _JobSection(page).state == result.status
    tables = list((result.job_dir / "features/imu").rglob("windows.parquet"))
    assert len(tables) == 1
    data = pd.read_parquet(tables[0])
    assert not data.empty
    assert data["t_mid_ns"].between(2_000_000_000, 5_000_000_000).all()
    assert hash_sources_tree(package) == before


def test_qc_only_job_preserves_intentional_source_selection(tmp_path: Path) -> None:
    package = _write_emg_imu_package(tmp_path / "qc-selected.mmsession")
    result = run(
        package, JobParams(command="qc", sources=["sim.imu.upper"],
                           extra={"inspect_payloads": True}, overwrite_job_id="qc-selected")
    )
    manifest, qc, page = _saved(result.job_dir)
    assert qc["streamCount"] == 1
    assert set(qc["trafficLights"]) == {"sim.imu.upper"}
    assert qc["streams"][0]["payloadInspection"]["sampleFramesChecked"] == 30
    assert manifest["sourcesSelected"] == ["sim.imu.upper"]
    assert _JobSection(page).state == result.status
