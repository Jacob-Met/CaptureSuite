# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path

import demo_qc
import pytest


def test_offline_demo_emits_reports_and_preserves_original(tmp_path: Path):
    before = demo_qc.tree_hashes(demo_qc.FIXTURE)
    out = tmp_path / "demo"
    receipt = demo_qc.create_demo(out)
    assert receipt["classification"] == "synthetic_fixture_demonstration"
    assert receipt["original_fixture_sha256"] == before == demo_qc.tree_hashes(demo_qc.FIXTURE)
    reports = receipt["reports_sha256"]
    assert len(reports) == 3
    for rel in reports:
        assert (out / rel).is_file()
    qc = json.loads(
        (out / "synthetic-demo.mmsession/processing/jobs/demo-qc/reports/qc.json").read_text()
    )
    assert qc["streamCount"] == 2
    assert json.loads((out / "DEMO-RECEIPT.json").read_text()) == receipt


def test_existing_output_is_preserved(tmp_path: Path):
    out = tmp_path / "existing"
    out.mkdir()
    marker = out / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        demo_qc.create_demo(out)
    assert marker.read_text() == "keep"
    assert list(out.iterdir()) == [marker]


def test_output_cannot_be_under_fixture():
    with pytest.raises(ValueError, match="original fixture"):
        demo_qc.create_demo(demo_qc.FIXTURE / "forbidden-output")


def test_engine_failure_preserves_original(tmp_path: Path, monkeypatch):
    before = demo_qc.tree_hashes(demo_qc.FIXTURE)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(demo_qc, "run", fail)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        demo_qc.create_demo(tmp_path / "failed-demo")
    assert demo_qc.tree_hashes(demo_qc.FIXTURE) == before


def test_missing_output_parent_reports_failure(tmp_path: Path):
    assert demo_qc.main([str(tmp_path / "missing" / "demo")]) == 1
