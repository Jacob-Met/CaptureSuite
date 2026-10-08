# SPDX-License-Identifier: GPL-3.0-only
"""Real QC jobs retain prior results when a replacement cannot be published."""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
from pathlib import Path
from typing import Any

import pytest
from capture_analysis import jobs

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"
SENTINEL = b"previous native job marker\x00\xff\n"


def tree_bytes(root: Path) -> dict[str, tuple[str, bytes | str]]:
    """Snapshot membership, empty directories, link targets, and file bytes."""
    if not root.is_dir():
        return {".": ("missing", "")}
    result: dict[str, tuple[str, bytes | str]] = {".": ("directory", "")}
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[name] = ("symlink", str(path.readlink()))
        elif path.is_dir():
            result[name] = ("directory", "")
        else:
            result[name] = ("file", path.read_bytes())
    return result


def assert_tree_retained(root: Path, expected: dict[str, Any]) -> None:
    actual = tree_bytes(root)
    changes = sorted(key for key in actual.keys() | expected.keys()
                     if actual.get(key) != expected.get(key))
    assert not changes, f"Tree changed at {root}: {changes}"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def package(tmp_path: Path) -> Path:
    destination = tmp_path / "mini.mmsession"
    shutil.copytree(FIXTURE, destination)
    return destination


