# SPDX-License-Identifier: GPL-3.0-only
"""One actual current-main numeric/checkpoint CLI pair; no numeric test-suite replay."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, UTC

ROOT = Path(__file__).resolve().parent
OWNER = ROOT.parent
REPOSITORY = OWNER / "repository"
PIN = "0ed1ccaa023a5327495565d59e1dd0b28b2ee5bd"
TREE = "b8990a709744eab58b25b875596c79d0865cce4a"
WINDOW_PATH = "libs/python/capture_analysis/capture_analysis/windows.py"
WINDOW_SHA = "5cf401b7b7d201225c966b804cfff39c3f6d59669da7e488dd68c4253a829c32"
WINDOW_BLOB = "aaafd8db78f82a5a56178135dbed5bfd4f45c634"
SECOND = 1_000_000_000
STEP = 100_000_000
SOURCE_ID, STREAM_ID = "sampler.section", "emg.evidence"
SUMMARY = {"source_commit": PIN, "source_tree": TREE,
           "purpose": "current numeric schema-first CLI receiving of the frozen closing-checkpoint resolver",
           "started_utc": datetime.now(UTC).isoformat(), "runs": []}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def git(*args, cwd=REPOSITORY):
    return subprocess.run(["/usr/bin/git", "-C", str(cwd), *args],
                          check=True, capture_output=True).stdout

def inventory(source, originals, variant):
    rows = []
    for row in originals:
        data = (source / row["path"]).read_bytes()
        actual = git_blob(data)
        expected = WINDOW_BLOB if variant == "candidate" and row["path"] == WINDOW_PATH else row["git_blob"]
        if actual != expected:
            raise AssertionError(f"Source changed: {variant} {row['path']} {actual} != {expected}")
        rows.append({**row, "executed_git_blob": actual, "bytes": len(data), "sha256": digest(data)})
    return rows

def raw_files(package):
    return {p.relative_to(package).as_posix(): {"bytes": p.stat().st_size, "sha256": digest(p.read_bytes())}
            for p in sorted(package.rglob("*")) if p.is_file() and
            p.relative_to(package).parts[0] != "processing"}

def make_package(path):
    from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
    from google.protobuf.descriptor_pb2 import FileDescriptorSet
    from mcap.writer import Writer

    path.mkdir()
    write_json(path / "manifest.json", {
        "session_schema_version": "1.0.0", "sessionId": "numeric-closed-section",
        "state": "finalized", "t0WallUtc": "2026-10-08T00:00:00Z",
        "finalizedUtc": "2026-10-08T00:00:08Z", "sourceIds": [SOURCE_ID]})
    # Persisted order is intentionally unsorted. The selected marker closes [2 s, 5 s].
    checkpoints = [
        {"checkpointId": "finish", "name": "Finish", "originalTimestampNs": str(7 * SECOND)},
        {"checkpointId": "trial", "name": "Trial closed", "originalTimestampNs": str(5 * SECOND)},
        {"checkpointId": "warmup", "name": "Warmup", "originalTimestampNs": str(2 * SECOND)},
    ]
    write_json(path / "events/checkpoints.json", checkpoints)
    write_json(path / "events/annotations.json", [])
    write_json(path / "events/sync_anchors.json", [])
    source = path / "sources" / SOURCE_ID
    write_json(source / "source.json", {"sourceId": SOURCE_ID})
    (source / "health").mkdir()
    (source / "health/gaps.jsonl").write_text("", encoding="utf-8")
    stream = source / "streams" / STREAM_ID
    write_json(stream / "stream.json", {
        "sourceId": SOURCE_ID, "streamId": STREAM_ID, "modality": "emg",
        "streamClass": "STREAM_CLASS_SAMPLED", "dataSchemaId": "generic.numeric_batch/1",
        "dataSchemaVersion": "1", "timestampSource": "TIMESTAMP_SOURCE_SESSION_MAPPED",
        "nominalRateHz": 10.0, "units": "a.u.", "dimensions": [1]})
    segment = stream / "segments/000000.mcap"
    segment.parent.mkdir()
    with segment.open("wb") as handle:
        writer = Writer(handle)
        writer.start(profile="protobuf", library="checkpoint-numeric-composition")
        descriptor = FileDescriptorSet()
        descriptor.file.add().ParseFromString(numeric_batch_pb2.DESCRIPTOR.serialized_pb)
        schema_id = writer.register_schema(name="capture.v1.data.NumericBatch",
                    encoding="protobuf", data=descriptor.SerializeToString())
        channel_id = writer.register_channel(topic=f"{SOURCE_ID}/{STREAM_ID}",
                    message_encoding="protobuf", schema_id=schema_id)
        for first, stop, device_origin in [(0, 40, 9 * SECOND), (40, 81, 17 * SECOND)]:
            msg = numeric_batch_pb2.NumericBatch(
                channel_count=1, units="a.u.", dtype="f64", channel_names=["index"],
                samples=[float(i) for i in range(first, stop)],
                device_time_ns=[device_origin + (i - first) * STEP for i in range(first, stop)])
            writer.add_message(channel_id=channel_id, log_time=first * STEP,
                publish_time=first * STEP, sequence=first,
                data=msg.SerializeToString())
        writer.finish()
    write_json(path / "integrity.json", {"schemaVersion": "1", "files": [{
        "path": segment.relative_to(path).as_posix(), "sizeBytes": str(segment.stat().st_size),
        "sha256": digest(segment.read_bytes()), "sourceId": SOURCE_ID, "streamId": STREAM_ID,
        "startSessionTimeNs": "0", "endSessionTimeNs": str(8 * SECOND),
        "status": "INTEGRITY_STATUS_SEALED"}]})
    return checkpoints

def run():
    assert git("rev-parse", f"{PIN}^{{tree}}").decode().strip() == TREE
    originals = []
    for line in git("ls-tree", "-rz", PIN).split(b"\0"):
        if not line:
            continue
        meta, name = line.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        assert kind == "blob" and mode in ("100644", "100755")
        originals.append({"path": name.decode(), "mode": mode, "git_blob": blob})
    assert len(originals) == 812
    overlay = (ROOT / "frozen-windows.py").read_bytes()
    assert digest(overlay) == WINDOW_SHA and git_blob(overlay) == WINDOW_BLOB
    intake = {"source_commit": PIN, "source_tree": TREE, "files": len(originals),
              "normalizations": [], "overlay": {"path": WINDOW_PATH, "sha256": WINDOW_SHA, "git_blob": WINDOW_BLOB}}
    sources = {}
    for variant in ("baseline", "candidate"):
        source = ROOT / f"{variant}-source"
        assert not source.exists(), f"refuse reusing mutable {source}"
        git("worktree", "add", "--quiet", "--detach", str(source), PIN)
        # Materialize exact canonical Git blobs in these receiving-only copies.
        # Git attributes may change checkout line endings; never alter other content.
        for row in originals:
            path = source / row["path"]
            raw = path.read_bytes()
            if git_blob(raw) != row["git_blob"]:
                canonical = git("cat-file", "blob", row["git_blob"])
                assert raw.replace(b"\r\n", b"\n") == canonical.replace(b"\r\n", b"\n")
                intake["normalizations"].append({"variant": variant, "path": row["path"],
                    "checkout_sha256": digest(raw), "canonical_sha256": digest(canonical)})
                path.write_bytes(canonical)
        if variant == "candidate":
            (source / WINDOW_PATH).write_bytes(overlay)
        sources[variant] = source
        write_json(ROOT / f"{variant}-source-before.json", inventory(source, originals, variant))
    write_json(ROOT / "source-intake.json", intake)
    sys.path[:0] = [str(sources["baseline"] / "libs/python" / name)
                    for name in ("capture_analysis", "capture_session", "capture_protocol")]
    import pandas as pd

    seed = ROOT / "raw-fixture.mmsession"
    checkpoints = make_package(seed)
    fixture_original = raw_files(seed)
    write_json(ROOT / "fixture-definition.json", {
        "checkpoints": checkpoints, "selected_checkpoint": "trial",
        "descriptive_modality": "emg", "wire_schema": "generic.numeric_batch/1",
        "mcap_schema": "capture.v1.data.NumericBatch", "nominal_rate_hz": 10,
        "frames": 81, "frame_values": "index i at session timestamp i * 100000000 ns",
        "batches": [{"indices": [0, 39], "log_time": 0, "native_origin": 9 * SECOND},
                    {"indices": [40, 80], "log_time": 4 * SECOND, "native_origin": 17 * SECOND}],
        "expected_closed_window": [2 * SECOND, 5 * SECOND],
        "original_following_window": [5 * SECOND, 7 * SECOND],
        "raw_files": fixture_original})
    for variant in ("baseline", "candidate"):
        case = ROOT / variant
        case.mkdir()
        source = sources[variant]
        package = case / "numeric.mmsession"
        shutil.copytree(seed, package)
        before = raw_files(package)
        assert before == fixture_original
        job_id = "numeric-checkpoint"
        argv = [sys.executable, str(source / "tools/run_analysis.py"), "all", str(package),
                "--checkpoint-section", "trial", "--sources", SOURCE_ID,
                "--strict-warnings", "--overwrite-job-id", job_id]
        env = os.environ.copy()
        env.update({"PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg",
                    "MPLCONFIGDIR": str(case / "matplotlib-cache"),
                    "CAPTURE_NUMERIC_MODULE_RECEIPT": str(case / "imported-source.json"),
                    "CAPTURE_NUMERIC_SOURCE": str(source),
                    "PYTHONPATH": os.pathsep.join([str(ROOT / "observer"),
                        str(source / "libs/python/capture_protocol/capture_protocol/generated")])})
        started = datetime.now(UTC).isoformat()
        t0 = time.monotonic()
        proc = subprocess.run(argv, cwd=source, env=env, capture_output=True, timeout=90)
        (case / "stdout.txt").write_bytes(proc.stdout)
        (case / "stderr.txt").write_bytes(proc.stderr)
        after = raw_files(package)
        job = package / "processing/jobs" / job_id
        manifest = json.loads((job / "job_manifest.json").read_text())
        schema = json.loads((job / "features/_schema.json").read_text())
        sync = json.loads((job / "figures/sync_dashboard_series.json").read_text())
        table_path, table_meta = next(iter(schema["tables"].items()))
        parquet = pd.read_parquet(job / table_path)
        csv = pd.read_csv((job / table_path).with_suffix(".csv"))
        series = sync["series"][0]
        modules = json.loads((case / "imported-source.json").read_text())
        row_data = parquet.to_dict("records")
        outputs = [{"path": p.relative_to(job).as_posix(), "bytes": p.stat().st_size,
                    "sha256": digest(p.read_bytes())} for p in sorted(job.rglob("*")) if p.is_file()]
        checks = []
        def check(name, ok, actual=None):
            checks.append({"name": name, "passed": bool(ok), "actual": actual})
        check("actual CLI strict success with real schema validation",
              proc.returncode == 0 and manifest["status"] == "completed" and not manifest["warnings"],
              {"exit": proc.returncode, "status": manifest["status"], "warnings": manifest["warnings"]})
        check("raw fixture and persisted checkpoints unchanged", before == after == fixture_original)
        check("generic schema dispatch selected numeric despite emg modality",
              table_path.startswith("features/numeric/") and
              any(x["module"] == "capture_analysis.plugins.numeric" for x in modules), table_path)
        check("exact selected source and stream metadata retained",
              (table_meta.get("sourceId"), table_meta.get("streamId")) == (SOURCE_ID, STREAM_ID))
        check("Parquet and CSV describe the same actual feature rows",
              parquet.shape == csv.shape and parquet.columns.tolist() == csv.columns.tolist()
              and all((parquet[c].to_numpy() == csv[c].to_numpy()).all()
                      if c in ("t_start_ns", "t_end_ns", "rate_hz", "gap_fraction")
                      else __import__("numpy").allclose(parquet[c], csv[c], rtol=1e-14, atol=0)
                      for c in parquet.columns))
        bounds = [sync["window"]["startSessionNs"], sync["window"]["endSessionNs"]]
        check("selected trial closes its preceding interval", bounds == [2 * SECOND, 5 * SECOND], bounds)
        check("all retained numeric timestamps are precisely the inclusive selected section",
              series["t_ns"] == [i * STEP for i in range(20, 51)], series["t_ns"])
        check("retained numeric values come from that closed section across both native batches",
              series["y"] == [float(i) for i in range(20, 51)], series["y"])
        check("only complete feature windows from the closed section are exported",
              parquet["t_start_ns"].tolist() == [i * STEP for i in (20, 25, 30, 35, 40)] and
              parquet["t_end_ns"].tolist() == [i * STEP for i in (30, 35, 40, 45, 50)], row_data)
        check("closed-section window means match original selected samples",
              __import__("numpy").allclose(parquet["index_mean"].to_numpy(),
                    [24.5, 29.5, 34.5, 39.5, 44.5], rtol=1e-14, atol=0)
              if len(parquet) == 5 else False, parquet["index_mean"].tolist())
        check("reported artifact sizes and hashes bind actual outputs",
              all((job / x["relativePath"]).stat().st_size == x["bytes"] and
                  digest((job / x["relativePath"]).read_bytes()) == x["sha256"]
                  for x in manifest["outputs"]))
        check("numeric and sync PNGs were emitted", len(list((job / "figures").rglob("*.png"))) == 2)
        source_after = inventory(source, originals, variant)
        write_json(ROOT / f"{variant}-source-after.json", source_after)
        check("all 812 executed source blobs unchanged",
              source_after == json.loads((ROOT / f"{variant}-source-before.json").read_text()))
        record = {"variant": variant, "started_utc": started, "seconds": time.monotonic() - t0,
                  "argv": argv, "exit_code": proc.returncode, "window": bounds,
                  "manifest_selection": manifest.get("window"), "feature_rows": row_data,
                  "retained_series": series, "source_modules": len(modules),
                  "raw_before": before, "raw_after": after, "outputs": outputs,
                  "checks": checks, "passed": sum(x["passed"] for x in checks),
                  "failed": sum(not x["passed"] for x in checks)}
        write_json(case / "receipt.json", record)
        SUMMARY["runs"].append(record)
        write_json(ROOT / "summary.json", SUMMARY)
        print(json.dumps({"variant": variant, "exit": proc.returncode, "window": bounds,
                          "rows": len(parquet), "samples": len(series["t_ns"]),
                          "passed": record["passed"], "failed": record["failed"]}), flush=True)
    SUMMARY["completed_utc"] = datetime.now(UTC).isoformat()
    SUMMARY["accepted"] = (SUMMARY["runs"][0]["failed"] == 5 and
                           SUMMARY["runs"][1]["failed"] == 0 and
                           SUMMARY["runs"][0]["passed"] == 8)
    write_json(ROOT / "summary.json", SUMMARY)
    if not SUMMARY["accepted"]:
        raise AssertionError("Receiving matrix did not match the declared baseline/candidate boundary")

if __name__ == "__main__":
    try:
        run()
    except BaseException as exc:
        SUMMARY["harness_error"] = {"type": type(exc).__name__, "message": str(exc),
                                    "traceback": traceback.format_exc()}
        write_json(ROOT / "summary.json", SUMMARY)
        raise
