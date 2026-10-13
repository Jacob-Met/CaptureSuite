# SPDX-License-Identifier: GPL-3.0-only
"""Saved-byte and real-file controls for the standalone QC comparison view."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import view_qc_comparison as view  # noqa: E402

SOURCE_NAMES = ("view_qc_comparison.py", "compare_qc_reports.py", "qc_comparison.html")


def fixture(**extra):
    document = {
        "schemaId": "capture.analysis_qc/2",
        "packagePath": "fictional <b> Ω\\session\n",
        "sessionId": "session Ω", "packageState": "finalized",
        "manifestSha256": "a" * 64, "durationNs": 0, "sourceCount": 0,
        "streamCount": 0, "openGapCount": 0, "closedGapCount": 0,
        "checkpointCount": 0, "annotationCount": 0, "syncAnchorCount": 0,
        "integrityFileCount": 0, "recoveryReports": [], "streams": [],
        "warnings": [], "trafficLights": {}, "gaps": [],
    }
    document.update(extra)
    return document


def raw(document):
    return (json.dumps(document, ensure_ascii=True) + "\n").encode("ascii")


def model(html):
    encoded = re.search(
        r'<script id="qc-data" type="application/octet-stream">([A-Za-z0-9+/=]+)</script>',
        html,
    ).group(1)
    return json.loads(base64.b64decode(encoded, validate=True))


def snapshot(root):
    return {
        str(p.relative_to(root)): (
            stat.S_IMODE(p.stat().st_mode),
            "directory" if p.is_dir() else hashlib.sha256(p.read_bytes()).hexdigest(),
        )
        for p in root.rglob("*")
    }


class SavedComparisonViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="saved qc view Ω ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for name in SOURCE_NAMES:
            shutil.copyfile(TOOLS / name, self.source / name)
        self.first = self.root / "before Ω.json"
        self.second = self.root / "after.json"
        self.first.write_bytes(raw(fixture()))
        self.second.write_bytes(raw(fixture(warnings=["recorded warning"])))
        self.output = self.root / "review.html"

    def cli(self, *args, stderr=subprocess.PIPE):
        env = os.environ.copy()
        for name in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX", "PYTHONPATH"):
            env.pop(name, None)
        return subprocess.run(
            [sys.executable, str(self.source / "view_qc_comparison.py"), *map(str, args)],
            stdout=subprocess.PIPE, stderr=stderr, cwd=self.root, env=env, timeout=10,
        )

    def test_exact_captures_full_comparison_and_literal_names(self):
        a = self.first.read_bytes()
        b = self.second.read_bytes()
        name = '</script><b>Ω\n@@DATA_BASE64@@'
        html = view.render_comparison_html(a, b, first_name=name)
        data = model(html)
        self.assertNotIn(name, html)
        self.assertEqual(data["captures"]["first"]["name"], view._literal(name))
        self.assertEqual(base64.b64decode(data["captures"]["first"]["base64"]), a)
        self.assertEqual(base64.b64decode(data["captures"]["second"]["base64"]), b)
        self.assertEqual(
            base64.b64decode(data["comparisonBase64"]),
            (view._literal(view.compare_bytes(a, b)) + "\n").encode("ascii"),
        )
        self.assertEqual(data["captures"]["first"]["sha256"], hashlib.sha256(a).hexdigest())
        self.assertEqual(data["captures"]["first"]["bytes"], str(len(a)))
        self.assertEqual(data["captures"]["first"]["session"], '"session \\u03a9"')

    def test_types_presence_large_integer_and_signed_zero_are_text(self):
        a = raw(fixture(extension={"a": False, "b": 1, "c": -0.0,
                                  "d": 9007199254740993, "gone": None}))
        b = raw(fixture(extension={"a": 0, "b": 1.0, "c": 0.0,
                                  "d": 9007199254740994, "new": None}))
        rows = {r["pointer"]: r for r in model(view.render_comparison_html(a, b))["rows"]}
        expected = {
            "a": ("boolean", "false", "integer", "0"),
            "b": ("integer", "1", "float", "1.0"),
            "c": ("float", "-0.0", "float", "0.0"),
            "d": ("integer", "9007199254740993", "integer", "9007199254740994"),
            "gone": ("null", "null", "absent", "(absent)"),
            "new": ("absent", "(absent)", "null", "null"),
        }
        for key, values in expected.items():
            row = rows["/extension/" + key]
            self.assertEqual(
                (row["before"]["type"], row["before"]["text"],
                 row["after"]["type"], row["after"]["text"]), values,
            )
        self.assertEqual(rows["/extension/gone"]["kind"], "removed")
        self.assertEqual(rows["/extension/new"]["kind"], "added")
        self.assertFalse(rows["/extension/new"]["before"]["present"])

    def test_equal_format_only_reports_keep_distinct_raw_hashes(self):
        a = raw(fixture())
        b = json.dumps(fixture(), separators=(",", ":")).encode()
        data = model(view.render_comparison_html(a, b))
        self.assertTrue(data["equal"])
        self.assertEqual(data["rows"], [])
        self.assertNotEqual(data["captures"]["first"]["sha256"],
                            data["captures"]["second"]["sha256"])

    def test_complete_admission_precedes_template_read(self):
        good = self.first.read_bytes()
        bads = [b"{", b'{"schemaId":"capture.analysis_qc/2","schemaId":"x"}',
                raw(fixture(streams=[{}])), raw(fixture(extension=float("inf")))]
        with patch.object(Path, "read_text", side_effect=AssertionError("template read")):
            for bad in bads:
                with self.subTest(bad=bad[:50]):
                    with self.assertRaises(view.ComparisonError):
                        view.render_comparison_html(good, bad)

    def test_name_template_and_output_bounds(self):
        good = self.first.read_bytes()
        for name in (None, "x" * 4097):
            with self.assertRaises(view.ComparisonError):
                view.render_comparison_html(good, good, first_name=name)
        with patch.object(view, "MAX_HTML_BYTES", 10):
            with self.assertRaisesRegex(view.ComparisonError, "64 MiB"):
                view.render_comparison_html(good, good)
        with patch.object(Path, "read_text", return_value="missing data marker"):
            with self.assertRaisesRegex(view.ComparisonError, "exactly one"):
                view.render_comparison_html(good, good)

    def test_ordinary_cli_success_preserves_source_and_inputs(self):
        source_before = snapshot(self.source)
        first, second = self.first.read_bytes(), self.second.read_bytes()
        result = self.cli(self.first, self.second, "--output", self.output)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        data = model(self.output.read_text())
        self.assertEqual(data["captures"]["first"]["downloadName"], self.first.name)
        self.assertEqual(self.first.read_bytes(), first)
        self.assertEqual(self.second.read_bytes(), second)
        self.assertEqual(snapshot(self.source), source_before)
        self.assertEqual(list(self.root.glob(".qc-review-*")), [])
        self.assertEqual(
            self.output.read_bytes(),
            view.render_comparison_html(first, second, first_name=self.first.name,
                                        second_name=self.second.name).encode(),
        )

    def test_actual_cli_refuses_occupied_and_alias_destinations(self):
        self.output.write_bytes(b"retained")
        destinations = [self.output, self.first]
        hardlink = self.root / "hardlink"
        os.link(self.first, hardlink)
        destinations.append(hardlink)
        if hasattr(os, "symlink"):
            link = self.root / "dangling"
            link.symlink_to("missing")
            destinations.append(link)
        original = self.first.read_bytes()
        for destination in destinations:
            result = self.cli(self.first, self.second, "--output", destination)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(self.first.read_bytes(), original)
            self.assertEqual(self.output.read_bytes(), b"retained")
        self.assertEqual(list(self.root.glob(".qc-review-*")), [])

    def test_actual_cli_bad_missing_directory_and_oversize_inputs(self):
        bad = self.root / "bad.json"
        bad.write_bytes(b"{")
        huge = self.root / "huge.json"
        huge.write_bytes(b" " * (view.MAX_INPUT_BYTES + 1))
        for selected in (bad, self.root / "missing", self.source, huge):
            result = self.cli(self.first, selected, "--output", self.output)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stdout, b"")
            self.assertFalse(self.output.exists())
        result = self.cli(self.first, self.second, "--output", self.root / "absent/report.html")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "absent").exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO receiving")
    def test_fifo_refusal_does_not_wait_for_writer(self):
        fifo = self.root / "input.fifo"
        os.mkfifo(fifo)
        result = self.cli(fifo, self.second, "--output", self.output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

    def test_publication_failures_and_arriving_destination(self):
        for operation in ("fsync", "link"):
            with self.subTest(operation=operation):
                with patch.object(view.os, operation, side_effect=OSError("owned refusal")):
                    with self.assertRaises(OSError):
                        view._publish_new(self.output, b"complete body")
                self.assertFalse(self.output.exists())
                self.assertEqual(list(self.root.glob(".qc-review-*")), [])
        real_link = os.link

        def arriving(stage, destination):
            Path(destination).write_bytes(b"arrived independently")
            return real_link(stage, destination)

        with patch.object(view.os, "link", side_effect=arriving):
            with self.assertRaises(FileExistsError):
                view._publish_new(self.output, b"complete body")
        self.assertEqual(self.output.read_bytes(), b"arrived independently")
        self.assertEqual(list(self.root.glob(".qc-review-*")), [])

    def test_postpublication_cleanup_failure_is_explicit(self):
        real_unlink = Path.unlink

        def refuse_stage(path, *args, **kwargs):
            if path.name.startswith(".qc-review-"):
                raise OSError("owned cleanup refusal")
            return real_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", refuse_stage):
            with self.assertRaisesRegex(OSError, "complete output was published"):
                view._publish_new(self.output, b"complete body")
        self.assertEqual(self.output.read_bytes(), b"complete body")
        self.assertEqual(len(list(self.root.glob(".qc-review-*"))), 1)

    def test_api_import_restores_caller_policy(self):
        for flag in (False, True):
            with tempfile.TemporaryDirectory(dir=self.root) as owned:
                source = Path(owned)
                for name in SOURCE_NAMES:
                    shutil.copyfile(TOOLS / name, source / name)
                probe = (
                    "import sys,pathlib,importlib.util,json\n"
                    "sys.path.insert(0,sys.argv[1])\n"
                    "sys.dont_write_bytecode=json.loads(sys.argv[2])\n"
                    "import view_qc_comparison\n"
                    "print(json.dumps({'flag':sys.dont_write_bytecode,'dependency':"
                    "pathlib.Path(importlib.util.cache_from_source(str(pathlib.Path(sys.argv[1])"
                    "/'compare_qc_reports.py'))).exists()}))\n"
                )
                result = subprocess.run(
                    [sys.executable, "-E", "-s", "-c", probe, str(source), json.dumps(flag)],
                    capture_output=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {"flag": flag, "dependency": False})

    def test_unavailable_diagnostic_stream_keeps_failure_status(self):
        with patch.object(view.sys, "stderr", None):
            self.assertEqual(view.main([str(self.first), "missing", "--output",
                                        str(self.output)]), 2)
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            result = self.cli(self.first, "missing", "--output", self.output, stderr=write_fd)
        finally:
            os.close(write_fd)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
