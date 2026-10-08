# SPDX-License-Identifier: GPL-3.0-only
"""Diagnostic output admission against real files and actual CLI processes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from diagnostic_bundle import __main__ as diagnostic


class DiagnosticOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="diagnostic-output-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / "synthetic.mmsession"
        self.package.mkdir()
        (self.package / "manifest.json").write_text(
            json.dumps({"session_id": "synthetic", "participant": {
                "id": "fixture-guid", "name": "Fictional Participant",
            }}), encoding="utf-8",
        )
        self.raw = self.package / "sources" / "sim" / "raw.mcap"
        self.raw.parent.mkdir(parents=True)
        self.raw.write_bytes(b"AUTHORED RAW SENTINEL")
        self.appdata = self.root / "empty-appdata"
        self.appdata.mkdir()
        self.environment = patch.dict(os.environ, {"LOCALAPPDATA": str(self.appdata)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def snapshot(self, path: Path) -> dict:
        return {
            p.relative_to(path).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in path.rglob("*") if p.is_file()
        }

    def refuse(self, output: Path, *, include_raw: bool = False) -> None:
        before = self.snapshot(self.package)
        retained = self.snapshot(self.root)
        with self.assertRaises((ValueError, FileExistsError)):
            diagnostic.build_bundle(self.package, output, include_raw=include_raw)
        self.assertEqual(self.snapshot(self.package), before)
        self.assertEqual(self.snapshot(self.root), retained)

    def cli(self, output: Path, *, cwd: Path | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(
            [sys.executable, "-B", str(Path(diagnostic.__file__).resolve()),
             str(self.package), "--output", str(output)],
            cwd=cwd or self.root, env=env, capture_output=True, timeout=20,
        )

    def assert_cli_refused(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(b"Choose a new output path", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertNotIn(b"Wrote", result.stdout)

    def test_existing_archive_is_preserved(self) -> None:
        output = self.root / "retained.zip"
        output.write_bytes(b"RETAINED ARCHIVE")
        self.refuse(output)

    def test_existing_directory_is_preserved(self) -> None:
        output = self.root / "retained-dir"
        output.mkdir()
        (output / "notes.txt").write_bytes(b"RETAINED NOTES")
        self.refuse(output)

    def test_manifest_cannot_be_replaced(self) -> None:
        self.refuse(self.package / "manifest.json", include_raw=True)

    def test_raw_file_cannot_be_replaced(self) -> None:
        self.refuse(self.raw, include_raw=True)

    def test_new_nested_package_output_is_refused(self) -> None:
        output = self.package / "new" / "nested" / "bundle.zip"
        self.refuse(output)
        self.assertFalse(output.parent.exists())

    def test_package_directory_itself_is_refused(self) -> None:
        self.refuse(self.package)

    def test_fresh_external_output_keeps_inventory_and_redaction(self) -> None:
        before = self.snapshot(self.package)
        output = self.root / "new-parent" / "bundle.zip"
        summary = diagnostic.build_bundle(self.package, output)
        self.assertEqual(summary["included"], ["manifest.json"])
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(set(archive.namelist()), {"manifest.json", "bundle_manifest.json"})
            self.assertEqual(json.loads(archive.read("manifest.json"))["participant"],
                             {"id": "fixture-guid"})
            self.assertEqual(json.loads(archive.read("bundle_manifest.json"))["included"],
                             summary["included"])
        self.assertEqual(self.snapshot(self.package), before)

    def test_explicit_raw_and_identifiers_remain_available(self) -> None:
        before = self.snapshot(self.package)
        output = self.root / "explicit.zip"
        diagnostic.build_bundle(self.package, output, include_raw=True, include_identifiers=True)
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(archive.read("sources/sim/raw.mcap"), b"AUTHORED RAW SENTINEL")
            self.assertEqual(json.loads(archive.read("manifest.json"))["participant"]["name"],
                             "Fictional Participant")
        self.assertEqual(self.snapshot(self.package), before)

    def test_similar_name_sibling_is_outside_package(self) -> None:
        output = self.root / "synthetic.mmsession-backup" / "bundle.zip"
        diagnostic.build_bundle(self.package, output)
        self.assertTrue(zipfile.is_zipfile(output))

    def test_cli_existing_archive_refuses_without_traceback(self) -> None:
        output = self.root / "retained.zip"
        output.write_bytes(b"RETAINED ARCHIVE")
        before = self.snapshot(self.root)
        self.assert_cli_refused(self.cli(output))
        self.assertEqual(self.snapshot(self.root), before)

    def test_cli_relative_package_output_is_refused(self) -> None:
        before = self.snapshot(self.package)
        self.assert_cli_refused(self.cli(Path("new") / "bundle.zip", cwd=self.package))
        self.assertEqual(self.snapshot(self.package), before)
        self.assertFalse((self.package / "new").exists())

    def test_cli_fresh_external_output_succeeds(self) -> None:
        output = self.root / "new.zip"
        before = self.snapshot(self.package)
        result = self.cli(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertIn(b"Wrote", result.stdout)
        self.assertTrue(zipfile.is_zipfile(output))
        self.assertEqual(self.snapshot(self.package), before)

    def test_late_destination_collision_preserves_other_writer(self) -> None:
        output = self.root / "late.zip"
        real_zipfile = zipfile.ZipFile
        before = self.snapshot(self.package)

        def competing_create(path, *args, **kwargs):
            self.assertFalse(Path(path).exists())
            Path(path).write_bytes(b"OTHER WRITER")
            return real_zipfile(path, *args, **kwargs)

        with patch.object(diagnostic.zipfile, "ZipFile", side_effect=competing_create):
            with self.assertRaises(FileExistsError):
                diagnostic.build_bundle(self.package, output)
        self.assertEqual(output.read_bytes(), b"OTHER WRITER")
        self.assertEqual(self.snapshot(self.package), before)

    def test_existing_hard_link_cannot_replace_source(self) -> None:
        output = self.root / "linked.zip"
        os.link(self.raw, output)
        self.assertTrue(output.samefile(self.raw))
        self.refuse(output)

    def test_resolved_directory_alias_into_package_is_refused(self) -> None:
        alias = self.root / "package-alias"
        if os.name == "nt":
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(alias), str(self.package)],
                capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            alias.symlink_to(self.package, target_is_directory=True)
        self.assertTrue(alias.samefile(self.package))
        self.refuse(alias / "new" / "bundle.zip")
        self.assertFalse((self.package / "new").exists())

    def test_dangling_directory_alias_is_occupied(self) -> None:
        alias = self.root / "occupied-output"
        missing = self.root / "missing-target"
        if os.name == "nt":
            result = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(alias), str(missing)],
                capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            alias.symlink_to(missing, target_is_directory=True)
        original_target = os.readlink(alias)
        self.assertFalse(missing.exists())
        self.refuse(alias)
        self.assertEqual(os.readlink(alias), original_target)
        self.assertFalse(missing.exists())

    def test_occupied_output_refuses_before_malformed_source_read(self) -> None:
        (self.package / "manifest.json").write_bytes(b"INVALID JSON")
        output = self.root / "retained.zip"
        output.write_bytes(b"RETAINED")
        with self.assertRaisesRegex(ValueError, "output already exists"):
            diagnostic.build_bundle(self.package, output)
        self.assertEqual(output.read_bytes(), b"RETAINED")


if __name__ == "__main__":
    unittest.main()
