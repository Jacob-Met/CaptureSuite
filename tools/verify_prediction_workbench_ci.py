#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Read the ordinary Windows JUnit and require actual workbench consumer cases."""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    receipts = list((ROOT / "build/evidence").glob("python-*/receipt.json"))
    assert len(receipts) == 1, "Expected one fresh ordinary test receipt"
    receipt_path = receipts[0]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    xml_path = receipt_path.with_name("pytest.xml")
    raw = xml_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == receipt["junit_sha256"], "JUnit changed after the ordinary gate"
    cases = [
        case for case in ET.fromstring(raw).iter("testcase")
        if case.get("classname") == "tests.ui.test_analysis_predictions"
    ]
    results = [
        {"name": case.get("name"), "xml": ET.tostring(case, encoding="unicode")}
        for case in cases
    ]
    print(json.dumps({
        "source_commit": receipt["source_commit"],
        "source_tree_sha256": receipt["source_tree_sha256"],
        "junit_sha256": digest,
        "junit_bytes": len(raw),
        "workbench_cases": results,
    }, indent=2))
    assert receipt["accepted"] and receipt["process_exit"] == 0
    assert receipt["source_unchanged_during_test"]
    required = (
        "test_evaluation_controls_in_actual_minimum_main_window",
        "test_actual_qt_file_choice_cancel_and_reselection",
        "test_actual_qt_file_choice_error_unwinds_without_replacing_path",
        "test_analysis_button_space_overrides_only_its_application_shortcut",
    )
    for name in required:
        matching = [case for case in cases if case.get("name") == name]
        assert len(matching) == 1, f"Expected exactly one actual case: {name}"
        assert not any(
            matching[0].find(tag) is not None
            for tag in ("skipped", "failure", "error")
        ), f"Required Windows case did not pass: {name}"


if __name__ == "__main__":
    main()
