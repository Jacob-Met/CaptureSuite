# SPDX-License-Identifier: GPL-3.0-only
"""Receive recorded stream gaps through native masks and feature extraction."""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np
from capture_analysis import discover_streams
from capture_analysis.features.emg import extract_emg_features
from capture_analysis.types import GapInterval, LoadedEmg, StreamRef, TimeWindow
from capture_analysis.windows import (
    build_gap_mask,
    enforce_gap_policy,
    gaps_to_intervals,
    validity_mask,
)
from capture_session.package_reader import GapSummary, load_review_summary

SECOND = 1_000_000_000
TIMES = np.arange(6, dtype=np.int64) * SECOND
WINDOW = TimeWindow(0, 5 * SECOND)


def stream(source: str = "source.shared", name: str = "healthy") -> StreamRef:
    return StreamRef(source, name, "emg", "emg.batch/1", 1.0, "mV")


def gap(
    source: str = "source.shared",
    name: str = "interrupted",
    start: int = 2 * SECOND,
    end: int | None = 3 * SECOND,
) -> GapInterval:
    return GapInterval(source, name, "disconnect", start, end, end is not None)


def summary_gap(value: GapInterval) -> GapSummary:
    return GapSummary(
        value.source_id,
        value.stream_id,
        value.cause,
        value.start_session_ns,
        value.end_session_ns,
        value.closed,
    )


def loaded_samples() -> LoadedEmg:
    return LoadedEmg(
        channel_ids=["amplitude"],
        t_sample_ns=TIMES.copy(),
        X=np.array([[1, 2, 3, 4, 5, 6]], dtype=np.float32),
        fs_hz=1.0,
        units="mV",
    )


