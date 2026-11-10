# SPDX-License-Identifier: GPL-3.0-only
"""Real MCAP bytes and the native QC report/CLI, not descriptor-only fixtures."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

from capture_analysis import JobParams, run
from capture_analysis.qc import collect_qc
from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
from google.protobuf import descriptor_pb2
from mcap.writer import CompressionType, Writer

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "sensor.force"
STREAM = "loadcell"
SEGMENT = f"sources/{SOURCE}/streams/{STREAM}/segments/000000.mcap"


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _package(tmp_path: Path, *, schema: str = "generic.numeric_batch/1") -> Path:
    root = tmp_path / "record.mmsession"
    _json(
        root / "manifest.json",
        {
            "schemaId": "capture.session_manifest/1",
            "sessionId": "payload-qc-course",
            "state": "finalized",
            "sourceIds": [SOURCE],
        },
    )
    _json(root / "integrity.json", {"files": [{"endSessionTimeNs": 3_000_000_000}]})
    _json(
        root / "sources" / SOURCE / "streams" / STREAM / "stream.json",
        {
            "sourceId": SOURCE,
            "streamId": STREAM,
            "modality": "force",
            "dataSchemaId": schema,
            "units": "N",
            "nominalRateHz": 100,
            "dimensions": [2],
        },
    )
    return root


def _write_mcap(root: Path, *, values: list[float], times: list[int]) -> None:
    target = root / SEGMENT
    target.parent.mkdir(parents=True, exist_ok=True)
    pb = numeric_batch_pb2.NumericBatch(
        channel_count=2,
        channel_names=["left", "right"],
        units="N",
        dtype="f64",
        samples=values,
        device_time_ns=times,
    )
    descriptors = descriptor_pb2.FileDescriptorSet()
    numeric_batch_pb2.DESCRIPTOR.CopyToProto(descriptors.file.add())
    with target.open("wb") as output:
        writer = Writer(output, compression=CompressionType.NONE)
        writer.start(profile="protobuf")
        schema_id = writer.register_schema(
            name="capture.v1.data.NumericBatch",
            encoding="protobuf",
            data=descriptors.SerializeToString(),
        )
        channel_id = writer.register_channel(
            topic=f"{SOURCE}/{STREAM}/generic.numeric_batch/1",
            message_encoding="protobuf",
            schema_id=schema_id,
        )
        writer.add_message(
            channel_id=channel_id,
            log_time=1_000_000_000,
            publish_time=1_000_000_000,
            data=pb.SerializeToString(),
        )
        writer.finish()


def _write_batched_mcap(
    root: Path, *, batches: list[list[int]], segment: str = "000000.mcap",
    untimed_batch_indices: frozenset[int] = frozenset(),
) -> None:
    """Write sealed, CRC-valid protobuf MCAP batches with controlled native clocks."""
    target = root / SEGMENT.replace("000000.mcap", segment)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptors = descriptor_pb2.FileDescriptorSet()
    numeric_batch_pb2.DESCRIPTOR.CopyToProto(descriptors.file.add())
    with target.open("wb") as output:
        writer = Writer(output, compression=CompressionType.NONE)
        writer.start(profile="protobuf")
        schema_id = writer.register_schema(
            name="capture.v1.data.NumericBatch",
            encoding="protobuf",
            data=descriptors.SerializeToString(),
        )
        channel_id = writer.register_channel(
            topic=f"{SOURCE}/{STREAM}/generic.numeric_batch/1",
            message_encoding="protobuf",
            schema_id=schema_id,
        )
        for i, times in enumerate(batches):
            pb = numeric_batch_pb2.NumericBatch(
                channel_count=2,
                channel_names=["left", "right"],
                units="N",
                dtype="f64",
                samples=[
                    float(j) for j in range(2 * (max(len(times), 1)
                    if i in untimed_batch_indices else len(times)))
                ],
                device_time_ns=[] if i in untimed_batch_indices else times,
            )
            writer.add_message(
                channel_id=channel_id,
                log_time=1_000_000_000 + i * 1_000_000,
                publish_time=1_000_000_000 + i * 1_000_000,
                data=pb.SerializeToString(),
            )
        writer.finish()


def test_native_clock_rewind_between_batches_is_not_green(tmp_path: Path) -> None:
    package = _package(tmp_path)
    _write_batched_mcap(package, batches=[[100, 200], [50, 75]])
    report = collect_qc(package, inspect_payloads=True).to_dict()
    observed = report["streams"][0]["payloadInspection"]
    assert observed["status"] == "failed", observed
    assert "backward" in observed["detail"], observed
    assert report["trafficLights"][SOURCE] == "fail"


def test_native_clock_rewind_between_segments_is_not_green(tmp_path: Path) -> None:
    package = _package(tmp_path)
    _write_batched_mcap(package, batches=[[100, 200]])
    _write_batched_mcap(package, batches=[[50, 75]], segment="000001.mcap")
    report = collect_qc(package, inspect_payloads=True).to_dict()
    assert report["streams"][0]["payloadInspection"]["status"] == "failed", report
    assert report["trafficLights"][SOURCE] == "fail"


def test_monotonic_native_clock_across_segments_is_accepted(tmp_path: Path) -> None:
    package = _package(tmp_path)
    _write_batched_mcap(package, batches=[[100, 200]])
    _write_batched_mcap(package, batches=[[201, 300]], segment="000001.mcap")
    report = collect_qc(package, inspect_payloads=True).to_dict()
    assert report["streams"][0]["payloadInspection"]["status"] == "numeric_samples_checked"
    assert report["streams"][0]["payloadInspection"]["sampleFramesChecked"] == 4
    assert report["trafficLights"][SOURCE] == "ok"


def test_missing_native_timestamps_stay_visible_as_unverified(tmp_path: Path) -> None:
    package = _package(tmp_path)
    _write_batched_mcap(
        package, batches=[[100, 200], []], untimed_batch_indices=frozenset({1})
    )
    report = collect_qc(package, inspect_payloads=True).to_dict()
    observed = report["streams"][0]["payloadInspection"]
    assert observed["status"] == "numeric_samples_checked"
    assert observed["sampleFramesChecked"] == 3
    assert observed["framesWithoutNativeTimestamps"] == 1
    assert report["trafficLights"][SOURCE] == "warn"
    assert "clock continuity" in " ".join(report["warnings"])


def test_cli_and_html_show_cross_batch_failure(tmp_path: Path) -> None:
    package = _package(tmp_path)
    _write_batched_mcap(package, batches=[[100, 200], [50, 75]])
    command = [
        sys.executable, str(ROOT / "tools/run_analysis.py"), "qc", str(package),
        "--inspect-payloads", "--strict-warnings", "--overwrite-job-id", "clock-review",
    ]
    response = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert response.returncode == 2, response.stdout + response.stderr
    report_dir = package / "processing/jobs/clock-review/reports"
    qc = json.loads((report_dir / "qc.json").read_text())
    assert qc["trafficLights"][SOURCE] == "fail"
    assert "between batches or segments" in qc["streams"][0]["payloadInspection"]["detail"]
    assert "between batches or segments" in (report_dir / "qc.html").read_text()


def test_opt_in_counts_real_frames_and_preserves_default_scope(tmp_path: Path) -> None:
    package = _package(tmp_path)
    _write_mcap(
        package,
        values=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
        times=[123, 124, 125],
    )

    uninspected = collect_qc(package).to_dict()
    assert uninspected["streams"][0]["payloadInspection"] == {"status": "not_requested"}

    before = (package / SEGMENT).read_bytes()
    params = JobParams(
        command="qc", overwrite_job_id="payload-qc", extra={"inspect_payloads": True}
    )
    output = run(package, params)
    assert output.status == "completed", output.manifest
    qc = json.loads((output.job_dir / "reports/qc.json").read_text())
    inspected = qc["streams"][0]["payloadInspection"]
    assert inspected["status"] == "numeric_samples_checked"
    assert inspected["sampleFramesChecked"] == 3
    assert inspected["messagesChecked"] == 1
    assert inspected["segmentsChecked"] == 1
    assert qc["trafficLights"][SOURCE] == "ok"
    html = (output.job_dir / "reports/qc.html").read_text()
    assert "numeric_samples_checked" in html
    assert "does not establish signal quality" in html
    assert (package / SEGMENT).read_bytes() == before


def test_real_nan_sample_is_a_visible_source_failure(tmp_path: Path) -> None:
    package = _package(tmp_path)
    _write_mcap(package, values=[1.0, math.nan], times=[100])

    report = collect_qc(package, inspect_payloads=True).to_dict()
    observed = report["streams"][0]["payloadInspection"]
    assert observed["status"] == "failed"
    assert observed["sampleFramesChecked"] is None
    assert "NaN or infinity" in observed["detail"]
    assert report["trafficLights"][SOURCE] == "fail"
    assert any("payload inspection failed" in note for note in report["warnings"])


def test_invalid_mcap_bytes_do_not_look_like_verified_signal(tmp_path: Path) -> None:
    package = _package(tmp_path)
    target = package / SEGMENT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"MCAP-placeholder-is-not-data")
    report = collect_qc(package, inspect_payloads=True).to_dict()
    assert report["streams"][0]["payloadInspection"]["status"] == "failed"
    assert report["trafficLights"][SOURCE] == "fail"


def test_unsupported_schema_is_only_message_inspection(tmp_path: Path) -> None:
    package = _package(tmp_path, schema="other.custom/1")
    _write_mcap(package, values=[1.0, 2.0], times=[100])
    report = collect_qc(package, inspect_payloads=True).to_dict()
    inspected = report["streams"][0]["payloadInspection"]
    assert inspected["status"] == "mcap_messages_checked"
    assert inspected["sampleFramesChecked"] is None


def test_native_cli_reports_invalid_stream_via_strict_warnings(tmp_path: Path) -> None:
    package = _package(tmp_path)
    _write_mcap(package, values=[1.0, math.inf], times=[100])
    command = [
        sys.executable,
        str(ROOT / "tools/run_analysis.py"),
        "qc",
        str(package),
        "--inspect-payloads",
        "--strict-warnings",
        "--overwrite-job-id",
        "cli-payload-qc",
    ]
    response = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert response.returncode == 2, response.stdout + response.stderr
    assert "status=completed_with_warnings" in response.stdout
    qc = json.loads((package / "processing/jobs/cli-payload-qc/reports/qc.json").read_text())
    assert qc["trafficLights"][SOURCE] == "fail"
    assert qc["streams"][0]["payloadInspection"]["status"] == "failed"
