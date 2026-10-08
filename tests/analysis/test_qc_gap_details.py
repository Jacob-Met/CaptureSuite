# SPDX-License-Identifier: GPL-3.0-only
"""Recorded gaps remain attributable in native QC JSON, HTML, and CLI output."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from html import escape
from html.parser import HTMLParser
from pathlib import Path

import pytest
from capture_analysis import JobParams, collect_qc, run
from capture_analysis.report_html import render_qc_html

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "sim.emg.main"
STREAM = "sim.emg.main.batch"


@pytest.fixture()
def package(tmp_path: Path) -> Path:
    dest = tmp_path / "gaps.mmsession"
    shutil.copytree(ROOT / "tests/fixtures/mini_session", dest)
    return dest


def gap(**changes) -> dict:
    row = {
        "sourceId": SOURCE,
        "streamId": STREAM,
        "cause": "DISCONNECT",
        "startSessionTimeNs": "2000000000",
        "endSessionTimeNs": "4500000000",
        "closed": True,
        "estimatedLostCount": "5000",
    }
    row.update(changes)
    return row


def write_gaps(package: Path, *rows: dict, source: str = SOURCE) -> None:
    path = package / "sources" / source / "health/gaps.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def raw_hashes(package: Path) -> dict[str, str]:
    return {
        p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(package.rglob("*"))
        if p.is_file() and p.relative_to(package).parts[0] != "processing"
    }


class TableRows(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag, attrs) -> None:
        if tag == "tr":
            self.row = []
        elif tag == "td":
            self.cell = []

    def handle_data(self, data) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag) -> None:
        if tag == "td" and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def gap_html_row(qc: dict, cause: str = "DISCONNECT") -> list[str]:
    parsed = TableRows()
    parsed.feed(render_qc_html(qc))
    return next(row for row in parsed.rows if cause in row)


def test_closed_gap_is_attributed_in_json_and_source_status(package: Path) -> None:
    write_gaps(package, gap())
    qc = collect_qc(package).to_dict()
    assert qc["schemaId"] == "capture.analysis_qc/2"
    assert qc["gaps"] == [gap() | {"durationNs": "2500000000", "durationStatus": "known"}]
    assert (qc["openGapCount"], qc["closedGapCount"]) == (0, 1)
    assert qc["trafficLights"] == {SOURCE: "warn", "sim.imu.upper": "ok"}
    assert any(SOURCE in w and "gap" in w for w in qc["warnings"])


@pytest.mark.parametrize(
    ("start", "end", "closed", "duration", "status"),
    [
        (2, 5, True, "3", "known"),
        (0, 0, True, "0", "known"),
        (-1, 1, True, "2", "known"),
        (2**63 - 2, 2**63 - 1, True, "1", "known"),
        (2, None, False, None, "open"),
        (2, None, True, None, "missing_end"),
        (2, 5, False, None, "open"),
        (5, 2, True, None, "end_before_start"),
    ],
)
def test_duration_requires_a_closed_consistent_interval(
    package: Path, start, end, closed, duration, status
) -> None:
    write_gaps(package, gap(startSessionTimeNs=str(start),
                            endSessionTimeNs=None if end is None else str(end), closed=closed))
    detail = collect_qc(package).to_dict()["gaps"][0]
    assert detail["startSessionTimeNs"] == str(start)
    assert detail["endSessionTimeNs"] == (None if end is None else str(end))
    assert detail["closed"] is closed
    assert detail["durationNs"] == duration
    assert detail["durationStatus"] == status


def test_native_writer_keys_and_directory_source_fallback(package: Path) -> None:
    write_gaps(package, {"stream_id": STREAM, "cause": "WRITER_ERROR",
                         "start_session_time_ns": 10, "end_session_time_ns": 20})
    detail = collect_qc(package).to_dict()["gaps"][0]
    assert (detail["sourceId"], detail["streamId"], detail["cause"]) == (
        SOURCE, STREAM, "WRITER_ERROR"
    )
    assert (detail["closed"], detail["durationNs"], detail["estimatedLostCount"]) == (
        True, "10", "0"
    )


def test_causes_and_overlapping_records_are_preserved_separately(package: Path) -> None:
    causes = ["GAP_CAUSE_DISCONNECT", "GAP_CAUSE_SEQUENCE_LOSS", "GAP_CAUSE_OVERLOAD_DROP",
              "GAP_CAUSE_WRITER_ERROR", "GAP_CAUSE_UNKNOWN", "GAP_CAUSE_UNSPECIFIED"]
    write_gaps(package, *(gap(cause=c, estimatedLostCount=str(2**53 + i))
                          for i, c in enumerate(causes)))
    qc = collect_qc(package).to_dict()
    assert [row["cause"] for row in qc["gaps"]] == causes
    assert [row["estimatedLostCount"] for row in qc["gaps"]] == [
        str(2**53 + i) for i in range(len(causes))
    ]
    assert len(qc["gaps"]) == qc["closedGapCount"] == len(causes)
    assert qc["trafficLights"][SOURCE] == "warn"


def test_gap_cannot_downgrade_an_existing_failed_source(package: Path) -> None:
    for path in (package / "sources" / SOURCE).rglob("*.mcap"):
        path.unlink()
    write_gaps(package, gap())
    assert collect_qc(package).to_dict()["trafficLights"][SOURCE] == "fail"


def test_gap_source_without_a_discovered_stream_is_still_visible(package: Path) -> None:
    write_gaps(package, gap(sourceId="missing.sensor", streamId=""), source="missing.sensor")
    qc = collect_qc(package).to_dict()
    assert qc["gaps"][0]["sourceId"] == "missing.sensor"
    assert qc["gaps"][0]["streamId"] == ""
    assert qc["trafficLights"]["missing.sensor"] == "warn"
    assert qc["trafficLights"][SOURCE] == "ok"
    assert qc["sourceCount"] == 3 and qc["streamCount"] == 2


def test_no_gap_control_remains_green(package: Path) -> None:
    qc = collect_qc(package).to_dict()
    assert qc["gaps"] == []
    assert (qc["openGapCount"], qc["closedGapCount"]) == (0, 0)
    assert set(qc["trafficLights"].values()) == {"ok"}
    assert qc["warnings"] == []
    assert "No gap records listed" in render_qc_html(qc)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (2_000_000_000, 4_500_000_000, ["2.000000000", "4.500000000", "2.500000000"]),
        (-1, 1, ["-0.000000001", "0.000000001", "0.000000002"]),
        (2**63 - 2, 2**63 - 1, ["9223372036.854775806", "9223372036.854775807", "0.000000001"]),
    ],
)
def test_html_keeps_nanosecond_precision(package: Path, start, end, expected) -> None:
    write_gaps(package, gap(startSessionTimeNs=str(start), endSessionTimeNs=str(end)))
    row = gap_html_row(collect_qc(package).to_dict())
    assert row == [SOURCE, STREAM, "DISCONNECT", "closed", *expected, "5000"]


@pytest.mark.parametrize(("end", "closed"), [(None, False), (None, True), (1, True), (5, False)])
def test_html_unknown_duration_is_never_displayed_as_zero(package: Path, end, closed) -> None:
    write_gaps(package, gap(startSessionTimeNs="2", endSessionTimeNs=end, closed=closed))
    row = gap_html_row(collect_qc(package).to_dict())
    assert "unknown" in row[6].lower()
    assert row[6] != "0.000000000"


def test_html_escapes_recorded_identifiers_and_cause(package: Path) -> None:
    source = '<img src=x onerror="fail()">'
    stream = '<script>fail()</script>'
    cause = 'unexpected <cause> & "quoted"'
    write_gaps(package, gap(sourceId=source, streamId=stream, cause=cause))
    qc = collect_qc(package).to_dict()
    html = render_qc_html(qc)
    assert qc["gaps"][0]["sourceId"] == source
    assert qc["gaps"][0]["streamId"] == stream
    assert qc["gaps"][0]["cause"] == cause
    for value in (source, stream, cause):
        assert escape(value) in html
        assert value not in html
    assert gap_html_row(qc, cause)[:3] == [source, stream, cause]


def test_legacy_html_distinguishes_missing_details_from_no_gaps(package: Path) -> None:
    old = collect_qc(package).to_dict()
    old.pop("gaps", None)
    old["schemaId"] = "capture.analysis_qc/1"
    old["closedGapCount"] = 2
    html = render_qc_html(old)
    assert "Gap details are not available" in html
    assert "No gap records listed" not in html
    assert "0/2" in html


def test_native_job_binds_report_bytes_and_preserves_all_raw_inputs(package: Path) -> None:
    write_gaps(package, gap())
    before = raw_hashes(package)
    result = run(package, JobParams(command="qc", overwrite_job_id="gap-details"))
    assert raw_hashes(package) == before
    assert result.status == "completed_with_warnings"
    qc_path = result.job_dir / "reports/qc.json"
    qc = json.loads(qc_path.read_text())
    assert qc == result.qc and qc["gaps"][0]["cause"] == "DISCONNECT"
    report = next(row for row in result.manifest["outputs"]
                  if row["relativePath"] == "reports/qc.json")
    assert report["sha256"] == hashlib.sha256(qc_path.read_bytes()).hexdigest()
    assert report["bytes"] == len(qc_path.read_bytes())


def test_actual_cli_emits_gap_details_and_preserves_inputs(package: Path) -> None:
    write_gaps(package, gap())
    before = raw_hashes(package)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_analysis.py"), "qc", str(package),
         "--overwrite-job-id", "cli-gap-details", "--strict-warnings"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "gaps_closed=1" in proc.stdout
    qc = json.loads((package / "processing/jobs/cli-gap-details/reports/qc.json").read_text())
    assert qc["gaps"][0]["durationNs"] == "2500000000"
    assert qc["trafficLights"][SOURCE] == "warn"
    assert raw_hashes(package) == before
