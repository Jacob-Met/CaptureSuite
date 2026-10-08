#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Independent saved-package receiver: future edits cannot change a closed section.

Run once per frozen source in a fresh interpreter. This is one metamorphic
receiving method with four real MCAP packages, not a formula/unit-test oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import traceback
from pathlib import Path

NS = 1_000_000_000
SOURCE_ID = "sim.imu.upper"
STREAM_ID = "sim.imu.upper.frames"
WINDOW_REL = "libs/python/capture_analysis/capture_analysis/windows.py"
VARIANTS = ("reference", "future_marker", "future_data", "inside_data")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def json_write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_map(root: Path, *, exclude_processing: bool = False) -> dict:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            if exclude_processing and rel.startswith("processing/"):
                continue
            data = path.read_bytes()
            result[rel] = {"bytes": len(data), "sha256": digest(data)}
    return result


def verify_source(root: Path, manifest: dict) -> None:
    expected = {row["path"]: row for row in manifest["files"]}
    actual = file_map(root)
    if set(actual) != set(expected):
        raise RuntimeError(f"source inventory differs: {set(actual) ^ set(expected)}")
    for rel, row in expected.items():
        data = (root / rel).read_bytes()
        if digest(data) != row["sha256"] or blob(data) != row["git_blob"]:
            raise RuntimeError(f"source bytes differ: {rel}")


def make_package(package: Path, variant: str) -> dict:
    from capture_protocol.generated.capture.v1.data import imu_frame_pb2
    from mcap.writer import Writer

    package.mkdir(parents=True, exist_ok=False)
    json_write(package / "manifest.json", {
        "session_schema_version": "1.0.0",
        "sessionId": "independent-checkpoint-fixture",
        "state": "finalized",
        "t0WallUtc": "2026-10-08T00:00:00Z",
        "finalizedUtc": "2026-10-08T00:00:12Z",
        "sourceIds": [SOURCE_ID],
    })
    checkpoints = []
    for cid, name, seconds in (
        ("A", "Warmup", 2), ("B", "Selected completed phase", 6),
        ("C", "Later phase", 12 if variant == "future_marker" else 9),
    ):
        checkpoints.append({
            "checkpointId": cid, "name": name,
            "originalTimestampNs": str(seconds * NS),
            "effectiveTimestampNs": str(seconds * NS),
        })
    json_write(package / "events/checkpoints.json", checkpoints)
    json_write(package / "events/annotations.json", [])
    json_write(package / "events/sync_anchors.json", [])
    source = package / "sources" / SOURCE_ID
    json_write(source / "source.json", {
        "sourceId": SOURCE_ID, "sourceType": "sim.imu",
        "alias": "Independent synthetic IMU", "pluginId": "sim.imu",
    })
    stream = source / "streams" / STREAM_ID
    json_write(stream / "stream.json", {
        "streamId": STREAM_ID, "sourceId": SOURCE_ID, "modality": "imu",
        "units": "a.u.", "dimensions": [3], "nominalRateHz": 60.0,
        "dataSchemaId": "imu.frame/1", "dataSchemaVersion": "1",
    })
    mcap_path = stream / "segments/000000.mcap"
    mcap_path.parent.mkdir(parents=True, exist_ok=True)
    messages = []
    with mcap_path.open("wb") as handle:
        writer = Writer(handle)
        writer.start(profile="", library="independent-checkpoint-receiver")
        schema_id = writer.register_schema(name="imu.frame/1", encoding="protobuf", data=b"")
        channel_id = writer.register_channel(
            topic="imu", message_encoding="protobuf", schema_id=schema_id,
        )
        for index in range(12 * 60 + 1):
            frame = imu_frame_pb2.ImuFrame()
            frame.timing.session_time_ns = index * NS // 60
            frame.timing.sequence_number = index
            frame.frame_index = index
            sensor = frame.sensors.add()
            sensor.sensor_id = "review_sensor"
            sensor.accel_x = index / 60.0 + 1.0
            sensor.accel_y = 2.0
            sensor.accel_z = 3.0
            sensor.gyro_x = 0.25
            sensor.qw = 1.0
            if variant == "future_data" and index > 6 * 60:
                sensor.accel_x += 1000.0
            if variant == "inside_data" and index == 4 * 60:
                sensor.accel_x += 1000.0
            payload = frame.SerializeToString()
            stamp = frame.timing.session_time_ns
            writer.add_message(
                channel_id=channel_id, log_time=stamp, data=payload, publish_time=stamp,
            )
            messages.append({"index": index, "time_ns": stamp, "sha256": digest(payload)})
        writer.finish()
    raw = mcap_path.read_bytes()
    json_write(package / "integrity.json", {
        "schemaVersion": "1",
        "files": [{
            "path": mcap_path.relative_to(package).as_posix(),
            "sizeBytes": len(raw), "sha256": digest(raw),
            "endSessionTimeNs": 12 * NS,
        }],
    })
    return {"checkpoints": checkpoints, "messages": messages}


