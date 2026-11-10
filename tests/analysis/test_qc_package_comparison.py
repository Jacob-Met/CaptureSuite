# SPDX-License-Identifier: GPL-3.0-only
"""Cross-session evidence through the actual command and real encoded MCAP."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

from capture_analysis.qc import collect_qc
from capture_analysis.qc_packages import create_qc_package_review

from tests.analysis.test_payload_inspection_qc import SEGMENT, _package, _write_mcap

ROOT = Path(__file__).resolve().parents[2]


def _files(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*") if p.is_file()
    }


def test_mixed_payload_review_keeps_native_failures_and_later_valid_data(tmp_path: Path) -> None:
    valid = _package(tmp_path / "good")
    bad = _package(tmp_path / "bad")
    structure = _package(tmp_path / "structure", schema="custom.force/1")
    _write_mcap(valid, values=[1.0, 2.0, 3.0, 4.0], times=[100, 200])
    _write_mcap(bad, values=[1.0, math.nan], times=[100])
    _write_mcap(structure, values=[8.0, 9.0], times=[100])
    selected = [bad, tmp_path / "missing.mmsession", structure, valid, valid]
    before = {str(p): _files(p) for p in (bad, structure, valid)}
    output = tmp_path / "review"

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/analysis_bundle_entry.py"), "review",
         "--inspect-payloads", "--strict-warnings", "--output", str(output),
         *map(str, selected)], cwd=ROOT, capture_output=True, text=True, check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    review = json.loads((output / "review.json").read_text())
    assert review["schemaId"] == "capture.qc_package_review/2"
    assert review["inspectPayloads"] is True
    assert (review["packageCount"], review["collectedCount"], review["failedCount"]) == (5, 4, 1)
    entries = review["packages"]
    assert [e["ordinal"] for e in entries] == [1, 2, 3, 4, 5]
    assert entries[0]["status"] == "collected"
    assert entries[0]["qc"]["streams"][0]["payloadInspection"]["status"] == "failed"
    assert entries[1]["status"] == "failed" and entries[1]["reports"] is None
    assert entries[2]["qc"]["streams"][0]["payloadInspection"]["status"] == "mcap_messages_checked"
    assert entries[3]["qc"]["streams"][0]["payloadInspection"]["sampleFramesChecked"] == 2
    expected = collect_qc(valid, inspect_payloads=True).to_dict()
    assert entries[3]["qc"] == entries[4]["qc"] == expected
    assert (output / "reports/004-qc.html").is_file()
    assert (output / "reports/005-qc.html").is_file()
    html = (output / "index.html").read_text()
    assert "Structure only" in html and "0 / 1 streams decoded" in html
    assert "Payload inspection failed" in html and "NaN or infinity" in html
    assert before == {str(p): _files(p) for p in (bad, structure, valid)}
    assert not any((p / "processing").exists() for p in (bad, structure, valid))


def test_metadata_does_not_misrepresent_decode_and_strict_warns_after_inspection(
    tmp_path: Path,
) -> None:
    package = _package(tmp_path)
    _write_mcap(package, values=[1.0, math.inf], times=[100])
    before = (package / SEGMENT).read_bytes()
    metadata = tmp_path / "metadata"
    inspection = tmp_path / "inspection"
    command = [
        sys.executable, str(ROOT / "tools/analysis_bundle_entry.py"), "review",
        "--strict-warnings", str(package),
    ]
    first = subprocess.run(
        [*command, "--output", str(metadata)], cwd=ROOT,
        capture_output=True, text=True, check=False,
    )
    second = subprocess.run(
        [*command, "--inspect-payloads", "--output", str(inspection)], cwd=ROOT,
        capture_output=True, text=True, check=False,
    )
    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 2, second.stdout + second.stderr
    assert "recorded samples were not inspected" in (metadata / "index.html").read_text()
    assert "0 / 1 streams decoded" in (metadata / "index.html").read_text()
    assert json.loads((inspection / "review.json").read_text())["failedCount"] == 0
    assert (package / SEGMENT).read_bytes() == before


def test_review_is_outside_all_inputs_and_never_replaces_an_old_review(tmp_path: Path) -> None:
    package = _package(tmp_path)
    _write_mcap(package, values=[1.0, 2.0], times=[100])
    output = tmp_path / "saved"
    create_qc_package_review([package], output, inspect_payloads=True)
    before = _files(tmp_path)
    for destination in (output, package / "review"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/review_qc_packages.py"),
             str(package), "--output", str(destination)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        assert result.returncode == 2
    assert _files(tmp_path) == before


def test_report_text_is_literal_and_empty_streams_are_not_a_clean_recording(tmp_path: Path) -> None:
    package = _package(tmp_path)
    manifest = json.loads((package / "manifest.json").read_text())
    manifest["sessionId"] = '<img src=x onerror="alert(1)">'
    (package / "manifest.json").write_text(json.dumps(manifest))
    # A selected session with no stream descriptors must stay visibly incomplete.
    for p in (package / "sources").rglob("stream.json"):
        p.unlink()
    review = create_qc_package_review([package], tmp_path / "review", inspect_payloads=True)
    html = (tmp_path / "review/index.html").read_text()
    assert review["packages"][0]["status"] == "collected"
    assert "No streams found" in html
    assert "<img src=x" not in html
    assert "&lt;img src=x" in html
