# SPDX-License-Identifier: GPL-3.0-only
"""Exercise saved-QC admission and literal comparison through the real CLI."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "tools" / "compare_qc_reports.py"


def report():
    return {
        "schemaId": "capture.analysis_qc/2",
        "packagePath": "saved/fictional.mmsession",
        "sessionId": "fictional-session",
        "packageState": "finalized",
        "durationNs": 100,
        "manifestSha256": "a" * 64,
        "sourceCount": 1,
        "streamCount": 1,
        "openGapCount": 1,
        "closedGapCount": 0,
        "checkpointCount": 0,
        "annotationCount": 0,
        "syncAnchorCount": 0,
        "recoveryReports": [],
        "integrityFileCount": 1,
        "warnings": ["saved observation"],
        "trafficLights": {"sensor": "warn"},
        "streams": [
            {
                "sourceId": "sensor",
                "streamId": "stream",
                "modality": "emg",
                "dataSchemaId": "emg.fixture/1",
                "nominalRateHz": 1000.0,
                "units": "fictional",
                "mcapSegments": 1,
                "mkvSegments": 0,
                "timingSegments": 0,
                "rateOk": True,
                "warnings": [],
            }
        ],
        "gaps": [
            {
                "sourceId": "sensor",
                "streamId": "stream",
                "cause": "fixture",
                "startSessionTimeNs": "9007199254740993",
                "endSessionTimeNs": None,
                "closed": False,
                "estimatedLostCount": "3",
                "durationNs": None,
                "durationStatus": "open",
            }
        ],
    }


def raw(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode()


class SavedQcComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="saved QC Ω ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.first = self.root / "first Ω.json"
        self.second = self.root / "second.json"
        self.source = TOOL.read_bytes()

    def invoke(self, first=None, second=None, *, human=False):
        self.first.write_bytes(raw(report()) if first is None else first)
        self.second.write_bytes(raw(report()) if second is None else second)
        before = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        args = [sys.executable, str(TOOL), str(self.first), str(self.second)]
        if not human:
            args.append("--json")
        result = subprocess.run(args, capture_output=True, timeout=10)
        self.assertEqual(
            before, {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        )
        self.assertEqual(TOOL.read_bytes(), self.source)
        return result

    def comparison(self, a, b):
        result = self.invoke(raw(a), raw(b))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stderr, b"")
        return json.loads(result.stdout)

    def test_format_only_preserves_distinct_full_byte_hashes(self):
        a = raw(report())
        b = json.dumps(report(), sort_keys=True, indent=2).encode()
        result = self.invoke(a, b)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["equal"])
        self.assertEqual(data["differences"], [])
        self.assertEqual(data["schemaId"], "capture.saved_qc_comparison/1")
        self.assertEqual(data["scope"], "saved_report_values_only")
        for key, captured in (("first", a), ("second", b)):
            self.assertEqual(
                data[key],
                {
                    "bytes": len(captured),
                    "sha256": hashlib.sha256(captured).hexdigest(),
                    "document": report(),
                },
            )

    def test_gap_closure_is_literal_without_counter_recomputation(self):
        a = report()
        b = copy.deepcopy(a)
        b["gaps"][0].update(
            closed=True,
            endSessionTimeNs="9007199254741010",
            durationNs="17",
            durationStatus="known",
        )
        data = self.comparison(a, b)
        self.assertEqual(
            [r["pointer"] for r in data["differences"]],
            [
                "/gaps/0/closed",
                "/gaps/0/durationNs",
                "/gaps/0/durationStatus",
                "/gaps/0/endSessionTimeNs",
            ],
        )
        self.assertEqual(data["second"]["document"]["openGapCount"], 1)
        self.assertEqual(
            data["second"]["document"]["gaps"][0]["startSessionTimeNs"], "9007199254740993"
        )

    def test_unknown_extension_missing_null_and_pointer_escape(self):
        a, b = report(), report()
        a["extension"] = {"/~": 7, "gone": None}
        b["extension"] = {"/~": 8, "new": None}
        rows = self.comparison(a, b)["differences"]
        self.assertEqual(
            rows,
            [
                {
                    "pointer": "/extension/gone",
                    "before": {"present": True, "value": None},
                    "after": {"present": False, "value": None},
                },
                {
                    "pointer": "/extension/new",
                    "before": {"present": False, "value": None},
                    "after": {"present": True, "value": None},
                },
                {
                    "pointer": "/extension/~1~0",
                    "before": {"present": True, "value": 7},
                    "after": {"present": True, "value": 8},
                },
            ],
        )

    def test_scalar_types_signed_zero_and_large_integers(self):
        cases = [(False, 0), (1, 1.0), (-0.0, 0.0), (2**70, 2**70 + 1)]
        for first, second in cases:
            with self.subTest(first=repr(first), second=repr(second)):
                a, b = report(), report()
                a["extension"], b["extension"] = first, second
                row = self.comparison(a, b)["differences"][0]
                self.assertEqual(row["pointer"], "/extension")
                self.assertEqual(json.dumps(row["before"]["value"]), json.dumps(first))
                self.assertEqual(json.dumps(row["after"]["value"]), json.dumps(second))
        self.assertEqual(math.copysign(1.0, cases[2][0]), -1)

    def test_array_order_duplicates_and_lexicographic_pointer_order(self):
        a, b = report(), report()
        a["extension"] = [0] * 12
        b["extension"] = [0] * 12
        b["extension"][2] = 1
        b["extension"][10] = 1
        self.assertEqual(
            [r["pointer"] for r in self.comparison(a, b)["differences"]],
            ["/extension/10", "/extension/2"],
        )
        a["extension"], b["extension"] = [1, 1, 2], [2, 1]
        rows = self.comparison(a, b)["differences"]
        self.assertEqual([r["pointer"] for r in rows], ["/extension/0", "/extension/2"])
        self.assertFalse(rows[1]["after"]["present"])

    def test_added_container_is_one_complete_subtree(self):
        a, b = report(), report()
        b["extension"] = {"retained": [None, False, 3.5]}
        row = self.comparison(a, b)["differences"][0]
        self.assertEqual(row["pointer"], "/extension")
        self.assertEqual(row["after"]["value"], b["extension"])

    def test_version_one_without_gaps_and_version_two_keep_schema_difference(self):
        a = report()
        a["schemaId"] = "capture.analysis_qc/1"
        del a["gaps"]
        result = self.invoke(raw(a), raw(a))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.comparison(a, report())
        self.assertEqual([r["pointer"] for r in data["differences"]], ["/gaps", "/schemaId"])

    def test_human_labels_and_values_are_escaped(self):
        a, b = report(), report()
        a["sessionId"] = "fictional Ω\n\x1b"
        b["sessionId"] = "other\t"
        result = self.invoke(raw(a), raw(b), human=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        text = result.stdout.decode("ascii")
        self.assertIn('"fictional \\u03a9\\n\\u001b"', text)
        self.assertIn('"/sessionId"', text)
        self.assertNotIn("\x1b", text)
        self.assertIn(hashlib.sha256(raw(a)).hexdigest(), text)

    def test_invalid_second_never_emits_comparison(self):
        bad = [
            b"{",
            b"\xff",
            b'{"schemaId":"x","schemaId":"y"}',
            raw(report()).replace(b'"durationNs": 100', b'"durationNs": 1e309'),
            raw(report()).replace(b'"durationNs": 100', b'"durationNs": NaN'),
        ]
        for value in bad:
            with self.subTest(value=value[:30]):
                result = self.invoke(second=value)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertTrue(result.stderr.startswith(b"error: "))

    def test_known_fields_are_structural_and_bool_is_not_integer(self):
        variants = []
        for field, value in (
            ("schemaId", "capture.analysis_qc/9"),
            ("durationNs", True),
            ("warnings", "bad"),
            ("trafficLights", {"sensor": 1}),
        ):
            v = report()
            v[field] = value
            variants.append(v)
        v = report()
        del v["sessionId"]
        variants.append(v)
        v = report()
        v["streams"][0]["nominalRateHz"] = True
        variants.append(v)
        v = report()
        v["gaps"][0]["closed"] = 1
        variants.append(v)
        v = report()
        v["gaps"][0]["startSessionTimeNs"] = 4
        variants.append(v)
        for value in variants:
            with self.subTest(value=value):
                result = self.invoke(second=raw(value))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")

    def test_depth_node_and_byte_limits_refuse_before_output(self):
        a = report()
        nested = None
        for _ in range(63):
            nested = [nested]
        a["extension"] = nested
        self.assertEqual(self.invoke(raw(a), raw(a)).returncode, 0)
        a["extension"] = [nested]
        b = report()
        b["extension"] = [0] * 50_000
        for value in (raw(a), raw(b), b" " * (2 * 1024 * 1024 + 1)):
            result = self.invoke(second=value)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stdout, b"")

    def test_complete_output_bound_precedes_stdout(self):
        a, b = report(), report()
        # Unicode key escapes and their repetition in each pointer exceed the result cap.
        for index in range(240):
            key = str(index) + "Ω" * 4000
            a[key], b[key] = 0, 1
        first, second = raw(a), raw(b)
        self.assertLess(len(first), 2 * 1024 * 1024)
        result = self.invoke(first, second)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"16 MiB", result.stderr)

    def test_directory_missing_file_and_fifo_refuse(self):
        self.first.write_bytes(raw(report()))
        candidates = [self.root, self.root / "missing.json"]
        if hasattr(os, "mkfifo"):
            fifo = self.root / "selected.fifo"
            os.mkfifo(fifo)
            candidates.append(fifo)
        for path in candidates:
            with self.subTest(path=path):
                result = subprocess.run(
                    [sys.executable, str(TOOL), str(self.first), str(path), "--json"],
                    capture_output=True,
                    timeout=5,
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")

    def test_closed_stdout_is_output_failure_two_without_shutdown_error(self):
        self.first.write_bytes(raw(report()))
        incoming, outgoing = os.pipe()
        os.close(incoming)
        try:
            result = subprocess.run(
                [sys.executable, str(TOOL), str(self.first), str(self.first), "--json"],
                stdout=outgoing,
                stderr=subprocess.PIPE,
                timeout=5,
            )
        finally:
            os.close(outgoing)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(b"Exception ignored", result.stderr)

    @unittest.skipUnless(Path("/dev/full").exists(), "requires a failing output device")
    def test_full_output_device_returns_two_without_shutdown_error(self):
        self.first.write_bytes(raw(report()))
        second = report()
        second["sessionId"] = "different recorded identity"
        self.second.write_bytes(raw(second))
        before = (self.first.read_bytes(), self.second.read_bytes())
        with open("/dev/full", "wb") as sink:
            result = subprocess.run(
                [sys.executable, str(TOOL), str(self.first), str(self.second), "--json"],
                stdout=sink,
                stderr=subprocess.PIPE,
                timeout=5,
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertTrue(result.stderr.startswith(b"error: "))
        self.assertNotIn(b"Exception ignored", result.stderr)
        self.assertEqual(before, (self.first.read_bytes(), self.second.read_bytes()))


if __name__ == "__main__":
    unittest.main()