def receive(source: Path, output: Path, manifest: dict, receipt: dict) -> None:
    import pandas as pd
    from capture_analysis import JobParams, run
    from capture_session.package_reader import load_review_summary

    tables = {}
    raw = {}
    checks = receipt["checks"]

    def check(name, condition, **details):
        checks.append({"name": name, "passed": bool(condition), **details})

    for variant in VARIANTS:
        package = output / "packages" / (variant + ".mmsession")
        description = make_package(package, variant)
        before = file_map(package, exclude_processing=True)
        summary = load_review_summary(package)
        check(variant + ": persisted reader",
              summary.checkpoints == description["checkpoints"] and summary.duration_ns == 12 * NS)
        result = run(package, JobParams(
            command="features", checkpoint_section="B", overwrite_job_id="section-B",
        ))
        after = file_map(package, exclude_processing=True)
        check(variant + ": raw package unchanged", before == after)
        disk_manifest = json.loads((result.job_dir / "job_manifest.json").read_text())
        csv_path = result.job_dir / f"features/imu/{SOURCE_ID}/windows.csv"
        parquet_path = csv_path.with_suffix(".parquet")
        csv = pd.read_csv(csv_path)
        parquet = pd.read_parquet(parquet_path)
        check(variant + ": completed real features",
              result.status == "completed" and not disk_manifest["warnings"]
              and not disk_manifest["errors"] and not parquet.empty
              and disk_manifest["featureTables"][0]["rows"] == len(parquet),
              status=result.status, rows=len(parquet), warnings=disk_manifest["warnings"])
        try:
            pd.testing.assert_frame_equal(csv, parquet, check_dtype=False, rtol=1e-12, atol=1e-12)
            mirrors_equal = True
        except AssertionError:
            mirrors_equal = False
        check(variant + ": CSV and Parquet agree", mirrors_equal)
        window = disk_manifest["timeRange"]
        times = [int(value) for value in parquet["t_mid_ns"]]
        check(variant + ": selected closed interval",
              window["startSessionNs"] == 2 * NS and window["endSessionNs"] == 6 * NS
              and window["checkpointIds"] == ["B"]
              and all(2 * NS <= stamp <= 6 * NS for stamp in times),
              observed_window=window, first_feature_ns=min(times), last_feature_ns=max(times))
        tables[variant] = {"frame": parquet, "csv": csv_path.read_bytes(), "window": window}
        raw[variant] = description
        receipt["variants"][variant] = {
            "description": description, "raw_before": before, "raw_after": after,
            "job_dir": result.job_dir.relative_to(output).as_posix(),
            "window": window, "feature_rows": len(parquet), "feature_times_ns": times,
            "csv": {"bytes": csv_path.stat().st_size, "sha256": digest(csv_path.read_bytes())},
            "parquet": {"bytes": parquet_path.stat().st_size, "sha256": digest(parquet_path.read_bytes())},
            "warnings": disk_manifest["warnings"], "errors": disk_manifest["errors"],
        }

    ref = tables["reference"]
    check("future-marker input isolation",
          raw["reference"]["messages"] == raw["future_marker"]["messages"]
          and raw["reference"]["checkpoints"][:2] == raw["future_marker"]["checkpoints"][:2])
    changed_future = [
        left["index"] for left, right in zip(raw["reference"]["messages"], raw["future_data"]["messages"])
        if left["sha256"] != right["sha256"]
    ]
    changed_inside = [
        left["index"] for left, right in zip(raw["reference"]["messages"], raw["inside_data"]["messages"])
        if left["sha256"] != right["sha256"]
    ]
    check("future-data input isolation", changed_future == list(range(361, 721)))
    check("inside-data input isolation", changed_inside == [240])
    for variant in ("future_marker", "future_data"):
        other = tables[variant]
        check(variant + ": completed-section output invariant",
              ref["window"] == other["window"] and ref["frame"].equals(other["frame"])
              and ref["csv"] == other["csv"])
    inside = tables["inside_data"]
    check("inside-data sensitivity control",
          ref["window"] == inside["window"]
          and list(ref["frame"]["t_mid_ns"]) == list(inside["frame"]["t_mid_ns"])
          and not ref["frame"].equals(inside["frame"]) and ref["csv"] != inside["csv"])
    verify_source(source, manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.manifest.read_text())
    receipt = {
        "label": args.label, "method": "saved-package closed-section future isolation",
        "argv": sys.argv, "python": sys.version, "executable": sys.executable,
        "platform": platform.platform(), "source_root": str(source),
        "source_manifest_sha256": digest(args.manifest.read_bytes()),
        "driver_sha256": digest(Path(__file__).read_bytes()), "variants": {}, "checks": [],
        "scope": "Actual persisted JSON/protobuf MCAP -> public capture_analysis.run -> native CSV/Parquet. Synthetic offline data; no daemon, UI, hardware capture, or scientific validity claim.",
    }
    try:
        verify_source(source, manifest)
        for package in ("capture_analysis", "capture_session", "capture_protocol"):
            sys.path.insert(0, str(source / "libs/python" / package))
        receive(source, output, manifest, receipt)
        receipt["source_files_verified_before_and_after"] = len(manifest["files"])
        receipt["result"] = "passed" if all(row["passed"] for row in receipt["checks"]) else "failed"
        exit_code = 0 if receipt["result"] == "passed" else 1
    except Exception:
        receipt["result"] = "infrastructure_error"
        receipt["exception"] = traceback.format_exc()
        exit_code = 2
    receipt["application_modules"] = []
    for name, module in sorted(sys.modules.items()):
        if name.split(".")[0] in {"capture_analysis", "capture_session", "capture_protocol"}:
            filename = getattr(module, "__file__", None)
            if filename:
                path = Path(filename).resolve()
                try:
                    rel = path.relative_to(source).as_posix()
                    data = path.read_bytes()
                    receipt["application_modules"].append({
                        "module": name, "path": rel, "sha256": digest(data), "git_blob": blob(data),
                    })
                except ValueError:
                    receipt["result"] = "infrastructure_error"
                    receipt["unexpected_module"] = str(path)
                    exit_code = 2
    receipt["dependency_versions"] = {
        name: importlib.metadata.version(name)
        for name in ("numpy", "pandas", "scipy", "mcap", "protobuf", "pyarrow", "matplotlib", "jsonschema")
    }
    json_write(output / "receiving-receipt.json", receipt)
    passed = sum(row["passed"] for row in receipt["checks"])
    print(json.dumps({
        "label": args.label, "result": receipt["result"], "checks_passed": passed,
        "checks_total": len(receipt["checks"]), "application_modules": len(receipt["application_modules"]),
        "failures": [row["name"] for row in receipt["checks"] if not row["passed"]],
        "exception": receipt.get("exception"), "receipt": str(output / "receiving-receipt.json"),
    }, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
