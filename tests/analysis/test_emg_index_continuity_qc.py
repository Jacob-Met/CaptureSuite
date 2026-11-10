# SPDX-License-Identifier: GPL-3.0-only
"""Recorded EMG batch continuity through actual MCAP and the operator QC path."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest
from capture_analysis import collect_qc, hash_sources_tree
from capture_analysis.report_html import render_qc_html
from capture_protocol.generated.capture.v1 import common_pb2
from capture_protocol.generated.capture.v1.data import emg_batch_pb2
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from mcap.writer import Writer

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "emg.lab"
STREAM = "muscles"


def make_package(root: Path, segments: list[list[tuple[int, int]]]) -> Path:
    """Each tuple is (first sample index, frame count); timestamps stay ordered."""
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({
        "schemaId": "capture.session_manifest/1", "sessionId": "emg-continuity",
        "state": "finalized", "sourceIds": [SOURCE],
    }))
    (root / "integrity.json").write_text(json.dumps({"files": []}))
    stream = root / "sources" / SOURCE / "streams" / STREAM
    (stream / "segments").mkdir(parents=True)
    (stream / "stream.json").write_text(json.dumps({
        "sourceId": SOURCE, "streamId": STREAM, "modality": "emg",
        "dataSchemaId": "emg.batch/1", "units": "mV", "nominalRateHz": 1000,
        "dimensions": [1],
    }))
    descriptors = FileDescriptorSet()
    common_pb2.DESCRIPTOR.CopyToProto(descriptors.file.add())
    emg_batch_pb2.DESCRIPTOR.CopyToProto(descriptors.file.add())
    timestamp = 0
    for segment_index, batches in enumerate(segments):
        with (stream / "segments" / f"{segment_index:06}.mcap").open("wb") as fh:
            writer = Writer(fh)
            writer.start(profile="protobuf")
            schema = writer.register_schema(
                name="capture.v1.data.EmgBatch", encoding="protobuf",
                data=descriptors.SerializeToString(),
            )
            channel = writer.register_channel(
                topic=f"{SOURCE}/{STREAM}", message_encoding="protobuf", schema_id=schema,
            )
            for first, count in batches:
                msg = emg_batch_pb2.EmgBatch(
                    first_sample_index=first, sample_count=count, channel_ids=["biceps"],
                    samples_f32_le=struct.pack(f"<{count}f", *range(count)),
                )
                msg.timing.session_time_ns = timestamp
                writer.add_message(
                    channel_id=channel, log_time=timestamp, publish_time=timestamp,
                    data=msg.SerializeToString(),
                )
                timestamp += count * 1_000_000
            writer.finish()
    return root


@pytest.mark.parametrize("segments,jumps,overlaps", [
    ([[(0, 4), (4, 2), (6, 3)]], 0, 0),
    ([[(200, 4)], [(204, 2)]], 0, 0),
    ([[(0, 4), (8, 2)]], 1, 0),
    ([[(0, 4)], [(8, 2)]], 1, 0),
    ([[(0, 4), (3, 2)]], 0, 1),
    ([[(0, 4), (0, 4)]], 0, 1),
    ([[(100, 4)], [(0, 2), (2, 2)]], 0, 1),
    ([[(0, 4), (8, 2), (1, 3)]], 1, 1),
    ([[(123, 4)]], 0, 0),
])
def test_decoded_continuity_surfaces_in_source_light(
    tmp_path: Path, segments: list[list[tuple[int, int]]], jumps: int, overlaps: int,
) -> None:
    package = make_package(tmp_path / "capture.mmsession", segments)
    before = hash_sources_tree(package)
    report = collect_qc(package, inspect_payloads=True).to_dict()
    assert report["trafficLights"][SOURCE] == ("warn" if jumps + overlaps else "ok")
    inspection = report["streams"][0]["payloadInspection"]
    assert inspection["status"] == "emg_samples_checked"
    assert inspection["sampleFramesChecked"] == sum(n for group in segments for _, n in group)
    continuity = inspection["sampleIndexContinuity"]
    assert continuity["batchesChecked"] == sum(map(len, segments))
    assert continuity["transitionsChecked"] == max(0, sum(map(len, segments)) - 1)
    assert continuity["forwardJumpCount"] == jumps
    assert continuity["overlapOrResetCount"] == overlaps
    assert hash_sources_tree(package) == before


def test_large_indices_remain_exact_and_examples_are_bounded(tmp_path: Path) -> None:
    first = (1 << 53) + 17
    package = make_package(
        tmp_path / "long.mmsession", [[(first + i * 8, 4) for i in range(15)]],
    )
    report = collect_qc(package, inspect_payloads=True).to_dict()
    continuity = report["streams"][0]["payloadInspection"]["sampleIndexContinuity"]
    assert continuity["forwardJumpCount"] == 14
    assert len(continuity["examples"]) == 10
    example = continuity["examples"][0]
    assert example["expectedFirstSampleIndex"] == str(first + 4)
    assert example["actualFirstSampleIndex"] == str(first + 8)
    assert example["segment"] == "000000.mcap"
    assert example["messageInSegment"] == 2
    html = render_qc_html(report)
    assert str(first + 4) in html
    assert str(first + 8) in html
    assert "first 10 of 14" in html


def test_strict_cli_warns_and_retains_an_actionable_report(tmp_path: Path) -> None:
    package = make_package(tmp_path / "missing.mmsession", [[(0, 4)], [(8, 2)]])
    before = hash_sources_tree(package)
    result = subprocess.run([
        sys.executable, str(ROOT / "tools/run_analysis.py"), "qc", str(package),
        "--inspect-payloads", "--strict-warnings", "--overwrite-job-id", "continuity-qc",
    ], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 2, result.stdout + result.stderr
    reports = package / "processing/jobs/continuity-qc/reports"
    report = json.loads((reports / "qc.json").read_text())
    assert report["trafficLights"][SOURCE] == "warn"
    html = (reports / "qc.html").read_text()
    assert "EMG sample-index discontinuities" in html
    assert "000001.mcap" in html
    assert "expected 4, observed 8" in html
    assert hash_sources_tree(package) == before


def test_descriptor_only_qc_does_not_claim_index_inspection(tmp_path: Path) -> None:
    package = make_package(tmp_path / "metadata.mmsession", [[(0, 4), (8, 2)]])
    report = collect_qc(package).to_dict()
    assert report["streams"][0]["payloadInspection"] == {"status": "not_requested"}
    assert "sample-index" not in render_qc_html(report)
