# SPDX-License-Identifier: GPL-3.0-only
"""Focused standalone report behavior; not the existing reader/Qt campaigns."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

from capture_session.package_reader import GapSummary, ReviewSummary, SessionPackageError
from capture_session.recorded_events_html import render_recorded_events_html

from tools.report_recorded_events import create_report

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "report_recorded_events.py"


class ReportDocument(HTMLParser):
    """Read the generated document as HTML, including decoded literal text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.records: list[tuple[str, str, str]] = []
        self.tags: list[tuple[str, dict]] = []
        self.text: list[str] = []
        self._record: tuple[str, str] | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if tag == "pre" and "data-kind" in attributes:
            self._record = (attributes["data-kind"], attributes["data-index"])
            self._parts = []

    def handle_data(self, data) -> None:
        self.text.append(data)
        if self._record is not None:
            self._parts.append(data)

    def handle_endtag(self, tag) -> None:
        if tag == "pre" and self._record is not None:
            self.records.append((*self._record, "".join(self._parts)))
            self._record = None
            self._parts = []


def document(source: str) -> ReportDocument:
    parsed = ReportDocument()
    parsed.feed(source)
    parsed.close()
    return parsed


def snapshot(root: Path) -> dict:
    return {
        p.relative_to(root).as_posix(): (
            p.read_bytes(),
            p.stat().st_mode,
            p.stat().st_mtime_ns,
        )
        for p in root.rglob("*")
        if p.is_file()
    }


