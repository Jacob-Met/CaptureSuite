# SPDX-License-Identifier: GPL-3.0-only
"""Real job admission must not claim an unimplemented alignment operation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from capture_analysis import JobParams, run
from capture_session.package_reader import load_review_summary

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mini_session"
ANCHOR = {
    "syncAnchorId": "synthetic-tap-250ms",
    "timestampNs": "250000000",
    "modalitiesTargeted": ["emg", "imu"],
    "mechanism": "manual",
    "metadata": {"classification": "synthetic_fixture"},
    "createdVia": "sync-request-test",
}
COMMANDS = ("qc", "features", "plots", "all", "pose", "kinematics", "ml_bundle", "eval")


@pytest.fixture()
def package(tmp_path: Path) -> Path:
    destination = tmp_path / "synthetic.mmsession"
    shutil.copytree(FIXTURE, destination)
    return destination


def _anchors(package: Path, present: bool) -> list[dict]:
    records = [ANCHOR] if present else []
    (package / "events" / "sync_anchors.json").write_text(
        json.dumps(records) + "\n", encoding="utf-8"
    )
    return records


def _snapshot(root: Path, *, exclude_processing: bool = False) -> dict:
    result = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if exclude_processing and (rel == "processing" or rel.startswith("processing/")):
            continue
        if path.is_symlink():
            result[rel] = ("symlink", str(path.readlink()))
        elif path.is_dir():
            result[rel] = ("directory", "")
        else:
            result[rel] = ("file", path.read_bytes())
    return result


@pytest.mark.parametrize("present", [False, True], ids=["no-anchors", "recorded-anchor"])
@pytest.mark.parametrize("explicit", [False, True], ids=["default", "explicit-false"])
def test_native_timestamp_qc_retains_anchor_inventory(
    package: Path, present: bool, explicit: bool
) -> None:
    anchors = _anchors(package, present)
    before = _snapshot(package, exclude_processing=True)
    params = JobParams(apply_sync_anchors=False) if explicit else None
    result = run(package, params)
    assert result.status == "completed"
    saved = json.loads((result.job_dir / "job_manifest.json").read_text(encoding="utf-8"))
    expected = {"applied": False, "anchors": []}
    assert result.manifest["syncAnchorsApplied"] == expected
    assert saved["syncAnchorsApplied"] == expected
    assert result.qc["syncAnchorCount"] == len(anchors)
    assert load_review_summary(package).sync_anchors == anchors
    assert _snapshot(package, exclude_processing=True) == before


@pytest.mark.parametrize("present", [False, True], ids=["no-anchors", "recorded-anchor"])
def test_requested_alignment_is_refused_without_producing_a_job(
    package: Path, present: bool
) -> None:
    _anchors(package, present)
    before = _snapshot(package)
    params = JobParams(apply_sync_anchors=True, overwrite_job_id="requested")
    params_before = params.to_dict()
    with pytest.raises(NotImplementedError, match="sync-anchor alignment is not implemented"):
        run(package, params)
    assert _snapshot(package) == before
    assert params.to_dict() == params_before


def test_rejected_alignment_preserves_the_complete_previous_job(package: Path) -> None:
    _anchors(package, True)
    previous = run(package, JobParams(overwrite_job_id="retained", extra={"revision": 1}))
    (previous.job_dir / "review-note.bin").write_bytes(b"retained review\x00\xff")
    (previous.job_dir / "retained-empty-directory").mkdir()
    before = _snapshot(package)
    request = JobParams(
        apply_sync_anchors=True, overwrite_job_id="retained", extra={"revision": 2}
    )
    with pytest.raises(NotImplementedError, match="sync-anchor alignment is not implemented"):
        run(package, request)
    assert _snapshot(package) == before
    assert not list(previous.job_dir.parent.glob(".attempt_*"))


@pytest.mark.parametrize("command", COMMANDS)
def test_unsupported_request_precedes_manifest_reads_and_progress(
    package: Path, command: str
) -> None:
    (package / "manifest.json").write_bytes(b"{malformed manifest")
    before = _snapshot(package)
    progress = []
    with pytest.raises(NotImplementedError, match="sync-anchor alignment is not implemented"):
        run(
            package,
            JobParams(command=command, apply_sync_anchors=True),
            progress=lambda stage, fraction: progress.append((stage, fraction)),
        )
    assert progress == []
    assert _snapshot(package) == before


@pytest.mark.parametrize("requested", [False, True])
def test_existing_unknown_command_admission_is_preserved(package: Path, requested: bool) -> None:
    before = _snapshot(package)
    with pytest.raises(NotImplementedError, match="command 'unknown' not supported yet"):
        run(package, JobParams(command="unknown", apply_sync_anchors=requested))
    assert _snapshot(package) == before
