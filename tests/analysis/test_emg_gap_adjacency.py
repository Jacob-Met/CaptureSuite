# SPDX-License-Identifier: GPL-3.0-only
"""EMG transition features need consecutive observations across recorded gaps."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from capture_analysis.features.emg import extract_emg_features
from capture_analysis.types import GapInterval, GapMask, LoadedEmg, StreamRef, TimeWindow


def write_gapped_emg_package(destination: Path) -> Path:
    """Two real MCAP batches with a recorded, unobserved disconnect between them."""
    from capture_protocol.generated.capture.v1.data import emg_batch_pb2
    from mcap.writer import Writer

    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "mini_session"
    shutil.copytree(fixture, destination)
    shutil.rmtree(destination / "sources" / "sim.imu.upper")
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sourceIds"] = ["sim.emg.main"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source = destination / "sources" / "sim.emg.main"
    stream = source / "streams" / "sim.emg.main.batch"
    stream_path = stream / "stream.json"
    description = json.loads(stream_path.read_text(encoding="utf-8"))
    description.update(nominalRateHz=40.0, dimensions=[1])
    stream_path.write_text(json.dumps(description), encoding="utf-8")
    mcap_path = stream / "segments" / "000000.mcap"
    with mcap_path.open("wb") as output:
        writer = Writer(output)
        writer.start(profile="", library="capturesuite-gap-regression")
        schema = writer.register_schema(name="emg.batch/1", encoding="protobuf", data=b"")
        channel = writer.register_channel(
            topic="emg", message_encoding="protobuf", schema_id=schema
        )
        for sequence, (start, level) in enumerate([(0, 1.0), (125_000_000, -1.0)]):
            message = emg_batch_pb2.EmgBatch()
            message.timing.session_time_ns = start
            message.timing.sequence_number = sequence
            message.first_sample_index = sequence * 5
            message.sample_count = 2
            message.channel_ids.append("ch0")
            message.samples_f32_le = np.array([level, level], dtype="<f4").tobytes()
            writer.add_message(
                channel_id=channel,
                log_time=start,
                publish_time=start,
                data=message.SerializeToString(),
            )
        writer.finish()
    (source / "health" / "gaps.jsonl").write_text(
        json.dumps(
            {
                "streamId": "sim.emg.main.batch",
                "cause": "GAP_CAUSE_DISCONNECT",
                "startSessionTimeNs": "50000000",
                "endSessionTimeNs": "100000000",
                "closed": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    integrity_path = destination / "integrity.json"
    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    integrity["files"][0].update(
        endSessionTimeNs=150_000_000,
        sizeBytes=mcap_path.stat().st_size,
        sha256=hashlib.sha256(mcap_path.read_bytes()).hexdigest(),
    )
    integrity_path.write_text(json.dumps(integrity), encoding="utf-8")
    return destination


class EmgGapAdjacencyTests(unittest.TestCase):
    def extract(self, values, *, times=None, gaps=(), policy="mask", window_s=None, hop_s=None):
        x = np.asarray(values, dtype=np.float32)
        if x.ndim == 1:
            x = x[np.newaxis, :]
        t = np.asarray(
            times if times is not None else np.arange(x.shape[1]) * 100_000_000, dtype=np.int64
        )
        stream = StreamRef("synthetic.emg", "samples", "emg", "emg.batch/1", 10.0, "mV")
        window = TimeWindow(int(t.min()) if t.size else 0, int(t.max()) if t.size else 0)
        mask = GapMask(
            stream,
            window,
            [
                GapInterval(
                    stream.source_id, stream.stream_id, "DISCONNECT", start, end, end is not None
                )
                for start, end in gaps
            ],
            policy,
        )
        loaded = LoadedEmg([f"ch{i}" for i in range(x.shape[0])], t, x, 10.0, "mV")
        original_x, original_t = x.copy(), t.copy()
        size_s = max(x.shape[1], 1) / 10.0
        result = extract_emg_features(
            loaded, mask, window_s=window_s or size_s, hop_s=hop_s or size_s
        )
        np.testing.assert_array_equal(x, original_x)
        np.testing.assert_array_equal(t, original_t)
        return result

    def test_constant_runs_with_retained_invalid_sample(self):
        table, _, fraction = self.extract([1, 1, 99, -1, -1], gaps=[(200_000_000, 200_000_000)])
        row = table.iloc[0]
        self.assertEqual((row.ch0_wl, row.ch0_zc, row.ch0_ssc), (0, 0, 0))
        self.assertEqual((row.ch0_rms, row.ch0_mav, row.valid_fraction, fraction), (1, 1, 0.8, 0.8))
        self.assertEqual(row.t_mid_ns, 200_000_000)

    def test_gap_between_retained_samples_still_breaks_adjacency(self):
        table, _, fraction = self.extract(
            [1, 1, -1, -1],
            times=[0, 100_000_000, 500_000_000, 600_000_000],
            gaps=[(200_000_000, 400_000_000)],
        )
        row = table.iloc[0]
        self.assertEqual((row.ch0_wl, row.ch0_zc, row.ch0_ssc), (0, 0, 0))
        self.assertEqual((row.ch0_rms, row.ch0_mav, row.valid_fraction, fraction), (1, 1, 1, 1))

    def test_slope_changes_require_uninterrupted_triples(self):
        table, _, _ = self.extract([0, 1, 99, 0, 1], gaps=[(200_000_000, 200_000_000)])
        row = table.iloc[0]
        self.assertEqual((row.ch0_wl, row.ch0_zc, row.ch0_ssc), (2, 0, 0))
        self.assertEqual((row.ch0_rms, row.ch0_mav), (np.sqrt(0.5), 0.5))

    def test_real_turns_inside_each_run_are_retained(self):
        table, _, _ = self.extract([0, 2, 1, 99, 2, 1, 3], gaps=[(300_000_000, 300_000_000)])
        row = table.iloc[0]
        self.assertEqual((row.ch0_wl, row.ch0_zc, row.ch0_ssc), (6, 0, 2))

    def test_isolated_valid_samples_have_no_transition_features(self):
        table, _, _ = self.extract(
            [1, 99, -1, 99, 1], gaps=[(100_000_000, 100_000_000), (300_000_000, 300_000_000)]
        )
        row = table.iloc[0]
        self.assertEqual((row.ch0_wl, row.ch0_zc, row.ch0_ssc), (0, 0, 0))
        self.assertEqual((row.ch0_rms, row.ch0_mav), (1, 1))

    def test_no_gap_features_keep_the_existing_definition(self):
        table, meta, fraction = self.extract([-2, 1, 3, -1, 1])
        row = table.iloc[0]
        self.assertEqual((row.ch0_wl, row.ch0_zc, row.ch0_ssc), (11, 3, 2))
        self.assertEqual((row.ch0_rms, row.ch0_mav, fraction), (np.sqrt(3.2), 1.6, 1))
        self.assertEqual(
            list(table.columns),
            ["t_mid_ns", "valid_fraction", "ch0_rms", "ch0_mav", "ch0_wl", "ch0_zc", "ch0_ssc"],
        )
        self.assertEqual([field["name"] for field in meta], list(table.columns))

    def test_gaps_outside_the_window_do_not_change_values(self):
        expected = self.extract([-2, 1, 3, -1, 1])
        actual = self.extract([-2, 1, 3, -1, 1], gaps=[(-400, -200), (800_000_000, None)])
        self.assertEqual(actual[0].to_dict(), expected[0].to_dict())
        self.assertEqual(actual[1:], expected[1:])

    def test_open_gap_keeps_only_the_observed_prefix(self):
        table, _, fraction = self.extract([0, 2, 1, -99, 99], gaps=[(250_000_000, None)])
        row = table.iloc[0]
        self.assertEqual((row.ch0_wl, row.ch0_zc, row.ch0_ssc), (3, 0, 1))
        self.assertEqual(fraction, 0.6)

    def test_masked_values_cannot_affect_any_feature_or_channel(self):
        expected = self.extract(
            [[1, 1, 0, -1, -1], [0, 1, 0, 0, 1]], gaps=[(200_000_000, 200_000_000)]
        )
        for value in [999, -999, float("nan"), float("inf")]:
            with self.subTest(value=value):
                actual = self.extract(
                    [[1, 1, value, -1, -1], [0, 1, value, 0, 1]], gaps=[(200_000_000, 200_000_000)]
                )
                self.assertEqual(actual[0].to_dict(), expected[0].to_dict())
                self.assertEqual(actual[1:], expected[1:])
        self.assertEqual(expected[0][["ch0_wl", "ch1_wl"]].values.tolist(), [[0, 2]])

    def test_overlapping_windows_do_not_join_separate_runs(self):
        table, _, _ = self.extract(
            [0, 1, 99, 0, 1, 2], gaps=[(200_000_000, 200_000_000)], window_s=0.4, hop_s=0.2
        )
        self.assertEqual(table.t_mid_ns.tolist(), [100_000_000, 400_000_000])
        self.assertEqual(table.ch0_wl.tolist(), [1, 2])
        self.assertEqual(table.ch0_ssc.tolist(), [0, 0])

    def test_interval_tests_preserve_integer_nanoseconds(self):
        for origin in [-(1 << 53), 1 << 53]:
            with self.subTest(origin=origin):
                table, _, _ = self.extract(
                    [1, 1, -1, -1],
                    times=[origin + k for k in [0, 1, 4, 5]],
                    gaps=[(origin + 2, origin + 3)],
                )
                self.assertEqual(table.ch0_wl.tolist(), [0])
                self.assertEqual(table.ch0_zc.tolist(), [0])

    def test_empty_fully_masked_and_single_sample_inputs(self):
        for values, gaps in [([], []), ([1, 2, 3], [(0, None)])]:
            table, meta, fraction = self.extract(values, gaps=gaps)
            self.assertTrue(table.empty)
            self.assertEqual(fraction, 0)
        table, _, fraction = self.extract([-2])
        row = table.iloc[0]
        self.assertEqual(
            (row.ch0_rms, row.ch0_mav, row.ch0_wl, row.ch0_zc, row.ch0_ssc), (2, 2, 0, 0, 0)
        )
        self.assertEqual(fraction, 1)

    def test_existing_split_and_fail_policy_behavior(self):
        masked = self.extract([1, 1, 99, -1, -1], gaps=[(200_000_000, 200_000_000)])
        split = self.extract([1, 1, 99, -1, -1], gaps=[(200_000_000, 200_000_000)], policy="split")
        self.assertEqual(masked[0].to_dict(), split[0].to_dict())
        self.assertEqual(masked[1:], split[1:])
        with self.assertRaisesRegex(RuntimeError, "gap_policy=fail"):
            self.extract([1, 1, 99, -1, -1], gaps=[(200_000_000, 200_000_000)], policy="fail")

    def test_recorded_mcap_gap_reaches_saved_feature_tables(self):
        import pandas as pd
        from capture_analysis import JobParams, hash_sources_tree, run

        with tempfile.TemporaryDirectory() as temporary:
            package = write_gapped_emg_package(Path(temporary) / "gap.mmsession")
            before = hash_sources_tree(package)
            result = run(package, JobParams(command="features", overwrite_job_id="gap-regression"))
            self.assertIn(result.status, ("completed", "completed_with_warnings"))
            self.assertEqual(hash_sources_tree(package), before)
            relative = "features/emg/sim.emg.main/windows.parquet"
            table = pd.read_parquet(result.job_dir / relative)
            self.assertEqual(len(table), 1)
            row = table.iloc[0]
            self.assertEqual((row.ch0_wl, row.ch0_zc, row.ch0_ssc), (0, 0, 0))
            self.assertEqual((row.ch0_rms, row.ch0_mav, row.valid_fraction), (1, 1, 1))
            self.assertEqual(row.t_mid_ns, 75_000_000)
            csv = pd.read_csv(result.job_dir / relative.replace(".parquet", ".csv"))
            pd.testing.assert_frame_equal(csv, table)
            schema = json.loads((result.job_dir / "features" / "_schema.json").read_text())
            self.assertEqual(schema["tables"][relative]["featureSchemaVersion"], 1)
            self.assertEqual(
                [column["name"] for column in schema["tables"][relative]["columns"]],
                list(table.columns),
            )


if __name__ == "__main__":
    unittest.main()
