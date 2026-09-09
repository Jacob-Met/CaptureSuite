# SPDX-License-Identifier: GPL-3.0-only
import xml.etree.ElementTree as ET
from pathlib import Path

import run_native_ci_tests as native


def write_junit(path: Path, *, skipped: int = 0, failed: int = 0):
    suite = ET.Element(
        "testsuite",
        tests="2",
        failures=str(failed),
        errors="0",
        skipped=str(skipped),
    )
    for index in range(2):
        case = ET.SubElement(suite, "testcase", name=f"case-{index}")
        if index < skipped:
            ET.SubElement(case, "skipped")
        elif index < skipped + failed:
            ET.SubElement(case, "failure")
    path.write_bytes(ET.tostring(suite, encoding="utf-8", xml_declaration=True))


def test_zero_skip_success_is_accepted(tmp_path):
    junit = tmp_path / "pytest.xml"
    write_junit(junit)
    report = native.evaluate(junit, 0)
    assert report["accepted"] is True
    assert report["counts"] == {"tests": 2, "passed": 2, "failures": 0, "errors": 0, "skipped": 0}


def test_skipped_native_test_is_rejected(tmp_path):
    junit = tmp_path / "pytest.xml"
    write_junit(junit, skipped=1)
    report = native.evaluate(junit, 0)
    assert report["accepted"] is False
    assert "Native integration tests were skipped" in report["problems"]


def test_nonzero_process_exit_is_rejected_even_with_clean_junit(tmp_path):
    junit = tmp_path / "pytest.xml"
    write_junit(junit)
    assert native.evaluate(junit, 7)["accepted"] is False


def test_build_must_be_explicit_and_inside_repo(tmp_path):
    assert native.resolve_build(tmp_path, None)[1]
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    assert native.resolve_build(tmp_path, str(outside))[1]


def test_changed_binary_bytes_change_receipt_hash(tmp_path):
    build = tmp_path / "build"
    for rel in native.REQUIRED_BINARIES:
        path = build / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"first")
    first, errors = native.inspect_binaries(build)
    assert errors == []
    target = build / native.REQUIRED_BINARIES[0]
    target.write_bytes(b"second")
    second, errors = native.inspect_binaries(build)
    assert errors == []
    assert first[0]["sha256"] != second[0]["sha256"]


def test_missing_binary_is_rejected(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    records, errors = native.inspect_binaries(build)
    assert records == []
    assert len(errors) == len(native.REQUIRED_BINARIES)


def test_native_scope_is_explicit_core_sim_and_recovery():
    assert len(native.NATIVE_TESTS) == 6
    assert len(set(native.NATIVE_TESTS)) == len(native.NATIVE_TESTS)
    assert any("kill_preserves_sealed_segment" in node for node in native.NATIVE_TESTS)
    assert not any("camera_apply_config" in node for node in native.NATIVE_TESTS)
    assert all(node.startswith("tests/") and "::test_" in node for node in native.NATIVE_TESTS)