@pytest.fixture()
def previous_job(package: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    raw_before = tree_bytes(package / "sources")
    result = jobs.run(
        package,
        jobs.JobParams(command="qc", overwrite_job_id="qc-test",
                       extra={"review_case": "previous"}),
    )
    assert result.status in {"completed", "completed_with_warnings"}
    assert result.job_dir == package / "processing" / "jobs" / "qc-test"
    assert load_json(result.job_dir / "reports" / "qc.json")["streamCount"] == 2
    assert len(list((package / "sources").rglob("*.mcap"))) == 2
    (result.job_dir / "review-sentinel.bin").write_bytes(SENTINEL)
    (result.job_dir / "retained-empty-directory").mkdir()
    assert_tree_retained(package / "sources", raw_before)
    return result.job_dir, tree_bytes(result.job_dir), raw_before


def replacement_params() -> jobs.JobParams:
    return jobs.JobParams(command="qc", overwrite_job_id="qc-test",
                          extra={"review_case": "replacement"})


def assert_failed_attempt(
    package: Path,
    previous: tuple[Path, dict[str, Any], dict[str, Any]],
    error_text: str,
    *,
    retained_at: Path | None = None,
) -> Path:
    old_dir, old_tree, raw_tree = previous
    assert_tree_retained(retained_at or old_dir, old_tree)
    assert_tree_retained(package / "sources", raw_tree)
    jobs_dir = old_dir.parent
    attempts = []
    for path in jobs_dir.iterdir():
        manifest_path = path / "job_manifest.json"
        if path != old_dir and manifest_path.is_file():
            manifest = load_json(manifest_path)
            if manifest.get("status") == "failed":
                attempts.append((path, manifest))
    assert len(attempts) == 1, "Failed replacement must remain separately recorded"
    attempt, manifest = attempts[0]
    assert manifest["jobId"] == attempt.name
    assert manifest["jobId"] != "qc-test"
    assert error_text in "\n".join(manifest["errors"])
    params = load_json(attempt / "params.json")
    assert params["overwriteJobId"] == "qc-test"
    assert params["extra"]["review_case"] == "replacement"
    assert error_text in (attempt / "logs" / "job.log").read_text(encoding="utf-8")
    for output in manifest["outputs"]:
        if output["relativePath"] == "job_manifest.json":
            continue
        data = (attempt / output["relativePath"]).read_bytes()
        assert len(data) == output["bytes"]
        assert hashlib.sha256(data).hexdigest() == output["sha256"]
    return attempt


def test_partial_qc_failure_preserves_previous_results(
    package: Path, previous_job, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_html(_report):
        raise RuntimeError("injected HTML report failure")

    with monkeypatch.context() as patch:
        patch.setattr(jobs, "render_qc_html", fail_html)
        with pytest.raises(RuntimeError, match="injected HTML report failure"):
            jobs.run(package, replacement_params())

    attempt = assert_failed_attempt(package, previous_job, "injected HTML report failure")
    assert load_json(attempt / "reports" / "qc.json")["streamCount"] == 2
    assert not (attempt / "reports" / "qc.html").exists()


def test_cancellation_after_real_report_write_preserves_previous_results(
    package: Path, previous_job, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancel = threading.Event()
    write_output = jobs._write_output
    wrote_report = False

    def cancel_after_report(job_dir, relative, data, kind, outputs):
        nonlocal wrote_report
        result = write_output(job_dir, relative, data, kind, outputs)
        if relative == "reports/qc.json":
            assert result.is_file()
            wrote_report = True
            cancel.set()
        return result

    with monkeypatch.context() as patch:
        patch.setattr(jobs, "_write_output", cancel_after_report)
        with pytest.raises(InterruptedError, match="analysis cancelled"):
            jobs.run(package, replacement_params(), cancel=cancel)
    assert wrote_report
    assert_failed_attempt(package, previous_job, "analysis cancelled")


def test_cancellation_from_manifest_callback_preserves_previous_results(
    package: Path, previous_job,
) -> None:
    cancel = threading.Event()
    stages: list[str] = []

    def progress(stage: str, _fraction: float) -> None:
        stages.append(stage)
        if stage == "manifest":
            cancel.set()

    with pytest.raises(InterruptedError, match="analysis cancelled"):
        jobs.run(package, replacement_params(), progress=progress, cancel=cancel)
    assert "manifest" in stages
    assert_failed_attempt(package, previous_job, "analysis cancelled")


def test_promotion_rename_failure_restores_previous_results(
    package: Path, previous_job, monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_dir = previous_job[0]
    rename = Path.rename
    injected = False

    def fail_first_promotion(source: Path, target) -> Path:
        nonlocal injected
        # Match the public destination; do not depend on a staging/backup name.
        if not injected and Path(target).absolute() == old_dir.absolute():
            injected = True
            raise OSError("injected replacement rename failure")
        return rename(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "rename", fail_first_promotion)
        with pytest.raises(OSError, match="injected replacement rename failure"):
            jobs.run(package, replacement_params())
    assert injected, "The native destination rename was not exercised"
    assert_failed_attempt(package, previous_job, "injected replacement rename failure")


def test_final_progress_callback_failure_preserves_previous_results(
    package: Path, previous_job,
) -> None:
    stages: list[str] = []

    def progress(stage: str, _fraction: float) -> None:
        stages.append(stage)
        if stage == "done":
            raise RuntimeError("injected final progress callback failure")

    with pytest.raises(RuntimeError, match="injected final progress callback failure"):
        jobs.run(package, replacement_params(), progress=progress)
    assert "done" in stages
    assert_failed_attempt(package, previous_job, "injected final progress callback failure")


def test_failed_promotion_and_restoration_report_recoverable_previous_tree(
    package: Path, previous_job, monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_dir, old_tree, _raw_tree = previous_job
    rename = Path.rename
    failures = 0

    def fail_all_renames_to_destination(source: Path, target) -> Path:
        nonlocal failures
        if Path(target).absolute() == old_dir.absolute():
            failures += 1
            raise OSError("injected destination rename failure")
        return rename(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "rename", fail_all_renames_to_destination)
        with pytest.raises(OSError, match="injected destination rename failure") as raised:
            jobs.run(package, replacement_params())
    assert failures >= 2, "Both publication and attempted restoration must be exercised"
    markers = [path for path in old_dir.parent.rglob("review-sentinel.bin")
               if path.read_bytes() == SENTINEL]
    assert len(markers) == 1, "The previous result must remain recoverable exactly once"
    retained = markers[0].parent
    assert retained != old_dir
    assert_tree_retained(retained, old_tree)
    assert str(retained) in str(raised.value), "Error must identify the recoverable previous job"
    assert_failed_attempt(
        package, previous_job, "injected destination rename failure", retained_at=retained,
    )


def test_successful_replacement_publishes_new_results(package: Path, previous_job) -> None:
    old_dir, old_tree, raw_tree = previous_job
    result = jobs.run(package, replacement_params())
    assert result.status in {"completed", "completed_with_warnings"}
    assert result.job_dir == old_dir
    assert result.job_id == "qc-test"
    assert load_json(old_dir / "job_manifest.json")["jobId"] == "qc-test"
    assert load_json(old_dir / "params.json")["extra"]["review_case"] == "replacement"
    assert load_json(old_dir / "reports" / "qc.json")["streamCount"] == 2
    assert (old_dir / "reports" / "qc.html").is_file()
    assert not (old_dir / "review-sentinel.bin").exists()
    assert tree_bytes(old_dir) != old_tree
    assert_tree_retained(package / "sources", raw_tree)
    assert {path.name for path in old_dir.parent.iterdir()} == {"qc-test"}


def test_post_commit_cleanup_failure_keeps_successful_replacement(
    package: Path, previous_job, monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_dir, old_tree, raw_tree = previous_job
    remove_tree = shutil.rmtree
    retained_previous: list[Path] = []

    def fail_removing_previous(path, *args, **kwargs):
        # Detect the previous result by its bytes, independent of backup names.
        directory = Path(path)
        for marker in directory.rglob("review-sentinel.bin"):
            if marker.read_bytes() == SENTINEL:
                retained_previous.append(marker.parent)
                raise OSError("injected previous-result cleanup failure")
        return remove_tree(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(shutil, "rmtree", fail_removing_previous)
        result = jobs.run(package, replacement_params())
    assert retained_previous, "Previous-result cleanup was not exercised"
    assert result.status in {"completed", "completed_with_warnings"}
    assert result.job_dir == old_dir
    assert load_json(old_dir / "job_manifest.json")["status"] == result.status
    assert load_json(old_dir / "params.json")["extra"]["review_case"] == "replacement"
    assert not (old_dir / "review-sentinel.bin").exists()
    assert_tree_retained(retained_previous[0], old_tree)
    assert_tree_retained(package / "sources", raw_tree)


def test_new_failed_job_remains_recorded(package: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw_tree = tree_bytes(package / "sources")

    def fail_html(_report):
        raise RuntimeError("injected new-job report failure")

    with monkeypatch.context() as patch:
        patch.setattr(jobs, "render_qc_html", fail_html)
        with pytest.raises(RuntimeError, match="injected new-job report failure"):
            jobs.run(package, jobs.JobParams(command="qc"))
    records = list((package / "processing" / "jobs").glob("*/job_manifest.json"))
    assert len(records) == 1
    manifest = load_json(records[0])
    assert manifest["jobId"] == records[0].parent.name
    assert manifest["status"] == "failed"
    assert "injected new-job report failure" in "\n".join(manifest["errors"])
    assert load_json(records[0].parent / "reports" / "qc.json")["streamCount"] == 2
    assert_tree_retained(package / "sources", raw_tree)
