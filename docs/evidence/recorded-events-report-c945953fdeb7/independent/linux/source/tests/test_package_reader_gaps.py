# SPDX-License-Identifier: GPL-3.0-only
"""Gap reader regressions with explicit read-only in-memory package I/O.

These tests execute load_review_summary and its actual JSON/error handling.
Only the reader module's Path binding is adapted. They do not qualify physical
filesystem behavior, the package initializer, or desktop presentation.
"""

from __future__ import annotations

import json
import unittest
from dataclasses import asdict
from pathlib import PurePosixPath
from types import MappingProxyType
from unittest.mock import patch

from capture_session import package_reader as reader

ROOT = "/fixtures/review-读.mmsession"
GAP_PATH = "sources/sensor-α/health/gaps.jsonl"
CAMEL_ROW = {
    "sourceId": "named-β",
    "streamId": "stream-A",
    "cause": "GAP_CAUSE_DISCONNECT",
    "startSessionTimeNs": "0",
    "endSessionTimeNs": "9007199254740997",
    "estimatedLostCount": "9007199254740999",
    "closed": True,
    "futureField": {"kept": "uninterpreted"},
}
SNAKE_ROW = {
    "stream_id": "stream-B",
    "cause": "UNKNOWN",
    "start_session_time_ns": -23,
    "end_session_time_ns": None,
    "estimated_lost_count": 3,
}


def _json(row):
    return json.dumps(row, ensure_ascii=False, separators=(",", ":"))


class _MemoryPath:
    """Only the read-only Path operations reached by these package fixtures."""

    def __init__(self, files, path):
        self._files = files
        self._path = PurePosixPath(str(path))

    def __str__(self):
        return str(self._path)

    def __truediv__(self, part):
        return _MemoryPath(self._files, self._path / part)

    def __lt__(self, other):
        return str(self) < str(other)

    @property
    def name(self):
        return self._path.name

    @property
    def stem(self):
        return self._path.stem

    def is_file(self):
        return str(self) in self._files

    def is_dir(self):
        prefix = str(self) + "/"
        return any(name.startswith(prefix) for name in self._files)

    def read_text(self, *, encoding):
        if encoding != "utf-8":
            raise AssertionError(f"unexpected fixture encoding: {encoding}")
        return self._files[str(self)]

    def iterdir(self):
        prefix = str(self) + "/"
        children = {
            name[len(prefix):].split("/", 1)[0]
            for name in self._files
            if name.startswith(prefix)
        }
        return iter(self / name for name in sorted(children))


class PackageReaderGapTests(unittest.TestCase):
    def _summary(self, text):
        files = {
            ROOT + "/manifest.json": json.dumps(
                {"sessionId": "review-读", "state": "finalized_recovered"},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        }
        if text is not None:
            files[ROOT + "/" + GAP_PATH] = text
        before = dict(files)
        readonly = MappingProxyType(files)
        try:
            with patch.object(reader, "Path", lambda path: _MemoryPath(readonly, path)):
                summary = reader.load_review_summary(ROOT)
        finally:
            self.assertEqual(files, before, "package fixture text changed")
        self.assertEqual(summary.session_id, "review-读")
        self.assertEqual(summary.state, "finalized_recovered")
        return summary

    def _assert_empty(self, text):
        summary = self._summary(text)
        self.assertEqual(summary.gaps, [])
        self.assertEqual(summary.open_gap_count, 0)
        self.assertEqual(summary.closed_gap_count, 0)
        self.assertEqual(summary.duration_ns, 0)

    def _assert_error(self, text, line, reason):
        with self.assertRaises(reader.SessionPackageError) as raised:
            self._summary(text)
        message = str(raised.exception)
        self.assertIn(ROOT + "/" + GAP_PATH, message)
        self.assertIn(f"line {line}", message)
        self.assertIn(reason, message)

    def test_missing_optional(self):
        self._assert_empty(None)

    def test_empty_optional(self):
        self._assert_empty("")

    def test_blank_lines(self):
        self._assert_empty(" \r\n\t\n\n")

    def test_valid_supported_rows(self):
        text = "\n".join(_json(row) for row in (CAMEL_ROW, SNAKE_ROW, {})) + "\n"
        summary = self._summary(text)
        self.assertEqual(
            [asdict(row) for row in summary.gaps],
            [
                {
                    "source_id": "named-β",
                    "stream_id": "stream-A",
                    "cause": "GAP_CAUSE_DISCONNECT",
                    "start_session_time_ns": 0,
                    "end_session_time_ns": 9007199254740997,
                    "closed": True,
                    "estimated_lost_count": 9007199254740999,
                },
                {
                    "source_id": "sensor-α",
                    "stream_id": "stream-B",
                    "cause": "UNKNOWN",
                    "start_session_time_ns": -23,
                    "end_session_time_ns": None,
                    "closed": False,
                    "estimated_lost_count": 3,
                },
                {
                    "source_id": "sensor-α",
                    "stream_id": "",
                    "cause": "unknown",
                    "start_session_time_ns": 0,
                    "end_session_time_ns": None,
                    "closed": False,
                    "estimated_lost_count": 0,
                },
            ],
        )
        self.assertEqual(summary.open_gap_count, 2)
        self.assertEqual(summary.closed_gap_count, 1)
        self.assertEqual(summary.duration_ns, 9007199254740997)

    def test_malformed_middle(self):
        text = "\n" + _json(CAMEL_ROW) + "\n \nnot-json\n" + _json(SNAKE_ROW) + "\n"
        self._assert_error(text, 4, "invalid JSON")

    def test_truncated_tail(self):
        text = _json(CAMEL_ROW) + '\n{"cause":"UNKNOWN"'
        self._assert_error(text, 2, "invalid JSON")

    def test_nonobject_null(self):
        self._assert_error("\nnull\n", 2, "expected JSON object")

    def test_nonobject_array(self):
        self._assert_error("\n[]\n", 2, "expected JSON object")

    def test_nonobject_number(self):
        self._assert_error("\n7\n", 2, "expected JSON object")

    def test_nonobject_boolean(self):
        self._assert_error("\ntrue\n", 2, "expected JSON object")

    def test_nonobject_string(self):
        self._assert_error('\n"text"\n', 2, "expected JSON object")


if __name__ == "__main__":
    unittest.main()
