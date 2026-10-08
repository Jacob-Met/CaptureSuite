# SPDX-License-Identifier: GPL-3.0-only
"""Independent receiving through real NumericBatch protobuf, MCAP and analysis APIs.

PYTHONPATH selects the reviewed source; no loader, decoder, handler or writer is
mocked. The same file is replayed unchanged on baseline and candidate source.
"""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from capture_analysis.discover import discover_streams
from capture_analysis.features.numeric_batch import extract_numeric_batch_features
from capture_analysis.jobs import JobParams, hash_sources_tree, run
from capture_analysis.loaders.base import RamBudgetExceeded
from capture_analysis.loaders.numeric_batch import load_numeric_batch
from capture_analysis.types import GapMask, LoadedEmg, TimeWindow
from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
from capture_session.package_reader import load_review_summary
from google.protobuf import descriptor_pb2
from mcap.writer import CompressionType, Writer

SOURCE_ID = "sim.numeric.force"
STREAM_ID = "force_signals"
SCHEMA_ID = "generic.numeric_batch/1"
NATIVE_SCHEMA_NAME = "capture.v1.data.NumericBatch"
MIB = 1024 * 1024


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def descriptor_bytes() -> bytes:
    descriptor = descriptor_pb2.FileDescriptorSet()
    numeric_batch_pb2.DESCRIPTOR.CopyToProto(descriptor.file.add())
    return descriptor.SerializeToString()


