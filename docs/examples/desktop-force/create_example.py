#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Create a synthetic saved-session example with the maintained analysis engine."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
for module in ("capture_protocol", "capture_session", "capture_analysis"):
    sys.path.insert(0, str(ROOT / "libs" / "python" / module))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def build(output: Path) -> dict:
    from mcap.writer import Writer
    from google.protobuf.descriptor_pb2 import FileDescriptorSet
    from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
    from capture_analysis import JobParams, run

    output = output.resolve()
    output.mkdir(parents=False, exist_ok=False)
    package = output / "synthetic-force.mmsession"
    stream = package / "sources" / "example.force" / "streams" / "force.samples"
    (stream / "segments").mkdir(parents=True)
    write_json(package / "manifest.json", {
        "session_schema_version": "1.0.0", "sessionId": "example.synthetic-force",
        "state": "finalized", "t0WallUtc": "2026-11-10T00:00:00Z",
        "finalizedUtc": "2026-11-10T00:00:06Z", "sourceIds": ["example.force"],
        "synthetic": True,
    })
    write_json(stream / "stream.json", {
        "sourceId": "example.force", "streamId": "force.samples",
        "modality": "numeric", "dataSchemaId": "generic.numeric_batch/1",
        "nominalRateHz": 10.0, "units": "N", "dimensions": [2],
        "synthetic": True,
    })
    descriptor = FileDescriptorSet()
    numeric_batch_pb2.DESCRIPTOR.CopyToProto(descriptor.file.add())
    values = [value for i in range(60) for value in (12.5 + i * 0.25, 25.0)]
    record = numeric_batch_pb2.NumericBatch(
        channel_count=2, channel_names=["ramp", "reference"], units="N",
        dtype="float64", samples=values,
        device_time_ns=[2_000_000_000 + i * 100_000_000 for i in range(60)],
    )
    segment = stream / "segments" / "000000.mcap"
    with segment.open("wb") as handle:
        writer = Writer(handle)
        writer.start(profile="protobuf", library="capturesuite-synthetic-desktop-example")
        schema = writer.register_schema(
            name="capture.v1.data.NumericBatch", encoding="protobuf",
            data=descriptor.SerializeToString(),
        )
        channel = writer.register_channel(
            topic="example.force/numeric/generic.numeric_batch/1",
            message_encoding="protobuf", schema_id=schema,
            metadata={"data_schema_id": "generic.numeric_batch/1"},
        )
        writer.add_message(channel_id=channel, log_time=0, publish_time=0,
                           data=record.SerializeToString())
        writer.finish()
    raw_hash = hashlib.sha256(segment.read_bytes()).hexdigest()
    write_json(package / "integrity.json", {"schemaVersion": "1", "files": [{
        "path": segment.relative_to(package).as_posix(),
        "sizeBytes": segment.stat().st_size, "sha256": raw_hash,
        "startSessionTimeNs": 0, "endSessionTimeNs": 6_000_000_000,
        "expectedCount": 60, "actualCount": 60, "status": "sealed",
    }]})
    jobs = []
    for params in (
        JobParams(command="all", overwrite_job_id="full-result"),
        JobParams(command="features", overwrite_job_id="late-window",
                  start_session_ns=3_000_000_000, end_session_ns=6_000_000_000),
    ):
        result = run(package, params)
        if result.status not in ("completed", "completed_with_warnings"):
            raise RuntimeError(f"Example analysis failed: {result.status}")
        jobs.append({"id": result.job_id, "status": result.status})
    if hashlib.sha256(segment.read_bytes()).hexdigest() != raw_hash:
        raise RuntimeError("Analysis changed the synthetic raw recording")
    source = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    receipt = {
        "classification": "synthetic_software_walkthrough",
        "analysisSourceCommit": source,
        "generatorSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rawMcapSha256": raw_hash,
        "sampleCountPerChannel": 60, "nominalRateHz": 10,
        "channels": {"ramp": "12.5 + 0.25 * i, i=0..59",
                     "reference": "25.0 for all 60 samples"},
        "units": "N (illustrative, uncalibrated)", "jobs": jobs,
        "limitations": "Synthetic NumericBatch MCAP, not daemon capture, device calibration, physical force, or clinical validation. No patient or personal data.",
    }
    write_json(output / "EXAMPLE.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory under an existing parent")
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))


if __name__ == "__main__":
    main()
