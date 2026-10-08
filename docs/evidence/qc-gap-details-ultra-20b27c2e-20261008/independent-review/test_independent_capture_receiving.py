# SPDX-License-Identifier: GPL-3.0-only
"""Independent receiving probes for attributable offline QC gap details."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
CHECKOUT = Path(os.environ.get("CAPTURE_REVIEW_CHECKOUT", ROOT / "candidate")).resolve()
sys.path[:0] = [str(CHECKOUT / "libs/python" / name) for name in (
    "capture_analysis", "capture_session", "capture_protocol"
)]

from capture_analysis import collect_qc  # noqa: E402
from capture_analysis.report_html import render_qc_html  # noqa: E402

A = "sim.emg.main"
AS = "sim.emg.main.batch"
B = "sim.imu.upper"
BS = "sim.imu.upper.frames"
C = "review.healthy.third"
CS = "review.healthy.third.batch"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_hashes(package: Path) -> dict[str, str]:
    return {
        p.relative_to(package).as_posix(): digest(p)
        for p in sorted(package.rglob("*"))
        if p.is_file() and p.relative_to(package).parts[0] != "processing"
    }


@pytest.fixture
def package(tmp_path: Path) -> Path:
    target = tmp_path / "independent.mmsession"
    shutil.copytree(CHECKOUT / "tests/fixtures/mini_session", target)
    return target


def gap(source: str = A, stream: str = AS, **changes) -> dict:
    value = {
        "sourceId": source,
        "streamId": stream,
        "cause": "VENDOR_FUTURE_CAUSE",
        "startSessionTimeNs": "3",
        "endSessionTimeNs": "7",
        "closed": True,
        "estimatedLostCount": "9007199254740993",
    }
    value.update(changes)
    return value


def write_gaps(package: Path, source_folder: str, rows: list[dict]) -> None:
    path = package / "sources" / source_folder / "health/gaps.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def multiple_sources(package: Path) -> list[dict]:
    """One failed + one healthy sibling, a gapped source, and a healthy source."""
    source_a = package / "sources" / A
    third = package / "sources" / C
    shutil.copytree(source_a, third)
    metadata = json.loads((third / "source.json").read_text())
    metadata["sourceId"] = C
    (third / "source.json").write_text(json.dumps(metadata), encoding="utf-8")
    third_stream = third / "streams" / AS
    metadata = json.loads((third_stream / "stream.json").read_text())
    metadata.update(sourceId=C, streamId=CS)
    (third_stream / "stream.json").write_text(json.dumps(metadata), encoding="utf-8")
    third_stream.rename(third / "streams" / CS)

    sibling = source_a / "streams/review.healthy.sibling"
    shutil.copytree(source_a / "streams" / AS, sibling)
    metadata = json.loads((sibling / "stream.json").read_text())
    metadata.update(sourceId=A, streamId="review.healthy.sibling")
    (sibling / "stream.json").write_text(json.dumps(metadata), encoding="utf-8")
    for path in (source_a / "streams" / AS / "segments").iterdir():
        if path.is_file():
            path.unlink()
    records = [
        gap(A, AS, cause="GAP_CAUSE_WRITER_ERROR"),
        gap(B, BS, cause="VENDOR_FUTURE_FAILURE<unclassified>&", estimatedLostCount="0"),
    ]
    write_gaps(package, A, [records[0]])
    write_gaps(package, B, [records[1]])
    return records


class HtmlEvidence(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        self.tags.append(tag)
        if tag == "tr":
            self.row = []
        if tag == "td":
            self.cell = []

    def handle_data(self, data) -> None:
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag) -> None:
        if tag == "td" and self.cell is not None and self.row is not None:
            self.row.append("".join(self.cell))
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def html_evidence(qc: dict) -> HtmlEvidence:
    parsed = HtmlEvidence()
    parsed.feed(render_qc_html(qc))
    return parsed


def invoke_cli(package: Path, name: str, strict: bool) -> tuple[subprocess.CompletedProcess, dict, str, dict]:
    before = raw_hashes(package)
    command = [sys.executable, str(CHECKOUT / "tools/run_analysis.py"), "qc", str(package),
               "--overwrite-job-id", name]
    if strict:
        command.append("--strict-warnings")
    result = subprocess.run(command, cwd=CHECKOUT, capture_output=True, text=True, timeout=30)
    job = package / "processing/jobs" / name
    qc_path = job / "reports/qc.json"
    html_path = job / "reports/qc.html"
    qc = json.loads(qc_path.read_text()) if qc_path.exists() else None
    html = html_path.read_text() if html_path.exists() else ""
    manifest = json.loads((job / "job_manifest.json").read_text()) if job.exists() else None
    after = raw_hashes(package)
    receipt = {
        "checkout": str(CHECKOUT), "command": command, "returncode": result.returncode,
        "stdout": result.stdout, "stderr": result.stderr, "raw_before": before,
        "raw_after": after, "raw_unchanged": before == after, "qc": qc,
        "html_sha256": digest(html_path) if html_path.exists() else None,
        "job_manifest": manifest,
    }
    evidence = ROOT / "evidence" / CHECKOUT.name
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / (name + ".json")).write_text(json.dumps(receipt, indent=2) + "\n")
    if html_path.exists():
        (evidence / (name + ".html")).write_bytes(html_path.read_bytes())
    assert result.returncode in (0, 2), result.stdout + result.stderr
    assert before == after, "The actual QC command changed package inputs"
    assert qc is not None and manifest is not None, result.stdout + result.stderr
    for relative in ("reports/qc.json", "reports/qc.html"):
        output = next(row for row in manifest["outputs"] if row["relativePath"] == relative)
        path = job / relative
        assert output["sha256"] == digest(path)
        assert int(output["bytes"]) == path.stat().st_size
    return result, qc, html, manifest


def test_source_and_stream_association_with_failure_dominance(package: Path) -> None:
    records = multiple_sources(package)
    before = raw_hashes(package)
    report = collect_qc(package).to_dict()
    assert (report["sourceCount"], report["streamCount"]) == (3, 4)
    assert report["trafficLights"] == {A: "fail", B: "warn", C: "ok"}
    assert len(report["gaps"]) == report["closedGapCount"] == 2
    assert report["openGapCount"] == 0
    assert [(row["sourceId"], row["streamId"], row["cause"]) for row in report["gaps"]] == [
        (row["sourceId"], row["streamId"], row["cause"]) for row in records
    ]
    assert [row["estimatedLostCount"] for row in report["gaps"]] == ["9007199254740993", "0"]
    assert len([w for w in report["warnings"] if "recorded gap(s)" in w]) == 2
    parsed = html_evidence(report)
    gap_rows = [row for row in parsed.rows if len(row) == 8]
    assert [(row[0], row[1], row[2]) for row in gap_rows] == [
        (row["sourceId"], row["streamId"], row["cause"]) for row in records
    ]
    assert "unclassified" not in parsed.tags
    assert raw_hashes(package) == before


def test_extreme_intervals_and_unknown_bounds_remain_distinct(package: Path) -> None:
    records = [
        gap(cause="FULL_SIGNED_RANGE", startSessionTimeNs=str(-(2**63)),
            endSessionTimeNs=str(2**63 - 1)),
        gap(cause="OPEN_REVERSED", startSessionTimeNs="10", endSessionTimeNs="2", closed=False),
        gap(cause="CLOSED_NO_END", endSessionTimeNs=None),
        {"cause": "NATIVE_START_ONLY", "start_session_time_ns": 0, "stream_id": ""},
    ]
    write_gaps(package, A, records)
    before = raw_hashes(package)
    qc = collect_qc(package).to_dict()
    assert (qc["openGapCount"], qc["closedGapCount"]) == (2, 2)
    assert [row["durationStatus"] for row in qc["gaps"]] == [
        "known", "end_before_start", "missing_end", "open"
    ]
    assert [row["durationNs"] for row in qc["gaps"]] == [str(2**64 - 1), None, None, None]
    rows = {row[2]: row for row in html_evidence(qc).rows if len(row) == 8}
    assert rows["FULL_SIGNED_RANGE"][4:7] == [
        "-9223372036.854775808", "9223372036.854775807", "18446744073.709551615"
    ]
    assert rows["OPEN_REVERSED"][3] == "open"
    assert rows["OPEN_REVERSED"][6] == "unknown (end precedes start)"
    assert rows["CLOSED_NO_END"][5:7] == ["unknown", "unknown (end not recorded)"]
    assert rows["NATIVE_START_ONLY"][0:2] == [A, "(source-wide)"]
    assert rows["NATIVE_START_ONLY"][4:8] == [
        "0.000000000", "unknown", "unknown (open gap)", "0"
    ]
    assert raw_hashes(package) == before


def test_gap_snapshot_is_detached_from_receivers_and_later_disk_changes(package: Path) -> None:
    write_gaps(package, A, [gap(cause="ORIGINAL_CAPTURE")])
    snapshot = collect_qc(package)
    original = snapshot.to_dict()
    receiver = snapshot.to_dict()
    receiver["gaps"][0]["cause"] = "RECEIVER_MUTATION"
    receiver["gaps"].append({"cause": "INJECTED"})
    receiver["trafficLights"][A] = "ok"
    receiver["warnings"].clear()
    assert snapshot.to_dict() == original
    before = raw_hashes(package)
    render_qc_html(snapshot.to_dict())
    assert raw_hashes(package) == before
    write_gaps(package, A, [gap(cause="LATER_CAPTURE", endSessionTimeNs="11")])
    changed = raw_hashes(package)
    differences = {name for name in before if before[name] != changed[name]}
    assert differences == {f"sources/{A}/health/gaps.jsonl"}
    assert snapshot.to_dict() == original
    assert collect_qc(package).to_dict()["gaps"][0]["cause"] == "LATER_CAPTURE"
    assert raw_hashes(package) == changed


def test_unavailable_legacy_details_are_not_reported_as_an_empty_capture(package: Path) -> None:
    report = collect_qc(package).to_dict()
    for unavailable in (None, "absent"):
        old = dict(report)
        old["schemaId"] = "capture.analysis_qc/1"
        old["closedGapCount"] = 3
        if unavailable == "absent":
            old.pop("gaps", None)
        else:
            old["gaps"] = None
        text = "".join(html_evidence(old).text)
        assert "Gap details are not available in this report." in text
        assert "No gap records listed." not in text
        assert "gaps open/closed 0/3" in text
    text = "".join(html_evidence(report).text)
    assert "No gap records listed." in text
    assert "Gap details are not available" not in text


def test_native_html_preserves_untrusted_recorded_text_without_markup(package: Path) -> None:
    recorded = gap(source='vendor<&"source', stream='stream</td><script>run()</script>',
                   cause='<img src="x" onerror="run()"> & next')
    write_gaps(package, A, [recorded])
    qc = collect_qc(package).to_dict()
    parsed = html_evidence(qc)
    assert not {"script", "img", "source"}.intersection(parsed.tags)
    row = next(row for row in parsed.rows if len(row) == 8)
    assert row[:3] == [recorded["sourceId"], recorded["streamId"], recorded["cause"]]
    assert qc["gaps"][0]["cause"] == recorded["cause"]
    assert qc["trafficLights"][recorded["sourceId"]] == "warn"
    assert qc["trafficLights"][A] == "ok"


def test_actual_cli_renders_gap_and_binds_unchanged_raw_inputs(package: Path) -> None:
    record = gap(cause='FUTURE<&"cause', startSessionTimeNs="9223372036854775806",
                 endSessionTimeNs="9223372036854775807")
    write_gaps(package, A, [record])
    result, qc, html, manifest = invoke_cli(package, "independent-gap", strict=True)
    assert result.returncode == 2, result.stdout
    assert "status=completed_with_warnings" in result.stdout
    assert "gaps_open=0 gaps_closed=1" in result.stdout
    assert qc["trafficLights"] == {A: "warn", B: "ok"}
    assert qc["gaps"] == [record | {"durationNs": "1", "durationStatus": "known"}]
    parsed = HtmlEvidence()
    parsed.feed(html)
    row = next(row for row in parsed.rows if len(row) == 8)
    assert row[:3] == [A, AS, record["cause"]]
    assert row[4:8] == ["9223372036.854775806", "9223372036.854775807", "0.000000001", "9007199254740993"]
    assert all("jsonschema" not in str(w) for w in manifest.get("warnings", []))


def test_actual_cli_no_gap_positive_control(package: Path) -> None:
    qc_before = collect_qc(package).to_dict()
    assert qc_before["warnings"] == []
    assert set(qc_before["trafficLights"].values()) == {"ok"}
    result, qc, _html, manifest = invoke_cli(package, "independent-no-gap", strict=False)
    assert result.returncode == 0
    assert "status=completed\n" in result.stdout
    assert "gaps_open=0 gaps_closed=0" in result.stdout
    assert qc["warnings"] == []
    assert set(qc["trafficLights"].values()) == {"ok"}
    assert qc["openGapCount"] == qc["closedGapCount"] == 0
    assert all("jsonschema" not in str(w) for w in manifest.get("warnings", []))