class StreamGapScopeTests(unittest.TestCase):
    def assert_mask(self, ref, gaps, expected, *, policy="mask"):
        mask = build_gap_mask(ref, WINDOW, gaps, policy=policy)
        self.assertEqual(validity_mask(TIMES, mask).tolist(), expected)
        return mask

    def test_recorded_gap_does_not_mask_another_stream_from_the_same_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "streams.mmsession"
            package.mkdir()
            (package / "manifest.json").write_text(
                json.dumps({"sessionId": "stream-scope-fixture", "state": "finalized"}),
                encoding="utf-8",
            )
            for source, name in [
                ("source.shared", "interrupted"),
                ("source.shared", "healthy"),
                ("source.other", "interrupted"),
            ]:
                directory = package / "sources" / source / "streams" / name
                directory.mkdir(parents=True)
                (directory / "stream.json").write_text(
                    json.dumps(
                        {
                            "sourceId": source,
                            "streamId": name,
                            "modality": "emg",
                            "dataSchemaId": "emg.batch/1",
                            "nominalRateHz": 1.0,
                            "units": "mV",
                        }
                    ),
                    encoding="utf-8",
                )
            health = package / "sources" / "source.shared" / "health"
            health.mkdir()
            (health / "gaps.jsonl").write_text(
                json.dumps(
                    {
                        "streamId": "interrupted",
                        "cause": "GAP_CAUSE_DISCONNECT",
                        "startSessionTimeNs": str(2 * SECOND),
                        "endSessionTimeNs": str(3 * SECOND),
                        "closed": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            before = {
                path.relative_to(package).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in package.rglob("*")
                if path.is_file()
            }
            summary = load_review_summary(package)
            self.assertEqual(len(summary.gaps), 1)
            self.assertEqual(summary.gaps[0].source_id, "source.shared")
            self.assertEqual(summary.gaps[0].stream_id, "interrupted")
            expected = {
                ("source.shared", "interrupted"): [True, True, False, False, True, True],
                ("source.shared", "healthy"): [True] * 6,
                ("source.other", "interrupted"): [True] * 6,
            }
            references = discover_streams(package)
            self.assertEqual(len(references), 3)
            for representation in [summary.gaps, gaps_to_intervals(summary)]:
                for ref in references:
                    with self.subTest(
                        representation=type(representation[0]).__name__,
                        source=ref.source_id,
                        stream=ref.stream_id,
                    ):
                        self.assert_mask(
                            ref, representation, expected[(ref.source_id, ref.stream_id)]
                        )
            after = {
                path.relative_to(package).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in package.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_healthy_feature_values_keep_all_samples_despite_a_sibling_gap(self):
        for recorded in [gap(), summary_gap(gap())]:
            with self.subTest(representation=type(recorded).__name__):
                loaded = loaded_samples()
                original = loaded.X.copy()
                mask = build_gap_mask(stream(), WINDOW, [recorded])
                frame, _, fraction = extract_emg_features(
                    loaded, mask, window_s=6.0, hop_s=6.0
                )
                self.assertEqual(fraction, 1.0)
                self.assertEqual(len(frame), 1)
                self.assertEqual(frame.iloc[0]["valid_fraction"], 1.0)
                self.assertAlmostEqual(frame.iloc[0]["amplitude_rms"], math.sqrt(91 / 6))
                self.assertAlmostEqual(frame.iloc[0]["amplitude_mav"], 3.5)
                np.testing.assert_array_equal(loaded.X, original)
                np.testing.assert_array_equal(loaded.t_sample_ns, TIMES)

    def test_fail_policy_accepts_healthy_stream_when_only_sibling_is_interrupted(self):
        for recorded in [gap(), summary_gap(gap())]:
            with self.subTest(representation=type(recorded).__name__):
                mask = build_gap_mask(stream(), WINDOW, [recorded], policy="fail")
                frame, _, fraction = extract_emg_features(
                    loaded_samples(), mask, window_s=6.0, hop_s=6.0
                )
                self.assertEqual(fraction, 1.0)
                self.assertEqual(len(frame), 1)

    def test_targeted_open_gap_does_not_remove_the_rest_of_a_sibling_stream(self):
        for recorded in [gap(end=None), summary_gap(gap(end=None))]:
            with self.subTest(representation=type(recorded).__name__):
                self.assert_mask(stream(), [recorded], [True] * 6)
                self.assert_mask(
                    stream(name="interrupted"),
                    [recorded],
                    [True, True, False, False, False, False],
                )

    def test_source_wide_gap_still_masks_all_streams_of_that_source(self):
        for recorded in [gap(name=""), summary_gap(gap(name=""))]:
            for name in ["healthy", "interrupted"]:
                with self.subTest(representation=type(recorded).__name__, stream=name):
                    self.assert_mask(
                        stream(name=name),
                        [recorded],
                        [True, True, False, False, True, True],
                    )
                    self.assert_mask(stream("source.other", name), [recorded], [True] * 6)

    def test_unspecified_source_and_stream_keep_existing_global_gap_behavior(self):
        for recorded in [gap(source="", name=""), summary_gap(gap(source="", name=""))]:
            for source in ["source.shared", "source.other"]:
                with self.subTest(representation=type(recorded).__name__, source=source):
                    self.assert_mask(
                        stream(source), [recorded], [True, True, False, False, True, True]
                    )

    def test_matching_gap_still_masks_samples_and_rejects_fail_policy(self):
        for recorded in [gap(name="healthy"), summary_gap(gap(name="healthy"))]:
            with self.subTest(representation=type(recorded).__name__):
                mask = self.assert_mask(
                    stream(), [recorded], [True, True, False, False, True, True], policy="fail"
                )
                with self.assertRaisesRegex(RuntimeError, "gap_policy=fail"):
                    enforce_gap_policy(mask, validity_mask(TIMES, mask))

    def test_other_sources_and_nonoverlapping_gaps_preserve_valid_samples(self):
        recorded = [
            gap(source="source.other", name="healthy"),
            gap(name="healthy", start=-2 * SECOND, end=-SECOND),
            gap(name="healthy", start=6 * SECOND, end=7 * SECOND),
        ]
        for representation in [recorded, list(map(summary_gap, recorded))]:
            with self.subTest(representation=type(representation[0]).__name__):
                self.assert_mask(stream(), representation, [True] * 6)


if __name__ == "__main__":
    unittest.main()
