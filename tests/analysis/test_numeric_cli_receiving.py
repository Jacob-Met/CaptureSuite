# SPDX-License-Identifier: GPL-3.0-only
"""Independent receiving of CaptureSuite's actual numeric CLI workflow.

The fixture contains synthetic values in real protobuf MCAP segments. No job,
handler, loader, feature writer, plotter, or subprocess result is replaced.
Numerical estimator/timebase/RAM qualification belongs to the other receiver.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from mcap.writer import Writer

SOURCE = Path(os.environ.get("CAPTURE_CLI_SOURCE", Path(__file__).resolve().parents[2])).resolve()
VARIANT = os.environ.get("CAPTURE_CLI_VARIANT", "native")
RECEIPT_ROOT = os.environ.get("CAPTURE_CLI_RECEIPT_DIR")
RUN_DIR = Path(RECEIPT_ROOT).resolve() / VARIANT if RECEIPT_ROOT else None
if RUN_DIR is not None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
COMMAND = [sys.executable, str(SOURCE / "tools" / "run_analysis.py")]
RECORDS: list[dict] = []
VALIDATOR_AVAILABLE = importlib.util.find_spec("jsonschema") is not None
ALLOW_MISSING_VALIDATOR = os.environ.get("CAPTURE_CLI_ALLOW_MISSING_VALIDATOR") == "1"
VALIDATOR_WARNING = "manifest schema validation: No module named 'jsonschema'"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retained_files(package: Path) -> dict[str, str]:
    return {
        p.relative_to(package).as_posix(): sha256(p)
        for p in sorted(package.rglob("*"))
        if p.is_file() and p.relative_to(package).parts[0] != "processing"
    }


def source_files() -> dict[str, str]:
    return {
        p.relative_to(SOURCE).as_posix(): sha256(p)
        for p in sorted(SOURCE.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_package(path: Path, *, malformed: bool = False, case_twins: bool = False) -> Path:
    """Two streams of one source and a third independently selectable source."""
    path.mkdir(parents=True)
    write_json(
        path / "manifest.json",
        {
            "session_schema_version": "1.0.0",
            "sessionId": "independent-numeric-cli",
            "state": "finalized",
            "t0WallUtc": "2026-10-08T00:00:00Z",
            "finalizedUtc": "2026-10-08T00:00:04Z",
            "sourceIds": ["sampler.a", "sampler.b"],
        },
    )
    write_json(path / "events" / "checkpoints.json", [])
    write_json(path / "events" / "annotations.json", [])
    write_json(path / "events" / "sync_anchors.json", [])
    integrity = []
    descriptors = [
        ("sampler.a", "voltage", "numeric", "V", 1.0),
        ("sampler.a", "force", "emg", "a.u.", 3.0),
        ("sampler.b", "temperature", "eeg", "degC", 7.0),
    ]
    for source_id, stream_id, modality, units, offset in descriptors:
        stream_folder = stream_id
        if case_twins:
            stream_id = {"voltage": "A", "force": "a"}.get(stream_id, stream_id)
            stream_folder = {"voltage": "first", "force": "second"}.get(
                stream_folder, stream_folder
            )
        source = path / "sources" / source_id
        write_json(source / "source.json", {"sourceId": source_id})
        health = source / "health" / "gaps.jsonl"
        health.parent.mkdir(parents=True, exist_ok=True)
        health.write_text("", encoding="utf-8")
        stream = source / "streams" / stream_folder
        write_json(
            stream / "stream.json",
            {
                "sourceId": source_id,
                "streamId": stream_id,
                "modality": modality,
                "streamClass": "STREAM_CLASS_SAMPLED",
                "dataSchemaId": "generic.numeric_batch/1",
                "dataSchemaVersion": "1",
                "timestampSource": "TIMESTAMP_SOURCE_SESSION_MAPPED",
                "nominalRateHz": 20.0,
                "units": units,
                "dimensions": [1],
            },
        )
        msg = numeric_batch_pb2.NumericBatch(
            channel_count=1,
            units=units,
            dtype="f64",
            channel_names=["input 1"],
            samples=[offset + (i % 10) / 10.0 for i in range(60)],
            device_time_ns=[9_000_000_000 + i * 50_000_000 for i in range(60)],
        )
        if malformed and stream_folder == "voltage":
            msg.channel_count = 2
            del msg.samples[:]
            msg.samples.extend([1.0, 2.0, 3.0])
            del msg.device_time_ns[:]
        segment = stream / "segments" / "000000.mcap"
        segment.parent.mkdir(parents=True, exist_ok=True)
        with segment.open("wb") as fh:
            writer = Writer(fh)
            writer.start(profile="protobuf", library="independent-cli-receiver")
            descriptor = FileDescriptorSet()
            descriptor.file.add().ParseFromString(numeric_batch_pb2.DESCRIPTOR.serialized_pb)
            schema_id = writer.register_schema(
                name="capture.v1.data.NumericBatch",
                encoding="protobuf",
                data=descriptor.SerializeToString(),
            )
            channel_id = writer.register_channel(
                topic=f"{source_id}/{stream_id}",
                message_encoding="protobuf",
                schema_id=schema_id,
            )
            writer.add_message(
                channel_id=channel_id,
                log_time=1_000_000_000,
                publish_time=1_000_000_000,
                sequence=1,
                data=msg.SerializeToString(),
            )
            writer.finish()
        integrity.append(
            {
                "path": segment.relative_to(path).as_posix(),
                "sizeBytes": str(segment.stat().st_size),
                "sha256": sha256(segment),
                "sourceId": source_id,
                "streamId": stream_id,
                "startSessionTimeNs": "1000000000",
                "endSessionTimeNs": "4000000000",
                "status": "INTEGRITY_STATUS_SEALED",
            }
        )
    write_json(path / "integrity.json", {"schemaVersion": "1", "files": integrity})
    if case_twins:
        gap = {
            "sourceId": "sampler.a",
            "streamId": "A",
            "cause": "DISCONNECT",
            "startSessionTimeNs": 1_500_000_000,
            "endSessionTimeNs": 1_950_000_000,
            "closed": True,
        }
        (path / "sources" / "sampler.a" / "health" / "gaps.jsonl").write_text(
            json.dumps(gap) + "\n", encoding="utf-8"
        )
    return path


class HtmlInventory(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.links: list[str] = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in ("href", "src") and value is not None:
                self.links.append(value)


class NumericCliReceiving(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(
            VALIDATOR_AVAILABLE or ALLOW_MISSING_VALIDATOR,
            "jsonschema is required for native clean-success acceptance",
        )
        self.assertTrue((SOURCE / "schemas/session/jsonschema/analysis_job.schema.json").is_file())
        self.assertTrue(
            (SOURCE / "docs/design/research/schemas/analysis_plugin_manifest.schema.json").is_file()
        )
        if RUN_DIR is None:
            temporary = tempfile.TemporaryDirectory(prefix="capturesuite-numeric-cli-")
            self.addCleanup(temporary.cleanup)
            self.case_dir = Path(temporary.name)
        else:
            self.case_dir = RUN_DIR / self._testMethodName
            self.case_dir.mkdir()

    def assert_healthy(self, proc, manifest: dict, *, strict: bool = True) -> None:
        expected_warnings = [] if VALIDATOR_AVAILABLE else [VALIDATOR_WARNING]
        self.assertEqual(manifest["warnings"], expected_warnings)
        expected_status = "completed_with_warnings" if expected_warnings else "completed"
        self.assertEqual(manifest["status"], expected_status)
        self.assertEqual(proc.returncode, 2 if strict and expected_warnings else 0,
                         proc.stdout + proc.stderr)
        self.assertIn(f"status={expected_status}\n", proc.stdout)

    def tables_by_identity(self, job: Path, manifest: dict) -> dict:
        schema_path = job / "features" / "_schema.json"
        self.assertTrue(schema_path.is_file(), "numeric feature schema must be created")
        tables = json.loads(schema_path.read_text())["tables"]
        self.assertEqual(set(tables), {row["relativePath"] for row in manifest["featureTables"]})
        indexed = {}
        for relative, descriptor in tables.items():
            identity = (descriptor["sourceId"], descriptor["streamId"])
            self.assertNotIn(identity, indexed)
            parts = Path(relative).parts
            self.assertEqual(parts[:2], ("features", "numeric"))
            self.assertEqual(len(parts), 5)
            self.assertTrue(parts[2].startswith("source-"))
            self.assertTrue(parts[3].startswith("stream-"))
            self.assertEqual(bytes.fromhex(parts[2][7:]).decode("utf-8"), identity[0])
            self.assertEqual(bytes.fromhex(parts[3][7:]).decode("utf-8"), identity[1])
            indexed[identity] = (relative, descriptor)
        return indexed

    def invoke(self, package: Path, command: str, job_id: str, *args: str):
        before = retained_files(package)
        argv = COMMAND + [command, str(package), "--overwrite-job-id", job_id, *args]
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["MPLCONFIGDIR"] = str(self.case_dir / "matplotlib-cache")
        generated = SOURCE / "libs/python/capture_protocol/capture_protocol/generated"
        env["PYTHONPATH"] = os.pathsep.join([str(generated), env.get("PYTHONPATH", "")])
        proc = subprocess.run(
            argv, cwd=SOURCE, env=env, text=True, capture_output=True, check=False, timeout=90
        )
        after = retained_files(package)
        job = package / "processing" / "jobs" / job_id
        manifest_path = job / "job_manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
        record = {
            "case": self._testMethodName,
            "argv": argv,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "raw_before": before,
            "raw_after": after,
            "raw_preserved": before == after,
            "job_dir": str(job),
            "manifest_status": (manifest or {}).get("status"),
            "manifest_warnings": (manifest or {}).get("warnings"),
        }
        RECORDS.append(record)
        write_json(self.case_dir / f"{job_id}-process.json", record)
        self.assertEqual(before, after, "raw and package metadata must remain byte-identical")
        self.assertNotIn("FAIL:", proc.stderr)
        return proc, job, manifest

    def assert_artifacts(self, job: Path, manifest: dict) -> None:
        rows = manifest["outputs"]
        paths = [row["relativePath"] for row in rows]
        self.assertEqual(
            len(paths), len(set(paths)), "output entries must not overwrite each other"
        )
        self.assertEqual(len(paths), len({path.casefold() for path in paths}),
                         "artifact identities must also be distinct on Windows")
        self.assertEqual(manifest["errors"], [])
        for row in rows:
            path = (job / row["relativePath"]).resolve()
            self.assertTrue(path.is_relative_to(job.resolve()))
            self.assertTrue(path.is_file(), row["relativePath"])
            # Existing jobs.py records a preliminary self-digest before rewriting
            # its own manifest. Its pre-existing self-entry is observed separately.
            if row["kind"] == "manifest":
                continue
            self.assertEqual(path.stat().st_size, row["bytes"], row["relativePath"])
            self.assertEqual(sha256(path), row["sha256"], row["relativePath"])
            if row["kind"] == "figure":
                data = path.read_bytes()
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                width, height = struct.unpack(">II", data[16:24])
                self.assertGreaterEqual(width, 500)
                self.assertGreaterEqual(height, 200)
        log = (job / "logs" / "job.log").read_text()
        self.assertIn(f"job_id={manifest['jobId']}", log)
        self.assertIn(f"status={manifest['status']}", log)
        self.assertIn(f"feature_tables={len(manifest['featureTables'])}", log)
        self.assertEqual(manifest["paramsDigest"], hashlib.sha256(
            json.dumps(json.loads((job / "params.json").read_text()), sort_keys=True,
                       separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest())

    def test_all_creates_distinct_numeric_tables_and_figures(self) -> None:
        package = make_package(self.case_dir / "session.mmsession")
        proc, job, manifest = self.invoke(package, "all", "cli-all", "--strict-warnings")
        self.assert_healthy(proc, manifest)
        self.assertIn("job_id=cli-all", proc.stdout)
        self.assert_artifacts(job, manifest)
        expected_identities = {
            ("sampler.a", "voltage"), ("sampler.a", "force"), ("sampler.b", "temperature")
        }
        tables = self.tables_by_identity(job, manifest)
        self.assertEqual(set(tables), expected_identities)
        expected = {relative for relative, _descriptor in tables.values()}
        figures = {x["relativePath"] for x in manifest["outputs"] if x["kind"] == "figure"}
        expected_figures = {
            "figures/numeric/" + "/".join(Path(relative).parts[2:4]) + "/channel_0.png"
            for relative in expected
        }
        self.assertEqual(figures, expected_figures | {"figures/sync_dashboard.png"})
        self.assertEqual(len({sha256(job / rel) for rel in expected}), 3)
        series = json.loads((job / "figures" / "sync_dashboard_series.json").read_text())
        self.assertEqual({x["label"] for x in series["series"]}, {
            "Numeric sampler.a/voltage · input 1",
            "Numeric sampler.a/force · input 1",
            "Numeric sampler.b/temperature · input 1",
        })
        self.assertEqual(
            set(json.loads((job / "features" / "_schema.json").read_text())["tables"]), expected
        )

    def test_features_source_selection_keeps_sibling_outputs_independent(self) -> None:
        package = make_package(self.case_dir / "session.mmsession")
        proc, job, manifest = self.invoke(
            package, "features", "cli-selected", "--strict-warnings", "--sources", "sampler.a"
        )
        self.assert_healthy(proc, manifest)
        self.assertEqual(manifest["sourcesSelected"], ["sampler.a"])
        tables = self.tables_by_identity(job, manifest)
        self.assertEqual(set(tables), {("sampler.a", "voltage"), ("sampler.a", "force")})
        self.assertFalse((job / "figures").exists())
        self.assert_artifacts(job, manifest)

    def test_plots_command_produces_real_numeric_figures_and_series(self) -> None:
        package = make_package(self.case_dir / "session.mmsession")
        proc, job, manifest = self.invoke(
            package, "plots", "cli-plots", "--strict-warnings", "--sources", "sampler.b"
        )
        self.assert_healthy(proc, manifest)
        self.assert_artifacts(job, manifest)
        figures = [x for x in manifest["outputs"] if x["kind"] == "figure"]
        self.assertEqual(len(figures), 2)
        self.assertEqual(len(manifest["featureTables"]), 1)
        self.assertEqual(
            set(self.tables_by_identity(job, manifest)), {("sampler.b", "temperature")}
        )

    def test_refused_stream_is_reported_and_strict_warnings_changes_exit(self) -> None:
        package = make_package(self.case_dir / "session.mmsession", malformed=True)
        ordinary, ordinary_job, ordinary_manifest = self.invoke(package, "features", "cli-warning")
        strict, strict_job, strict_manifest = self.invoke(
            package, "features", "cli-strict", "--strict-warnings"
        )
        self.assertEqual(ordinary.returncode, 0, ordinary.stdout + ordinary.stderr)
        self.assertEqual(strict.returncode, 2, strict.stdout + strict.stderr)
        for job, manifest in [(ordinary_job, ordinary_manifest), (strict_job, strict_manifest)]:
            self.assertEqual(manifest["status"], "completed_with_warnings")
            expected_count = 1 if VALIDATOR_AVAILABLE else 2
            self.assertEqual(len(manifest["warnings"]), expected_count)
            self.assertIn("sampler.a/voltage", manifest["warnings"][0])
            self.assertIn("whole frames", manifest["warnings"][0])
            if not VALIDATOR_AVAILABLE:
                self.assertEqual(manifest["warnings"][1], VALIDATOR_WARNING)
            self.assertEqual(len(manifest["featureTables"]), 2)
            self.assertEqual(set(self.tables_by_identity(job, manifest)), {
                ("sampler.a", "force"), ("sampler.b", "temperature")
            })
            self.assert_artifacts(job, manifest)

    def test_qc_html_inventory_and_manifest_are_available_without_features(self) -> None:
        package = make_package(self.case_dir / "session.mmsession")
        proc, job, manifest = self.invoke(package, "qc", "cli-qc", "--strict-warnings")
        self.assert_healthy(proc, manifest)
        self.assert_artifacts(job, manifest)
        self.assertEqual(manifest["featureTables"], [])
        html = HtmlInventory()
        html.feed((job / "reports" / "qc.html").read_text())
        content = " ".join(html.text)
        for value in ["Analysis QC", "independent-numeric-cli", "sampler.a", "sampler.b",
                      "voltage", "force", "temperature", "generic.numeric_batch/1"]:
            self.assertIn(value, content)
        # This is the current QC page's inventory contract. Figures are reached
        # through manifest output paths; this page does not claim figure links.
        self.assertEqual(html.links, [])
        self.assertEqual(len(json.loads((job / "reports" / "qc.json").read_text())["streams"]), 3)
        entry = next(x for x in manifest["outputs"] if x["kind"] == "manifest")
        RECORDS[-1]["existing_manifest_self_digest_matches"] = (
            entry["sha256"] == sha256(job / "job_manifest.json")
        )
        RECORDS[-1]["existing_log_listed_in_persisted_manifest"] = any(
            x["relativePath"] == "logs/job.log" for x in manifest["outputs"]
        )

    def test_case_only_stream_ids_keep_distinct_paths_and_gap_provenance(self) -> None:
        package = make_package(self.case_dir / "session.mmsession", case_twins=True)
        proc, job, manifest = self.invoke(package, "all", "cli-case-twins", "--strict-warnings")
        self.assert_healthy(proc, manifest)
        self.assert_artifacts(job, manifest)
        tables = self.tables_by_identity(job, manifest)
        self.assertEqual(set(tables), {
            ("sampler.a", "A"), ("sampler.a", "a"), ("sampler.b", "temperature")
        })
        affected_path, affected = tables[("sampler.a", "A")]
        healthy_path, healthy = tables[("sampler.a", "a")]
        self.assertNotEqual(affected_path.casefold(), healthy_path.casefold())
        self.assertNotEqual(sha256(job / affected_path), sha256(job / healthy_path))
        self.assertGreater(affected["validFraction"], 0.0)
        self.assertLess(affected["validFraction"], 1.0)
        self.assertEqual(healthy["validFraction"], 1.0)
        self.assertEqual(tables[("sampler.b", "temperature")][1]["validFraction"], 1.0)

    def test_missing_package_is_a_hard_cli_failure_without_a_job(self) -> None:
        missing = self.case_dir / "does-not-exist.mmsession"
        argv = COMMAND + ["all", str(missing)]
        proc = subprocess.run(
            argv, cwd=SOURCE, env=os.environ.copy(), text=True, capture_output=True,
            check=False, timeout=90
        )
        RECORDS.append({"case": self._testMethodName, "argv": argv,
                        "exit_code": proc.returncode, "stdout": proc.stdout,
                        "stderr": proc.stderr, "job_created": missing.exists()})
        self.assertEqual(proc.returncode, 1)
        self.assertIn("FAIL: package not found:", proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    before_source = source_files() if RUN_DIR is not None else {}
    started = datetime.now(UTC).isoformat()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NumericCliReceiving)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after_source = source_files() if RUN_DIR is not None else {}
    receipt = {
        "receiver": "estate-e82707f2bc62/runtime_discovery",
        "variant": VARIANT,
        "source_root": str(SOURCE),
        "test_sha256": sha256(Path(__file__)),
        "started_utc": started,
        "finished_utc": datetime.now(UTC).isoformat(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "source_sha256": before_source,
        "source_unchanged_during_receiving": before_source == after_source,
        "schema_validator_available": VALIDATOR_AVAILABLE,
        "explicit_local_missing_validator_boundary": ALLOW_MISSING_VALIDATOR,
        "clean_strict_success_qualified": VALIDATOR_AVAILABLE and result.wasSuccessful(),
        "processes": RECORDS,
        "scope": "Actual CLI subprocesses on synthetic protobuf MCAP; workflow artifacts and exits."
    }
    if RUN_DIR is not None:
        write_json(RUN_DIR / "receiving-receipt.json", receipt)
    sys.exit(0 if result.wasSuccessful() and before_source == after_source else 1)
