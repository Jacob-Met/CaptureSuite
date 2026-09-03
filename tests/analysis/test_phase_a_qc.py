# SPDX-License-Identifier: GPL-3.0-only
"""Phase A: discover, QC, job manifest, immutability, RAM guard."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"


@pytest.fixture()
def package(tmp_path: Path) -> Path:
    dest = tmp_path / "mini.mmsession"
    shutil.copytree(FIXTURE, dest)
    return dest


def test_discover_streams_reads_descriptor_rate_and_units(package: Path) -> None:
    from capture_analysis import discover_streams

    refs = discover_streams(package)
    by_mod = {r.modality: r for r in refs}
    assert "emg" in by_mod
    assert by_mod["emg"].nominal_rate_hz == 2000.0
    assert by_mod["emg"].units == "mV"
    assert by_mod["emg"].data_schema_id == "emg.batch/1"
    assert by_mod["imu"].units == "a.u."
    assert by_mod["emg"].require_rate() == 2000.0


def test_require_rate_fails_when_missing() -> None:
    from capture_analysis.types import StreamRef

    ref = StreamRef(
        source_id="x",
        stream_id="y",
        modality="emg",
        data_schema_id="emg.batch/1",
        nominal_rate_hz=0.0,
        units="mV",
    )
    with pytest.raises(ValueError, match="invent a timebase"):
        ref.require_rate()


def test_ram_guard_trips() -> None:
    from capture_analysis.loaders.base import RamBudgetExceeded, guard_ram
    from capture_analysis.types import StreamRef

    ref = StreamRef(
        source_id="sim.emg.main",
        stream_id="batch",
        modality="emg",
        data_schema_id="emg.batch/1",
        nominal_rate_hz=2000.0,
        units="mV",
    )
    with pytest.raises(RamBudgetExceeded, match="sim.emg.main"):
        guard_ram(3 * 1024**3, max_ram_bytes=2 * 1024**3, stream=ref)


def test_qc_job_writes_manifest_and_reports(package: Path) -> None:
    from capture_analysis import JobParams, hash_sources_tree, run

    before = hash_sources_tree(package)
    result = run(package, JobParams(command="qc", overwrite_job_id="qc-test"))
    after = hash_sources_tree(package)

    assert before == after, "sources/** must be byte-identical after QC job"
    assert result.status in ("completed", "completed_with_warnings")
    assert (result.job_dir / "reports" / "qc.json").is_file()
    assert (result.job_dir / "reports" / "qc.html").is_file()
    assert (result.job_dir / "job_manifest.json").is_file()

    manifest = json.loads((result.job_dir / "job_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaId"] == "capture.analysis_job/1"
    assert manifest["sessionId"] == "mini-analysis-fixture"
    assert manifest["jobId"] == "qc-test"
    assert "emg" in manifest["modalities"]
    assert "imu" in manifest["modalities"]

    qc = json.loads((result.job_dir / "reports" / "qc.json").read_text(encoding="utf-8"))
    assert qc["streamCount"] == 2
    assert qc["manifestSha256"]


def test_analysis_job_schema_validates(package: Path) -> None:
    import jsonschema

    from capture_analysis import JobParams, run

    result = run(package, JobParams(command="qc", overwrite_job_id="qc-schema"))
    manifest = json.loads((result.job_dir / "job_manifest.json").read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "schemas" / "session" / "jsonschema" / "analysis_job.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.validate(manifest, schema)


def test_cli_qc(package: Path) -> None:
    import subprocess
    import sys

    py = Path(sys.executable)
    proc = subprocess.run(
        [
            str(py),
            str(ROOT / "tools" / "run_analysis.py"),
            "qc",
            str(package),
            "--overwrite-job-id",
            "cli-qc",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 2), proc.stdout + proc.stderr
    assert "job_id=cli-qc" in proc.stdout
    assert (package / "processing" / "jobs" / "cli-qc" / "reports" / "qc.json").is_file()
