# SPDX-License-Identifier: GPL-3.0-only
"""Fail-closed receipt/parser controls; these are not camera execution evidence."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location(
    "camera_qualification", ROOT / "tools/qualify_camera_ci.py")
camera = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(camera)


def native_xml() -> ET.Element:
    root = ET.Element("Catch2TestRun", {
        "name": "capture_core_tests.exe", "xml-format-version": "3", "catch2-version": "3.10.0",
    })
    for name in camera.TEST_NAMES:
        case = ET.SubElement(root, "TestCase", {"name": name, "tags": "[worker_host][camera]"})
        ET.SubElement(case, "OverallResult", {"success": "true", "skips": "0"})
    ET.SubElement(root, "OverallResults", {
        "successes": "37", "failures": "0", "expectedFailures": "0", "skips": "0",
    })
    ET.SubElement(root, "OverallResultsCases", {
        "successes": "3", "failures": "0", "expectedFailures": "0", "skips": "0",
    })
    return root


def sdk_metadata() -> dict:
    return {
        "schema": "capturesuite.camera-sdk.v1", "accepted": True, "gstreamer_version": "1.24.13",
        "binary_coverage": "all_sdk_dll_and_exe",
        "installers": [
            {"name": name, "url": camera.VENDOR_URL_PREFIX + name,
             "sha256": digest, "expected_sha256": digest, "bytes": 1}
            for name, digest in camera.INSTALLER_PINS.items()
        ],
        "extractions": [{"name": name, "exit_code": 0} for name in camera.INSTALLER_PINS],
        "probe": {"exit_code": 0, "output": "gst-inspect-1.0 version 1.24.13\nGStreamer 1.24.13\n"},
    }


class CameraReceiptControls(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="camera-receipt-unit-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "native.xml"

    def evaluate(self, root=None, code=0):
        self.path.write_bytes(ET.tostring(root if root is not None else native_xml()))
        return camera.evaluate_xml(self.path, code)

    def test_native_case_totals_are_distinct_from_assertion_totals(self):
        result = self.evaluate()
        self.assertTrue(result["accepted"], result["problems"])
        self.assertEqual(result["cases"]["successes"], 3)
        self.assertEqual(result["assertions"]["successes"], 37)
        self.assertEqual(set(result["test_names"]), set(camera.TEST_NAMES))

    def test_zero_or_wrong_camera_selection_is_rejected(self):
        for kind in ("zero", "missing", "duplicate", "substitute", "extra"):
            with self.subTest(kind=kind):
                root = native_xml()
                cases = root.findall("TestCase")
                if kind == "zero":
                    for case in cases:
                        root.remove(case)
                    root.find("OverallResultsCases").set("successes", "0")
                elif kind == "missing":
                    root.remove(cases[-1])
                elif kind == "duplicate":
                    cases[-1].set("name", cases[0].get("name"))
                elif kind == "substitute":
                    cases[-1].set("name", "worker host spawns stub with Hello and Identify")
                else:
                    root.append(copy.deepcopy(cases[0]))
                self.assertFalse(self.evaluate(root)["accepted"])

    def test_nonzero_timeout_and_noninteger_exits_are_rejected(self):
        for code in (1, -1, 3221225781, None, False, 0.0, "0"):
            with self.subTest(code=code):
                self.assertFalse(self.evaluate(code=code)["accepted"])

    def test_per_case_failure_or_skip_cannot_hide_behind_success_totals(self):
        for attribute, value in (("success", "false"), ("skips", "1"), ("skips", "-1")):
            with self.subTest(attribute=attribute, value=value):
                root = native_xml()
                root.find("TestCase/OverallResult").set(attribute, value)
                self.assertFalse(self.evaluate(root)["accepted"])

    def test_failure_exception_and_skip_nodes_are_rejected(self):
        for tag in ("Failure", "Exception", "FatalErrorCondition", "Skip", "Expression"):
            with self.subTest(tag=tag):
                root = native_xml()
                ET.SubElement(root.find("TestCase"), tag, {"success": "false"})
                self.assertFalse(self.evaluate(root)["accepted"])

    def test_failed_expected_failure_and_skipped_totals_are_rejected(self):
        for tag in ("OverallResultsCases", "OverallResults"):
            for attribute in ("failures", "expectedFailures", "skips"):
                with self.subTest(tag=tag, attribute=attribute):
                    root = native_xml()
                    root.find(tag).set(attribute, "1")
                    self.assertFalse(self.evaluate(root)["accepted"])
        root = native_xml()
        root.find("OverallResults").set("successes", "0")
        self.assertFalse(self.evaluate(root)["accepted"])

    def test_missing_duplicate_and_malformed_count_evidence_is_rejected(self):
        for kind in ("missing", "duplicate", "negative", "fraction", "wrong_cases"):
            with self.subTest(kind=kind):
                root = native_xml()
                counts = root.find("OverallResultsCases")
                if kind == "missing":
                    del counts.attrib["skips"]
                elif kind == "duplicate":
                    root.append(copy.deepcopy(counts))
                else:
                    counts.set("successes", {"negative": "-3", "fraction": "3.0",
                                            "wrong_cases": "37"}[kind])
                self.assertFalse(self.evaluate(root)["accepted"])

    def test_truncated_unrelated_and_entity_xml_is_rejected(self):
        for raw in (b"<Catch2TestRun", b"<testsuite tests='3'/>",
                    b"<!DOCTYPE x [<!ENTITY y 'unsafe'>]><Catch2TestRun/>"):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                self.assertFalse(camera.evaluate_xml(self.path, 0)["accepted"])
        self.path.write_bytes(ET.tostring(native_xml()))
        with patch.object(camera, "MAX_XML_BYTES", 16):
            self.assertFalse(camera.evaluate_xml(self.path, 0)["accepted"])

    def test_nested_or_unfinished_case_is_rejected(self):
        root = native_xml()
        root.find("TestCase").remove(root.find("TestCase/OverallResult"))
        self.assertFalse(self.evaluate(root)["accepted"])
        root = native_xml()
        root.find("TestCase").append(copy.deepcopy(root.findall("TestCase")[-1]))
        self.assertFalse(self.evaluate(root)["accepted"])

    def test_sdk_receipt_requires_both_pins_and_successful_extraction_and_probe(self):
        camera.validate_sdk_metadata(sdk_metadata())
        changes = (
            lambda x: x.update(accepted=False),
            lambda x: x.update(gstreamer_version="1.24.12"),
            lambda x: x.pop("binary_coverage"),
            lambda x: x.update(binary_coverage="selected_files"),
            lambda x: x["installers"].pop(),
            lambda x: x["installers"][0].update(expected_sha256="0" * 64),
            lambda x: x["installers"][0].update(sha256="0" * 64),
            lambda x: x["installers"][0].update(bytes=True),
            lambda x: x["installers"][0].update(url="https://example.com/runtime.msi"),
            lambda x: x["installers"][0].update(name="runtime.msi"),
            lambda x: x["installers"][0].update(
                sha256=x["installers"][1]["sha256"],
                expected_sha256=x["installers"][1]["expected_sha256"]),
            lambda x: x["installers"][0].update(url=x["installers"][1]["url"]),
            lambda x: x["installers"][0].update(
                url=x["installers"][0]["url"].replace("/1.24.13/msvc/", "/1.24.12/msvc/")),
            lambda x: x["installers"].__setitem__(0, None),
            lambda x: x["extractions"].__setitem__(0, None),
            lambda x: x["extractions"][0].update(exit_code=1),
            lambda x: x["extractions"][0].update(exit_code=False),
            lambda x: x["probe"].update(exit_code=1),
            lambda x: x["probe"].update(output="GStreamer 1.24.12"),
            lambda x: x["probe"].update(output="GStreamer 1.24.13.1"),
            lambda x: x["probe"].update(output="not GStreamer 1.24.13"),
        )
        for change in changes:
            with self.subTest(change=change):
                value = sdk_metadata()
                change(value)
                with self.assertRaises((ValueError, TypeError, KeyError)):
                    camera.validate_sdk_metadata(value)

    def test_sdk_manifest_binds_logs_and_complete_binary_files(self):
        base = Path(self.directory.name)
        sdk = base / "sdk"
        evidence = base / "evidence"
        unrelated_root = base / "repository"
        evidence.mkdir()
        unrelated_root.mkdir()
        value = sdk_metadata()
        value["gstreamer_root"] = str(sdk)
        value["files"] = []
        for relative in ("include/gstreamer-1.0/gst/gst.h", "lib/gstreamer-1.0.lib",
                         "lib/gstapp-1.0.lib", "lib/gstvideo-1.0.lib",
                         "bin/gst-inspect-1.0.exe", "bin/gst-launch-1.0.exe"):
            path = sdk / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"authored metadata fixture; never executed\n")
            value["files"].append({"path": relative, "bytes": path.stat().st_size,
                                   "sha256": camera.sha256(path)})
        for extraction in value["extractions"]:
            log = evidence / (extraction["name"] + ".extract.log")
            log.write_bytes(b"authored SDK extraction evidence\n")
            extraction.update(log=log.name, log_sha256=camera.sha256(log))
            (unrelated_root / log.name).write_bytes(log.read_bytes())
        manifest = evidence / "manifest.json"

        def inspect():
            manifest.write_text(json.dumps(value), encoding="utf-8")
            return camera.inspect_sdk(manifest)

        with patch.object(camera, "ROOT", unrelated_root), patch.dict(
                os.environ, {"GSTREAMER_1_0_ROOT_MSVC_X86_64": str(sdk)}):
            # The producer's relative basename must resolve beside manifest.json.
            self.assertEqual(inspect()[0], sdk.resolve())
            log = evidence / value["extractions"][0]["log"]
            original = log.read_bytes()
            log.unlink()
            # A same-named, correctly hashed repository file cannot substitute.
            with self.assertRaises(ValueError):
                inspect()
            log.write_bytes(original + b"changed")
            with self.assertRaises(ValueError):
                inspect()
            log.write_bytes(original)
            original_name = value["extractions"][0]["log"]
            for escaped in ("../repository/" + original_name,
                            str(unrelated_root / original_name)):
                with self.subTest(escaped=escaped):
                    value["extractions"][0]["log"] = escaped
                    with self.assertRaises(ValueError):
                        inspect()
            value["extractions"][0]["log"] = original_name
            self.assertEqual(inspect()[0], sdk.resolve())
            # A newly added plugin cannot hide outside the recorded subset.
            plugin = sdk / "lib/gstreamer-1.0/nested/authored-plugin.dll"
            plugin.parent.mkdir(parents=True)
            plugin.write_bytes(b"authored plugin metadata; never executed")
            with self.assertRaises(ValueError):
                inspect()
            value["files"].append({"path": plugin.relative_to(sdk).as_posix(),
                                   "bytes": plugin.stat().st_size,
                                   "sha256": camera.sha256(plugin)})
            self.assertEqual(inspect()[0], sdk.resolve())
            original_plugin = plugin.read_bytes()
            plugin.write_bytes(original_plugin + b"changed")
            with self.assertRaises(ValueError):
                inspect()
            plugin.write_bytes(original_plugin)
            plugin.unlink()
            with self.assertRaises(ValueError):
                inspect()
            value["files"].pop()
            outside = base / "outside"
            outside.mkdir()
            (outside / "omitted.dll").write_bytes(b"authored metadata; never executed")
            link = sdk / "linked-runtime"
            if sys.platform == "win32":
                # Directory junctions need no symbolic-link privilege.
                command = [os.environ["ComSpec"], "/d", "/c", "mklink", "/J",
                           str(link), str(outside)]
                process = subprocess.run(command, capture_output=True, text=True, timeout=10)
                self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            else:
                link.symlink_to(outside, target_is_directory=True)
            try:
                with self.assertRaises(ValueError):
                    inspect()
            finally:
                if sys.platform == "win32":
                    link.rmdir()
                else:
                    link.unlink()
            self.assertEqual(inspect()[0], sdk.resolve())

    def test_pipe_listening_success_is_not_a_client_connection(self):
        self.assertFalse(camera.pipe_connection_observed(True, 0))
        self.assertFalse(camera.pipe_connection_observed(False, 536))
        self.assertTrue(camera.pipe_connection_observed(False, 535))
        self.assertTrue(camera.pipe_connection_observed(False, 232))
        with self.assertRaises(OSError):
            camera.pipe_connection_observed(False, 5)

    def test_invalid_pe_bytes_cannot_supply_binary_identity(self):
        path = Path(self.directory.name) / "invalid-parser-input.bin"
        for raw in (b"not PE", b"MZ" + b"\0" * 62):
            with self.subTest(raw=raw):
                path.write_bytes(raw)
                with self.assertRaises((ValueError, struct.error)):
                    camera.pe_identity(path)
        raw = bytearray(64)
        raw[:2] = b"MZ"
        struct.pack_into("<I", raw, 0x3C, 0xFFFFFFFF)
        path.write_bytes(raw)
        with self.assertRaises(ValueError):
            camera.pe_identity(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