def package_at(root: Path, state: str = "finalized_recovered") -> Path:
    package = root / "fixture.mmsession"
    package.mkdir()
    (package / "events").mkdir()
    (package / "sources" / "sensor-A" / "health").mkdir(parents=True)
    (package / "manifest.json").write_text(
        json.dumps({"sessionId": "fixture-读", "state": state}) + "\n",
        encoding="utf-8",
    )
    (package / "events" / "checkpoints.json").write_text(
        json.dumps(
            [
                {"checkpointId": "later", "timestampNs": "9007199254740997"},
                {"checkpointId": "earlier", "timestampNs": "-23"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (package / "events" / "annotations.json").write_text(
        json.dumps([{"text": "Literal <script> & café", "extra": {"kept": True}}]) + "\n",
        encoding="utf-8",
    )
    (package / "events" / "sync_anchors.json").write_text(
        json.dumps([{"syncAnchorId": "sync-1", "timestampNs": "0"}]) + "\n",
        encoding="utf-8",
    )
    (package / "sources" / "sensor-A" / "health" / "gaps.jsonl").write_text(
        json.dumps(
            {
                "startSessionTimeNs": "-23",
                "endSessionTimeNs": "9007199254740997",
                "closed": False,
                "estimatedLostCount": "9007199254740999",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return package


class RecordedEventsReportTests(unittest.TestCase):
    def test_full_literal_records_and_reader_order_survive_html(self) -> None:
        checkpoints = [
            {"id": "later", "timestampNs": "9007199254740997", "extra": [False, None]},
            {"id": "earlier", "timestampNs": -23, "structured": {"label": "Café — 左"}},
            {"id": "duplicate", "timestampNs": -23},
        ]
        annotations = [{"text": '</pre><script>alert("literal")</script>&', "future": {"a": 1}}]
        anchors = [{"timestampNs": "0", "mechanism": "manual", "unknown": [1, "two"]}]
        summary = ReviewSummary(
            "literal <package>", "ID & notes", "finalized",
            checkpoints=checkpoints, annotations=annotations, sync_anchors=anchors,
        )
        before = copy.deepcopy(summary)
        parsed = document(render_recorded_events_html(summary))
        self.assertEqual(summary, before)
        self.assertEqual(
            [(kind, index, json.loads(raw)) for kind, index, raw in parsed.records],
            [
                *[("checkpoints", str(i), row) for i, row in enumerate(checkpoints)],
                ("annotations", "0", annotations[0]),
                ("sync-anchors", "0", anchors[0]),
            ],
        )
        self.assertNotIn("script", [tag for tag, _ in parsed.tags])
        self.assertTrue(all("src" not in attrs for _, attrs in parsed.tags))
        self.assertTrue(
            all(attrs["href"].startswith("#") for _, attrs in parsed.tags if "href" in attrs)
        )

    def test_gap_projection_keeps_integer_null_and_closure_independent(self) -> None:
        gaps = [
            GapSummary("A", "stream", "unknown", -23, 9007199254740997, False, 9007199254740999),
            GapSummary("B", "", "unknown", 0, None, True, 0),
        ]
        summary = ReviewSummary("p", "s", "finalized", gaps=gaps)
        parsed = document(render_recorded_events_html(summary))
        self.assertEqual(
            [json.loads(raw) for kind, _, raw in parsed.records if kind == "gaps"],
            [
                {
                    "source_id": "A", "stream_id": "stream", "cause": "unknown",
                    "start_session_time_ns": -23, "end_session_time_ns": 9007199254740997,
                    "closed": False, "estimated_lost_count": 9007199254740999,
                },
                {
                    "source_id": "B", "stream_id": "", "cause": "unknown",
                    "start_session_time_ns": 0, "end_session_time_ns": None,
                    "closed": True, "estimated_lost_count": 0,
                },
            ],
        )
        self.assertIn("not copies of the original gap JSON", "".join(parsed.text))

    def test_empty_and_recovered_report_keeps_omission_limits_visible(self) -> None:
        parsed = document(
            render_recorded_events_html(ReviewSummary("p", "s", "finalized_recovered"))
        )
        text = "".join(parsed.text)
        self.assertEqual(parsed.records, [])
        self.assertIn("Recovered session", text)
        self.assertIn("Returned counts do not establish a complete or repaired capture", text)
        self.assertIn("filtered nonobject entries may be omitted", text)
        self.assertIn("not an atomic filesystem snapshot", text)
        for kind in ("checkpoint", "annotation", "sync", "normalized gap"):
            self.assertIn(f"No {kind} records were returned", text)

    def test_escaped_surrogate_is_kept_without_invalid_utf8(self) -> None:
        literal = {"text": "\ud800", "unicode": "Café 🙂"}
        summary = ReviewSummary("p", "s", "finalized", annotations=[literal])
        source = render_recorded_events_html(summary)
        self.assertEqual(source.encode("utf-8").decode("utf-8"), source)
        parsed = document(source)
        self.assertEqual(json.loads(parsed.records[0][2]), literal)

    def test_actual_cli_creates_physical_file_and_preserves_package(self) -> None:
        with tempfile.TemporaryDirectory(prefix="events-cli-") as directory:
            work = Path(directory)
            package = package_at(work)
            before = snapshot(package)
            output = work / "events.html"
            result = subprocess.run(
                [sys.executable, "-I", "-B", str(CLI), str(package), str(output)],
                cwd=work,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            receipt = json.loads(result.stdout)
            actual = output.read_bytes()
            self.assertEqual(receipt["status"], "written")
            self.assertEqual(receipt["bytes"], len(actual))
            self.assertEqual(receipt["sha256"], hashlib.sha256(actual).hexdigest())
            self.assertEqual(
                receipt["records_returned"],
                {"checkpoints": 2, "annotations": 1, "sync_anchors": 1, "normalized_gaps": 1},
            )
            self.assertEqual(len(document(actual.decode("utf-8")).records), 5)
            self.assertEqual(snapshot(package), before)

    def test_existing_destination_and_inside_package_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory(prefix="events-output-") as directory:
            work = Path(directory)
            package = package_at(work)
            output = work / "retained.html"
            output.write_bytes(b"retained report\x00")
            before = snapshot(work)
            with self.assertRaises(FileExistsError):
                create_report(package, output)
            self.assertEqual(snapshot(work), before)
            with self.assertRaisesRegex(ValueError, "outside the original package"):
                create_report(package, package / "report.html")
            self.assertEqual(snapshot(work), before)

    def test_qualified_reader_error_prevents_any_report_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="events-reader-error-") as directory:
            work = Path(directory)
            package = package_at(work)
            gap = package / "sources" / "sensor-A" / "health" / "gaps.jsonl"
            gap.write_text("\nnot-json\n", encoding="utf-8")
            before = snapshot(package)
            output = work / "absent.html"
            with self.assertRaises(SessionPackageError) as raised:
                create_report(package, output)
            self.assertIn(str(gap), str(raised.exception))
            self.assertIn("line 2", str(raised.exception))
            self.assertFalse(output.exists())
            self.assertEqual(snapshot(package), before)

    def test_nonfinalized_state_is_a_visible_refusal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="events-state-") as directory:
            work = Path(directory)
            package = package_at(work, state="recording")
            before = snapshot(package)
            output = work / "absent.html"
            with self.assertRaisesRegex(ValueError, "finalized or finalized_recovered"):
                create_report(package, output)
            self.assertFalse(output.exists())
            self.assertEqual(snapshot(package), before)


if __name__ == "__main__":
    unittest.main()