def write_segment(
    path: Path,
    *,
    log_time: int,
    device_times: list[int],
    samples: list[float],
    channel_count: int = 2,
    channel_names: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    message = numeric_batch_pb2.NumericBatch(
        channel_count=channel_count,
        channel_names=channel_names or ["force_x", "force_y"],
        units="N",
        dtype="f64",
        samples=samples,
        device_time_ns=device_times,
    )
    with path.open("wb") as output:
        writer = Writer(output, compression=CompressionType.NONE)
        writer.start(profile="protobuf")
        schema_id = writer.register_schema(
            name=NATIVE_SCHEMA_NAME,
            encoding="protobuf",
            data=descriptor_bytes(),
        )
        channel_id = writer.register_channel(
            topic=f"{SOURCE_ID}/{STREAM_ID}/{SCHEMA_ID}",
            message_encoding="protobuf",
            schema_id=schema_id,
            metadata={
                "data_schema_id": SCHEMA_ID,
                "source_id": SOURCE_ID,
                "stream_id": STREAM_ID,
            },
        )
        writer.add_message(
            channel_id=channel_id,
            log_time=log_time,
            publish_time=log_time + 10**15,
            data=message.SerializeToString(),
        )
        writer.finish()


class NumericReceiving(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="numeric-receiving-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "native.mmsession"
        self.stream_dir = self.root / "sources" / SOURCE_ID / "streams" / STREAM_ID

    def package(
        self,
        *,
        duration: int | None = 7_000_000_000,
        rate: float | None = 10.0,
        dimensions: list[int] | None = None,
    ) -> None:
        write_json(
            self.root / "manifest.json",
            {
                "schemaId": "capture.session_manifest/1",
                "sessionId": "independent-numeric-receiving",
                "state": "finalized",
                "sourceIds": [SOURCE_ID],
            },
        )
        # Deliberately exercise a modality collision: the serialization schema
        # is NumericBatch even when an adapter labels its modality as EMG.
        stream = {
            "sourceId": SOURCE_ID,
            "streamId": STREAM_ID,
            "modality": "emg",
            "dataSchemaId": SCHEMA_ID,
            "units": "N",
            "dimensions": dimensions or [2],
        }
        if rate is not None:
            stream["nominalRateHz"] = rate
        write_json(self.stream_dir / "stream.json", stream)
        write_json(
            self.root / "events" / "checkpoints.json",
            [
                {"checkpointId": "trial", "effectiveTimestampNs": 5_080_000_000},
                {"checkpointId": "rest", "effectiveTimestampNs": 6_600_000_000},
            ],
        )
        entries = [] if duration is None else [{"endSessionTimeNs": duration}]
        write_json(self.root / "integrity.json", {"files": entries})

    def two_segments(self, **package_kwargs: object) -> None:
        self.package(**package_kwargs)
        # File order opposes time order. Each segment's device clock has its
        # own unrelated epoch, so only MCAP first-datum anchoring aligns them.
        write_segment(
            self.stream_dir / "segments" / "000000.mcap",
            log_time=6_000_000_000,
            device_times=[
                9_000_000_000 + offset
                for offset in [0, 100_000_000, 250_000_000, 450_000_000, 600_000_000, 800_000_000]
            ],
            samples=[v for x in [70, 80, 90, 100, 110, 120] for v in [x, 10 * x]],
        )
        write_segment(
            self.stream_dir / "segments" / "000001.mcap",
            log_time=5_000_000_000,
            device_times=[
                1_000_000_000_000 + offset
                for offset in [0, 80_000_000, 210_000_000, 310_000_000, 450_000_000, 550_000_000]
            ],
            samples=[v for x in [10, 20, 30, 40, 50, 60] for v in [x, 10 * x]],
        )

    def stream(self):
        refs = discover_streams(self.root)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].data_schema_id, SCHEMA_ID)
        return refs[0]

    def assert_feature_table(self, result):
        self.assertEqual(result.manifest["errors"], [])
        tables = result.manifest["featureTables"]
        self.assertEqual(len(tables), 1, result.manifest)
        relative = tables[0]["relativePath"]
        self.assertTrue(relative.startswith("features/numeric/"), relative)
        path = result.job_dir / relative
        self.assertTrue(path.is_file())
        frame = pd.read_parquet(path)
        self.assertEqual(tables[0]["rows"], len(frame))
        artifact = next(x for x in result.manifest["outputs"] if x["relativePath"] == relative)
        self.assertEqual(artifact["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(artifact["bytes"], path.stat().st_size)
        return frame, relative

    def test_native_mcap_segments_are_anchored_sorted_and_clipped_together(self) -> None:
        self.two_segments()
        raw_before = hash_sources_tree(self.root)
        loaded = load_numeric_batch(
            self.stream(),
            TimeWindow(5_080_000_000, 6_600_000_000),
            max_ram_bytes=8 * MIB,
        )
        np.testing.assert_array_equal(
            loaded.t_sample_ns,
            [
                5_080_000_000,
                5_210_000_000,
                5_310_000_000,
                5_450_000_000,
                5_550_000_000,
                6_000_000_000,
                6_100_000_000,
                6_250_000_000,
                6_450_000_000,
                6_600_000_000,
            ],
        )
        expected = np.arange(20, 111, 10, dtype=np.float64)
        np.testing.assert_array_equal(loaded.X, np.vstack([expected, 10 * expected]))
        self.assertEqual(loaded.channel_ids, ["force_x", "force_y"])
        self.assertEqual(loaded.fs_hz, 10)
        self.assertEqual(loaded.units, "N")
        self.assertFalse(any(flag & 8 for flag in loaded.batch_quality_flags))
        self.assertEqual(hash_sources_tree(self.root), raw_before)

    def test_public_checkpoint_job_exports_exact_native_bounds_math_and_metadata(self) -> None:
        self.two_segments()
        raw_before = hash_sources_tree(self.root)
        result = run(
            self.root,
            # The rest checkpoint closes the preceding 5.08s to 6.6s section.
            JobParams(command="features", checkpoint_section="rest", max_ram_bytes=8 * MIB),
        )
        frame, relative = self.assert_feature_table(result)
        self.assertEqual(len(frame), 1)
        row = frame.iloc[0]
        self.assertEqual(int(row["t_start_ns"]), 5_080_000_000)
        self.assertEqual(int(row["t_end_ns"]), 6_700_000_000)
        self.assertAlmostEqual(row["force_x_mean"], 65.0)
        self.assertAlmostEqual(row["force_x_rms"], math.sqrt(5050.0))
        self.assertAlmostEqual(row["force_y_mean"], 650.0)
        self.assertAlmostEqual(row["force_y_rms"], 10 * math.sqrt(5050.0))
        self.assertEqual(row["gap_fraction"], 0.0)
        self.assertEqual(row["rate_hz"], 10.0)
        metadata = json.loads((result.job_dir / "features" / "_schema.json").read_text())
        columns = {item["name"]: item for item in metadata["tables"][relative]["columns"]}
        self.assertEqual(set(columns), set(frame.columns))
        for name in ["force_x_mean", "force_x_rms", "force_y_mean", "force_y_rms"]:
            self.assertEqual(columns[name]["units"], "N")
            self.assertEqual(columns[name]["id"], "numeric.basic.v1")
            self.assertIs(columns[name]["provisional"], True)
            self.assertIs(columns[name]["calibrated"], False)
            self.assertIs(columns[name]["interpolatedTimestamps"], False)
        self.assertEqual(hash_sources_tree(self.root), raw_before)

    def test_durationless_public_job_admits_small_native_recording(self) -> None:
        self.two_segments(duration=None)
        self.assertEqual(load_review_summary(self.root).duration_ns, 0)
        raw_before = hash_sources_tree(self.root)
        result = run(self.root, JobParams(command="features", max_ram_bytes=8 * MIB))
        frame, _relative = self.assert_feature_table(result)
        self.assertEqual(len(frame), 1)
        self.assertEqual(int(frame.iloc[0]["t_start_ns"]), 5_000_000_000)
        self.assertEqual(int(frame.iloc[0]["t_end_ns"]), 6_550_000_000)
        self.assertAlmostEqual(frame.iloc[0]["force_x_mean"], 55.0)
        self.assertTrue(any("duration" in warning for warning in result.manifest["warnings"]))
        self.assertFalse(any("max-ram-bytes" in w for w in result.manifest["warnings"]))
        self.assertEqual(hash_sources_tree(self.root), raw_before)

    def test_durationless_public_job_reports_small_budget_refusal(self) -> None:
        self.two_segments(duration=None)
        raw_before = hash_sources_tree(self.root)
        result = run(self.root, JobParams(command="features", max_ram_bytes=512))
        self.assertEqual(result.manifest["featureTables"], [])
        warnings = result.manifest["warnings"]
        self.assertTrue(
            any(f"{SOURCE_ID}/{STREAM_ID}" in w and "max-ram-bytes" in w for w in warnings)
        )
        self.assertEqual(result.status, "completed_with_warnings")
        self.assertEqual(hash_sources_tree(self.root), raw_before)

    def test_missing_rate_refuses_to_invent_timebase(self) -> None:
        self.two_segments(rate=None)
        with self.assertRaisesRegex(ValueError, "missing nominal_rate_hz"):
            load_numeric_batch(self.stream(), TimeWindow(0, 7_000_000_000), max_ram_bytes=8 * MIB)

    def test_actual_payload_budget_is_not_hidden_by_small_descriptor(self) -> None:
        self.package(rate=1, dimensions=[1])
        write_segment(
            self.stream_dir / "segments" / "000000.mcap",
            log_time=5_000_000_000,
            device_times=list(range(1024)),
            samples=[1.0] * (256 * 1024),
            channel_count=256,
            channel_names=[f"ch{i}" for i in range(256)],
        )
        raw_before = hash_sources_tree(self.root)
        with self.assertRaisesRegex(RamBudgetExceeded, f"{SOURCE_ID}/{STREAM_ID}"):
            load_numeric_batch(
                self.stream(),
                TimeWindow(5_000_000_000, 5_000_001_024),
                max_ram_bytes=2 * MIB,
            )
        self.assertEqual(hash_sources_tree(self.root), raw_before)

    def test_partial_frame_payload_is_rejected(self) -> None:
        self.package()
        write_segment(
            self.stream_dir / "segments" / "000000.mcap",
            log_time=5_000_000_000,
            device_times=[100],
            samples=[1.0, 2.0, 3.0],
        )
        with self.assertRaisesRegex(ValueError, "sample|frame|channel"):
            load_numeric_batch(self.stream(), TimeWindow(0, 7_000_000_000), max_ram_bytes=8 * MIB)

    def test_partial_device_timestamps_are_rejected(self) -> None:
        self.package()
        write_segment(
            self.stream_dir / "segments" / "000000.mcap",
            log_time=5_000_000_000,
            device_times=[100],
            samples=[1.0, 2.0, 3.0, 4.0],
        )
        with self.assertRaisesRegex(ValueError, "timestamp|device_time"):
            load_numeric_batch(self.stream(), TimeWindow(0, 7_000_000_000), max_ram_bytes=8 * MIB)

    def test_finite_large_values_keep_finite_mean_and_rms(self) -> None:
        self.package(rate=2, dimensions=[1])
        loaded = LoadedEmg(
            channel_ids=["force"],
            t_sample_ns=np.asarray([0, 500_000_000], dtype=np.int64),
            X=np.asarray([[1e308, 1e308]], dtype=np.float64),
            fs_hz=2,
            units="N",
        )
        gap_mask = GapMask(self.stream(), TimeWindow(0, 1_000_000_000))
        frame, _metadata, fraction = extract_numeric_batch_features(loaded, gap_mask)
        self.assertEqual(len(frame), 1)
        self.assertEqual(fraction, 1.0)
        self.assertTrue(np.isfinite(frame[["force_mean", "force_rms"]].to_numpy()).all())
        self.assertEqual(frame.iloc[0]["force_mean"], 1e308)
        self.assertEqual(frame.iloc[0]["force_rms"], 1e308)


if __name__ == "__main__":
    import capture_analysis

    print(f"Reviewed package: {Path(capture_analysis.__file__).resolve()}", flush=True)
    print("Fixture: real self-describing protobuf MCAP; native writer schema name", flush=True)
    unittest.main(verbosity=2)
