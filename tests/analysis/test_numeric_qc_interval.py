import json
import subprocess
import sys
from pathlib import Path

from capture_analysis import collect_qc, hash_sources_tree
from capture_analysis.report_html import render_qc_html
from test_payload_inspection_qc import ROOT, _package, _write_mcap


def test_late_numeric_episode_reachable_through_actual_qc_cli(tmp_path: Path):
    package = _package(tmp_path)
    (package / "integrity.json").write_text(
        json.dumps({"files": [{"endSessionTimeNs": 20_000_000_000}]})
    )
    # Twenty seconds of paired force measurements: a late grip pulse after rest.
    native = [2**59 + i * 10_000_000 for i in range(2000)]
    values = [v for i in range(2000) for v in ([12.5, -4.0] if 600 <= i <= 610 else [0.0, 0.0])]
    _write_mcap(package, values=values, times=native)
    before = hash_sources_tree(package)
    initial = collect_qc(package, inspect_payloads=True).to_dict()["streams"][0][
        "payloadInspection"
    ]["numericPreview"]
    assert all(row == [0.0, 0.0] for row in initial["batches"][0]["values"])
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/run_analysis.py"),
            "qc",
            str(package),
            "--inspect-payloads",
            "--start-ns",
            "7000000000",
            "--end-ns",
            "7100000000",
            "--overwrite-job-id",
            "late-grip",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    reports = package / "processing/jobs/late-grip/reports"
    d = json.loads((reports / "qc.json").read_text())
    inspection = d["streams"][0]["payloadInspection"]
    p = inspection["numericPreview"]
    assert inspection["sampleFramesChecked"] == 2000
    assert p["selection"] == "session_interval" and p["matchingFrames"] == p["framesShown"] == 11
    assert p["batches"][0]["firstFrame"] == 600 and p["batches"][0]["displayFirstFrame"] == 0
    assert p["batches"][0]["values"] == [[12.5, -4.0]] * 11
    assert p["batches"][0]["nativeTimeNs"][0] == str(native[600])
    assert p["batches"][0]["mappedSessionTimeNs"] == [
        str(7_000_000_000 + i * 10_000_000) for i in range(11)
    ]
    html = (reports / "qc.html").read_text()
    assert (
        "Whole-recording QC" in html and "7000000000" in html and "First 11 of 11 matching" in html
    )
    assert hash_sources_tree(package) == before


def test_empty_and_untimed_interval_are_explicit(tmp_path: Path):
    package = _package(tmp_path)
    _write_mcap(package, values=[1, 2, 3, 4], times=[])
    report = collect_qc(package, inspect_payloads=True, preview_window=(0, 2_000_000_000)).to_dict()
    p = report["streams"][0]["payloadInspection"]["numericPreview"]
    assert p["untimedFramesExcluded"] == 2 and p["framesShown"] == 0
    assert "No timed samples to display" in render_qc_html(report)
    _write_mcap(package, values=[1, 2, 3, 4], times=[100, 200])
    report = collect_qc(
        package, inspect_payloads=True, preview_window=(3_000_000_000, 4_000_000_000)
    ).to_dict()
    p = report["streams"][0]["payloadInspection"]["numericPreview"]
    assert p["matchingFrames"] == p["untimedFramesExcluded"] == 0
    assert "No timed samples to display" in render_qc_html(report)


def test_interval_spans_batches_caps_display_and_keeps_full_qc(tmp_path: Path):
    from mcap.writer import CompressionType, Writer
    from test_payload_inspection_qc import SEGMENT

    package = _package(tmp_path)
    target = package / SEGMENT
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as output:
        writer = Writer(output, compression=CompressionType.NONE)
        writer.start()
        schema = writer.register_schema("generic.numeric_batch/1", "jsonschema", b"{}")
        channel = writer.register_channel("force", "json", schema)
        for batch in range(3):
            anchor = 1_000_000_000 + batch * 2_000_000_000
            writer.add_message(
                channel,
                anchor,
                json.dumps(
                    {
                        "channel_count": 2,
                        "channel_names": ["left", "right"],
                        "samples": [v for i in range(200) for v in [batch * 200 + i, -i]],
                        "device_time_ns": [
                            2**59 + (batch * 200 + i) * 10_000_000 for i in range(200)
                        ],
                    }
                ).encode(),
                anchor,
            )
        writer.finish()
    report = collect_qc(
        package, inspect_payloads=True, preview_window=(2_500_000_000, 5_500_000_000)
    ).to_dict()
    inspection = report["streams"][0]["payloadInspection"]
    p = inspection["numericPreview"]
    assert inspection["sampleFramesChecked"] == 600
    assert p["matchingFrames"] == 301 and p["framesShown"] == 256
    assert [b["firstFrame"] for b in p["batches"]] == [150, 200, 400]
    assert [b["displayFirstFrame"] for b in p["batches"]] == [0, 50, 250]
    assert [len(b["values"]) for b in p["batches"]] == [50, 200, 6]
    assert p["batches"][-1]["mappedSessionTimeNs"][-1] == "5050000000"
    html = render_qc_html(report)
    assert html.count('<polyline class="signal"') == 6
    assert "First 256 of 301 matching" in html
