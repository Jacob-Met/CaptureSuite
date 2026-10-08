# SPDX-License-Identifier: GPL-3.0-only
"""Numeric analysis receiving through real MCAP, protobuf and public APIs."""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from capture_analysis import hash_sources_tree
from capture_analysis.features.numeric_batch import extract_numeric_batch_features
from capture_analysis.loaders.base import RamBudgetExceeded
from capture_analysis.loaders.numeric_batch import load_numeric_batch
from capture_analysis.pipeline import run_features_and_plots
from capture_analysis.plugins.registry import get_registry
from capture_analysis.types import GapInterval, GapMask, LoadedEmg, StreamRef, TimeWindow
from capture_analysis.windows import full_window
from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
from capture_session.package_reader import load_review_summary
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from mcap.writer import Writer


def _batch(**overrides) -> dict:
    record = {
        "channel_count": 2,
        "channel_names": ["left", "right"],
        "units": "V",
        "dtype": "float64",
        "samples": [1.0, 3.0, 2.0, 4.0, 3.0, 5.0, 4.0, 6.0],
        "device_time_ns": [100, 500_000_100, 1_000_000_100, 1_500_000_100],
    }
    record.update(overrides)
    return record


def _write_mcap(
    path: Path,
    records: list[tuple[int, dict]],
    *,
    as_json: bool = False,
    schema_name: str | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = FileDescriptorSet()
    numeric_batch_pb2.DESCRIPTOR.CopyToProto(descriptor.file.add())
    encoding = "json" if as_json else "protobuf"
    name = schema_name or ("generic.numeric_batch/1" if as_json else "capture.v1.data.NumericBatch")
    with path.open("wb") as fh:
        writer = Writer(fh)
        writer.start(profile=encoding, library="capture-numeric-receiving")
        sid = writer.register_schema(
            name=name,
            encoding=encoding,
            data=b"" if as_json else descriptor.SerializeToString(),
        )
        cid = writer.register_channel(
            topic="numeric.source/numeric.stream/generic.numeric_batch/1",
            message_encoding=encoding,
            schema_id=sid,
            metadata={"data_schema_id": "generic.numeric_batch/1"},
        )
        for log_time, record in records:
            payload = (
                json.dumps(record).encode("utf-8")
                if as_json
                else numeric_batch_pb2.NumericBatch(**record).SerializeToString()
            )
            writer.add_message(
                channel_id=cid, log_time=log_time, publish_time=log_time, data=payload
            )
        writer.finish()
    return path


class NumericLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "numeric.mcap"
        self.ref = StreamRef(
            "numeric.source",
            "numeric.stream",
            "numeric",
            "generic.numeric_batch/1",
            2.0,
            "V",
            dimensions=(2,),
            mcap_paths=(self.path,),
        )
        self.window = TimeWindow(1_000_000_000, 3_000_000_000)

    def load(self, **kwargs) -> LoadedEmg:
        return load_numeric_batch(
            kwargs.pop("ref", self.ref),
            kwargs.pop("window", self.window),
            max_ram_bytes=kwargs.pop("max_ram_bytes", 16 * 1024**2),
            **kwargs,
        )

    def test_native_worker_schema_decodes_channels_units_and_session_time(self) -> None:
        _write_mcap(self.path, [(1_000_000_000, _batch())])
        before = self.path.read_bytes()
        loaded = self.load()
        self.assertEqual(loaded.channel_ids, ["left", "right"])
        self.assertEqual(loaded.units, "V")
        self.assertEqual(loaded.fs_hz, 2.0)
        self.assertEqual(loaded.batch_quality_flags, [0])
        np.testing.assert_array_equal(loaded.X, [[1, 2, 3, 4], [3, 4, 5, 6]])
        np.testing.assert_array_equal(
            loaded.t_sample_ns, [1_000_000_000, 1_500_000_000, 2_000_000_000, 2_500_000_000]
        )
        self.assertEqual(self.path.read_bytes(), before)

    def test_json_schema_alias_and_generated_channel_names(self) -> None:
        _write_mcap(self.path, [(1_000_000_000, _batch(channel_names=[]))], as_json=True)
        loaded = self.load()
        self.assertEqual(loaded.channel_ids, ["ch0", "ch1"])
        np.testing.assert_array_equal(loaded.X, [[1, 2, 3, 4], [3, 4, 5, 6]])

    def test_missing_native_times_use_rate_and_mark_interpolation(self) -> None:
        _write_mcap(self.path, [(1_000_000_000, _batch(device_time_ns=[]))])
        loaded = self.load(ref=replace(self.ref, nominal_rate_hz=4.0))
        np.testing.assert_array_equal(
            loaded.t_sample_ns, [1_000_000_000, 1_250_000_000, 1_500_000_000, 1_750_000_000]
        )
        self.assertEqual(loaded.batch_quality_flags, [1 << 3])
        _, meta, _ = extract_numeric_batch_features(loaded, GapMask(self.ref, self.window))
        self.assertTrue(all(row["interpolatedTimestamps"] for row in meta))
        self.assertTrue(all(row["provisional"] and not row["calibrated"] for row in meta))

    def test_empty_and_outside_window_return_valid_public_result(self) -> None:
        _write_mcap(self.path, [])
        empty = self.load()
        self.assertEqual(empty.X.shape, (0, 0))
        self.assertEqual(empty.t_sample_ns.size, 0)
        self.assertEqual(empty.units, "V")
        _write_mcap(self.path, [(1_000_000_000, _batch())])
        outside = self.load(window=TimeWindow(4_000_000_000, 5_000_000_000))
        self.assertEqual(outside.X.shape, (2, 0))
        self.assertEqual(outside.t_sample_ns.size, 0)

    def test_other_schema_is_not_decoded_as_numeric(self) -> None:
        _write_mcap(self.path, [(1_000_000_000, _batch())], schema_name="emg.batch/1")
        self.assertEqual(self.load().X.size, 0)

    def test_rate_is_required_and_finite(self) -> None:
        for rate in (0.0, -1.0, math.nan, math.inf):
            with self.assertRaisesRegex(ValueError, "rate|timebase"):
                self.load(ref=replace(self.ref, nominal_rate_hz=rate))

    def test_impossible_budget_refuses_before_iteration(self) -> None:
        with patch(
            "capture_analysis.loaders.numeric_batch.iter_mcap_messages",
            side_effect=AssertionError("iteration must not begin"),
        ):
            with self.assertRaises(RamBudgetExceeded):
                self.load(max_ram_bytes=1)

    def test_actual_batch_guard_does_not_trust_descriptor_density(self) -> None:
        record = _batch(samples=[1.0, 2.0] * 1000, device_time_ns=list(range(1000)))
        _write_mcap(self.path, [(1_000_000_000, record)])
        underestimated = replace(self.ref, nominal_rate_hz=0.01)
        with self.assertRaises(RamBudgetExceeded):
            self.load(ref=underestimated, max_ram_bytes=1_100_000)
        self.assertEqual(self.load(ref=underestimated).X.shape, (2, 1000))

    def test_actual_budget_accumulates_across_batches(self) -> None:
        record = _batch(samples=[1.0, 2.0] * 500, device_time_ns=list(range(500)))
        records = [(1_000_000_000 + offset * 1000, record) for offset in range(4)]
        _write_mcap(self.path, records)
        with self.assertRaises(RamBudgetExceeded):
            self.load(max_ram_bytes=1_280_000)
        self.assertEqual(self.load().X.shape, (2, 2000))

    def test_incomplete_frame_is_refused(self) -> None:
        _write_mcap(self.path, [(1_000_000_000, _batch(samples=[1, 2, 3]))])
        with self.assertRaisesRegex(ValueError, "whole frames"):
            self.load()

    def test_partial_device_times_are_refused(self) -> None:
        _write_mcap(self.path, [(1_000_000_000, _batch(device_time_ns=[1]))])
        with self.assertRaisesRegex(ValueError, "one value per frame"):
            self.load()

    def test_unpaired_timestamps_are_refused(self) -> None:
        _write_mcap(self.path, [(1_000_000_000, _batch(samples=[]))])
        with self.assertRaisesRegex(ValueError, "without sample frames"):
            self.load()

    def test_invalid_channel_names_are_refused(self) -> None:
        for names in (["a"], ["a", "a"], ["", "b"]):
            _write_mcap(self.path, [(1_000_000_000, _batch(channel_names=names))])
            with self.assertRaisesRegex(ValueError, "channel names"):
                self.load()

    def test_changing_layout_is_refused(self) -> None:
        records = [
            (1_000_000_000, _batch()),
            (2_000_000_000, _batch(channel_names=["right", "left"])),
        ]
        _write_mcap(self.path, records)
        with self.assertRaisesRegex(ValueError, "layout changed"):
            self.load()

    def test_backward_device_times_are_refused(self) -> None:
        _write_mcap(self.path, [(1_000_000_000, _batch(device_time_ns=[10, 9, 11, 12]))])
        with self.assertRaisesRegex(ValueError, "backwards"):
            self.load()

    def test_nonfinite_samples_are_refused(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            _write_mcap(self.path, [(1_000_000_000, _batch(samples=[value, 0] * 4))])
            with self.assertRaisesRegex(ValueError, "samples must be finite"):
                self.load()

    def test_session_timestamp_overflow_is_refused(self) -> None:
        _write_mcap(
            self.path,
            [((1 << 63) - 2, _batch(samples=[1, 2, 3, 4], device_time_ns=[0, 2]))],
        )
        with self.assertRaisesRegex(ValueError, "session timestamp outside int64"):
            self.load(window=TimeWindow(0, (1 << 63) - 1))

    def test_json_device_timestamp_overflow_is_refused(self) -> None:
        record = _batch(device_time_ns=[-(1 << 63) - 1, 0, 1, 2])
        _write_mcap(self.path, [(1_000_000_000, record)], as_json=True)
        with self.assertRaisesRegex(ValueError, "device timestamp outside int64"):
            self.load()

    def test_json_types_are_not_silently_coerced(self) -> None:
        for changes, message in (
            ({"channel_count": True}, "channel_count"),
            ({"samples": ["1", 2]}, "samples must be numbers"),
            ({"device_time_ns": [0.0, 1, 2, 3]}, "integer nanoseconds"),
        ):
            _write_mcap(self.path, [(1_000_000_000, _batch(**changes))], as_json=True)
            with self.assertRaisesRegex(ValueError, message):
                self.load()


class NumericFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ref = StreamRef("source", "stream", "numeric", "generic.numeric_batch/1", 2, "V")
        self.window = TimeWindow(0, 4_000_000_000)

    def test_large_and_small_finite_values_have_finite_correct_reductions(self) -> None:
        for values, mean, rms in (
            ([1e308, 1e308], 1e308, 1e308),
            ([-1e308, 1e308], 0.0, 1e308),
            ([1e-308, 1e-308], 1e-308, 1e-308),
            ([0.0, 0.0], 0.0, 0.0),
        ):
            loaded = LoadedEmg(["signal"], np.array([0, 500_000_000]), np.array([values]), 2.0, "V")
            with np.errstate(over="raise", invalid="raise"):
                df, _, _ = extract_numeric_batch_features(loaded, GapMask(self.ref, self.window))
            self.assertTrue(math.isclose(df.iloc[0]["signal_mean"], mean, rel_tol=1e-12))
            self.assertTrue(math.isclose(df.iloc[0]["signal_rms"], rms, rel_tol=1e-12))

    def test_known_gap_masks_samples_and_fail_policy_refuses(self) -> None:
        loaded = LoadedEmg(
            ["signal"],
            np.array([0, 500_000_000, 1_000_000_000, 1_500_000_000]),
            np.array([[1.0, 1000.0, 3.0, 4.0]]),
            2.0,
            "V",
        )
        gap = GapInterval("source", "stream", "DISCONNECT", 500_000_000, 500_000_000, True)
        mask = GapMask(self.ref, self.window, [gap], "mask")
        df, _, vf = extract_numeric_batch_features(loaded, mask, window_s=2.0)
        self.assertEqual(vf, 0.75)
        self.assertEqual(df.iloc[0]["gap_fraction"], 0.25)
        self.assertAlmostEqual(df.iloc[0]["signal_mean"], 8.0 / 3.0)
        self.assertAlmostEqual(df.iloc[0]["signal_rms"], math.sqrt(26.0 / 3.0))
        with self.assertRaisesRegex(RuntimeError, "gap_policy=fail"):
            extract_numeric_batch_features(loaded, replace(mask, policy="fail"))

    def test_split_does_not_bridge_a_gap_without_samples(self) -> None:
        loaded = LoadedEmg(
            ["signal"],
            np.array([0, 500_000_000, 3_000_000_000, 3_500_000_000]),
            np.array([[1.0, 2.0, 3.0, 4.0]]),
            2.0,
            "V",
        )
        gap = GapInterval("source", "stream", "DISCONNECT", 1_000_000_000, 2_900_000_000, True)
        df, _, vf = extract_numeric_batch_features(
            loaded, GapMask(self.ref, self.window, [gap], "split")
        )
        self.assertEqual(vf, 1.0)
        self.assertEqual(df["t_start_ns"].tolist(), [0, 3_000_000_000])
        self.assertEqual(df["t_end_ns"].tolist(), [1_000_000_000, 4_000_000_000])
        self.assertEqual(df["signal_mean"].tolist(), [1.5, 3.5])

    def test_public_feature_shape_and_rate_are_validated(self) -> None:
        mask = GapMask(self.ref, self.window)
        loaded = LoadedEmg(["signal"], np.array([0, 1]), np.array([[1.0, 2.0]]), 2.0, "V")
        for bad in (replace(loaded, X=np.array([[1.0]])), replace(loaded, fs_hz=0.0)):
            with self.assertRaises(ValueError):
                extract_numeric_batch_features(bad, mask)


class NumericPipelineTests(unittest.TestCase):
    def test_schema_route_precedes_descriptive_modality(self) -> None:
        registry = get_registry()
        for modality in ("numeric", "emg", "eeg", "radar", ""):
            ref = StreamRef(
                "source",
                "stream",
                modality,
                "generic.numeric_batch/1",
                2,
                "V",
                mcap_paths=(Path("recording.mcap"),),
            )
            handler = registry.stream_handler_for(ref)
            self.assertIsNotNone(handler, modality)
            self.assertEqual(handler.__name__, "handle_numeric", modality)

    def test_non_numeric_modality_routes_remain_available(self) -> None:
        registry = get_registry()
        for modality, schema, expected in (
            ("emg", "emg.batch/1", "handle_emg"),
            ("imu", "imu.frame/1", "handle_imu"),
        ):
            ref = StreamRef(
                "source", "stream", modality, schema, 2, "V", mcap_paths=(Path("recording.mcap"),)
            )
            self.assertEqual(registry.stream_handler_for(ref).__name__, expected)
        unknown = StreamRef("source", "stream", "numeric", "generic.numeric_batch/2", 2, "V")
        self.assertIsNone(registry.stream_handler_for(unknown))

    def test_durationless_two_stream_package_writes_real_numeric_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "numeric.mmsession"
            package.mkdir()
            (package / "manifest.json").write_text(
                json.dumps({"sessionId": "numeric.receiving", "state": "sealed"}), encoding="utf-8"
            )
            for index, stream_id in enumerate(("eeg/left", "eeg%2Fleft")):
                stream = package / "sources" / "lsl" / "streams" / f"stream{index}"
                path = stream / "segments" / "000000.mcap"
                _write_mcap(path, [(1_000_000_000, _batch())])
                (stream / "stream.json").write_text(
                    json.dumps(
                        {
                            "sourceId": "lsl",
                            "streamId": stream_id,
                            "modality": "eeg",
                            "dataSchemaId": "generic.numeric_batch/1",
                            "nominalRateHz": 2.0,
                            "units": "V",
                            "dimensions": [2],
                        }
                    ),
                    encoding="utf-8",
                )
            before = hash_sources_tree(package)
            summary = load_review_summary(package)
            self.assertEqual(summary.duration_ns, 0)
            work = package / "processing" / "jobs" / "numeric-receiving"
            work.mkdir(parents=True)
            outputs, warnings, tables = [], [], []
            context = run_features_and_plots(
                package,
                work,
                summary,
                full_window(summary),
                gap_policy="mask",
                max_ram_bytes=16 * 1024**2,
                sources_filter=[],
                do_features=True,
                do_plots=True,
                outputs=outputs,
                warnings=warnings,
                feature_tables=tables,
            )
            self.assertEqual(warnings, [])
            self.assertEqual(hash_sources_tree(package), before)
            self.assertEqual(len(tables), 2)
            self.assertEqual(len({table["relativePath"] for table in tables}), 2)
            self.assertEqual(context["valid_fractions"], {"lsl": 1.0})
            for table in tables:
                self.assertTrue(table["relativePath"].startswith("features/numeric/"))
                df = pd.read_parquet(work / table["relativePath"])
                self.assertEqual(table["rows"], 3)
                self.assertEqual(df["left_mean"].tolist(), [1.5, 2.5, 3.5])
                self.assertTrue(np.isfinite(df.to_numpy()).all())
            self.assertEqual(len({output["relativePath"] for output in outputs}), len(outputs))
            for output in outputs:
                path = work / output["relativePath"]
                data = path.read_bytes()
                self.assertEqual(output["sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(output["bytes"], len(data))
                if output["kind"] == "figure":
                    self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
            schema = json.loads((work / "features" / "_schema.json").read_text(encoding="utf-8"))
            self.assertEqual(len(schema["tables"]), 2)
            for descriptor in schema["tables"].values():
                self.assertTrue(all(row["provisional"] for row in descriptor["columns"]))
                self.assertTrue(all(not row["calibrated"] for row in descriptor["columns"]))
                self.assertEqual(
                    next(
                        row["units"] for row in descriptor["columns"] if row["name"] == "left_mean"
                    ),
                    "V",
                )
            series = json.loads(
                (work / "figures" / "sync_dashboard_series.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(series["series"]), 2)
            self.assertTrue(all(row["label"].startswith("Numeric ") for row in series["series"]))


if __name__ == "__main__":
    unittest.main()
