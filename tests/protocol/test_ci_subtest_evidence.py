# SPDX-License-Identifier: GPL-3.0-only
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from run_ci_tests import summarize


def run_example(tmp_path, program):
    root = Path(__file__).resolve().parents[2]
    example = tmp_path / "test_example.py"
    example.write_text(program)
    xml = tmp_path / "pytest.xml"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-o",
            "addopts=",
            "-p",
            "tools.ci_subtest_evidence",
            "--junitxml",
            str(xml),
            str(example),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return result.returncode, xml, xml.with_suffix(".subtests.json")


@pytest.mark.skipif(
    pytest.version_tuple[0] < 9, reason="requires pytest's built-in subtests fixture"
)
def test_receipt_uses_real_nested_events_and_preserves_native_xml(tmp_path):
    code, xml, evidence = run_example(
        tmp_path,
        """
import pytest

def test_ordinary():
    pass

def test_mixed(subtests):
    with subtests.test(label='same'):
        assert True
    with subtests.test(label='same'):
        pytest.skip('unavailable')
""",
    )
    original = xml.read_bytes()
    report = summarize(xml, code, subtests=evidence)
    assert report["accepted"] and report["counts"] == {
        "tests": 4,
        "passed": 3,
        "skipped": 1,
        "errors": 0,
        "failures": 0,
    }
    assert report["subtest_counts"] == {"passed": 1, "failed": 0, "skipped": 1}
    assert xml.read_bytes() == original
    assert report["junit_sha256"] == hashlib.sha256(original).hexdigest()
    assert report["subtests_sha256"] == hashlib.sha256(evidence.read_bytes()).hexdigest()
    data = json.loads(evidence.read_bytes())
    cases = data["parents"][0]["events"]
    assert [case["ordinal"] for case in cases] == [1, 2]
    assert not summarize(xml, code)["accepted"]
    cases[1]["ordinal"] = cases[0]["ordinal"]
    evidence.write_text(json.dumps(data))
    assert not summarize(xml, code, subtests=evidence)["accepted"]
    cases[1]["ordinal"] = 2
    cases.pop(0)
    evidence.write_text(json.dumps(data))
    assert not summarize(xml, code, subtests=evidence)["accepted"]


@pytest.mark.skipif(
    pytest.version_tuple[0] < 9, reason="requires pytest's built-in subtests fixture"
)
def test_failed_child_and_parent_remain_two_failures_even_with_exit_zero(tmp_path):
    code, xml, evidence = run_example(
        tmp_path,
        """
def test_mixed(subtests):
    for value in (1, 2):
        with subtests.test(value=value):
            assert value == 1
""",
    )
    assert code != 0
    for exit_code in (code, 0):
        report = summarize(xml, exit_code, subtests=evidence)
        assert not report["accepted"]
        assert report["subtest_counts"] == {"passed": 1, "failed": 1, "skipped": 0}
        assert report["counts"] == {
            "tests": 3,
            "passed": 1,
            "skipped": 0,
            "errors": 0,
            "failures": 2,
        }
    data = json.loads(evidence.read_bytes())
    group = data["parents"][0]
    child = group["events"][1]
    assert child["failure_sha256"] != group["parent_failure_sha256"]
    child["failure_sha256"], group["parent_failure_sha256"] = (
        group["parent_failure_sha256"],
        child["failure_sha256"],
    )
    evidence.write_text(json.dumps(data))
    assert summarize(xml, 0, subtests=evidence)["counts"] is None
    data["parents"][0]["events"][1]["outcome"] = "passed"
    evidence.write_text(json.dumps(data))
    assert not summarize(xml, 0, subtests=evidence)["accepted"]


def test_missing_or_mismatched_evidence_fails_closed(tmp_path):
    xml = tmp_path / "pytest.xml"
    xml.write_text('<testsuite tests="1"><testcase classname="m" name="t"/></testsuite>')
    evidence = tmp_path / "pytest.subtests.json"
    assert not summarize(xml, 0, subtests=evidence)["accepted"]
    evidence.write_text(
        json.dumps(
            {
                "schema": "capturesuite.pytest-subtests.v1",
                "junit_sha256": "0" * 64,
                "parents": [],
            }
        )
    )
    assert not summarize(xml, 0, subtests=evidence)["accepted"]
