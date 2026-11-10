import json
import subprocess
import sys
from pathlib import Path

import pytest
from capture_analysis import collect_qc, hash_sources_tree
from capture_protocol.generated.capture.v1.data import imu_frame_pb2
from test_phase_b_features import ROOT, _replace_payload_segment, _write_emg_imu_package


@pytest.mark.parametrize(
    "sources,expected,exit_code",
    [
        ([], ["sim.emg.main", "sim.imu.upper"], 2),
        (["sim.emg.main"], ["sim.emg.main"], 0),
        (["sim.imu.upper"], ["sim.imu.upper"], 2),
    ],
)
def test_actual_qc_source_selection_controls_report_and_strict_exit(
    tmp_path: Path, sources, expected, exit_code
):
    package = _write_emg_imu_package(tmp_path / "scoped.mmsession")
    frame = imu_frame_pb2.ImuFrame()
    frame.sensors.add(sensor_id="missing")
    _replace_payload_segment(
        package,
        source_id="sim.imu.upper",
        stream_id="sim.imu.upper.frames",
        schema_name="imu.frame/1",
        message=frame,
    )
    before = hash_sources_tree(package)
    args = [
        sys.executable,
        str(ROOT / "tools/run_analysis.py"),
        "qc",
        str(package),
        "--inspect-payloads",
        "--strict-warnings",
        "--overwrite-job-id",
        "selected",
    ]
    if sources:
        args.extend(["--sources", *sources])
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == exit_code, result.stdout + result.stderr
    reports = package / "processing/jobs/selected/reports"
    report = json.loads((reports / "qc.json").read_text())
    assert sorted(report["trafficLights"]) == expected
    assert sorted(s["sourceId"] for s in report["streams"]) == expected
    assert report["sourceCount"] == len(expected)
    assert report["selectedSources"] == sources
    assert ("IMU orientation unavailable" in (reports / "qc.html").read_text()) == (
        "sim.imu.upper" in expected
    )
    assert hash_sources_tree(package) == before


def test_unknown_qc_source_does_not_silently_report_empty_success(tmp_path: Path):
    package = _write_emg_imu_package(tmp_path / "unknown.mmsession")
    with pytest.raises(ValueError, match="unknown QC source IDs: typo"):
        collect_qc(package, sources=["typo"])


def test_selected_source_gap_counts_do_not_include_other_source(tmp_path: Path):
    from test_qc_gap_details import gap, write_gaps

    package = _write_emg_imu_package(tmp_path / "gaps.mmsession")
    write_gaps(package, gap(closed=False, endSessionTimeNs=None))
    selected = collect_qc(package, sources=["sim.imu.upper"]).to_dict()
    assert selected["gaps"] == []
    assert selected["openGapCount"] == selected["closedGapCount"] == 0
    assert not any("gap" in warning for warning in selected["warnings"])
    emg = collect_qc(package, sources=["sim.emg.main"]).to_dict()
    assert emg["openGapCount"] == 1
    assert len(emg["gaps"]) == 1
    assert emg["trafficLights"] == {"sim.emg.main": "warn"}
