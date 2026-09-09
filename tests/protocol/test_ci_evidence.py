# SPDX-License-Identifier: GPL-3.0-only
import hashlib

import pytest
from run_ci_tests import summarize


def evidence(tmp_path, cases, *, tests=None, skipped=0, failures=0, errors=0):
    path = tmp_path / "pytest.xml"
    n = len(cases) if tests is None else tests
    path.write_text(
        f'<testsuites><testsuite tests="{n}" failures="{failures}" '
        f'errors="{errors}" skipped="{skipped}">' + "".join(cases) + "</testsuite></testsuites>"
    )
    return path


def test_success_needs_process_and_test_evidence(tmp_path):
    p = evidence(tmp_path, ['<testcase name="good"/>'])
    result = summarize(p, 0)
    assert result["accepted"]
    assert result["counts"] == dict(tests=1, passed=1, failures=0, errors=0, skipped=0)
    assert result["junit_sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.parametrize("exit_code", [1, 3221226356, None, False, "0"])
def test_native_crash_never_becomes_a_pass(tmp_path, exit_code):
    p = evidence(tmp_path, ['<testcase name="passed_before_crash"/>'])
    assert not summarize(p, exit_code)["accepted"]


def test_missing_junit_is_not_zero_failures(tmp_path):
    result = summarize(tmp_path / "missing.xml", 0)
    assert not result["accepted"] and result["counts"] is None


def test_empty_suite_is_not_success(tmp_path):
    assert not summarize(evidence(tmp_path, []), 0)["accepted"]


def test_skips_are_separate_and_reject_everything_does_not_pass(tmp_path):
    case = '<testcase name="not_run"><skipped/></testcase>'
    r = summarize(evidence(tmp_path, [case], skipped=1), 0)
    assert r["counts"]["skipped"] == 1 and not r["accepted"]
    p = evidence(tmp_path, [case, '<testcase name="ran"/>'], skipped=1)
    assert summarize(p, 0)["accepted"]


@pytest.mark.parametrize("tag,key", [("failure", "failures"), ("error", "errors")])
def test_failing_case_overrides_success_exit(tmp_path, tag, key):
    p = evidence(tmp_path, [f'<testcase name="bad"><{tag}/></testcase>'], **{key: 1})
    assert not summarize(p, 0)["accepted"]


def test_summary_cannot_claim_more_cases_than_exist(tmp_path):
    p = evidence(tmp_path, ['<testcase name="one"/>'], tests=100)
    assert not summarize(p, 0)["accepted"]


@pytest.mark.parametrize(
    "raw", [b"not xml", b"<report/>", b'<!DOCTYPE testsuite [<!ENTITY x "x">]><testsuite/>']
)
def test_unsupported_xml_is_rejected(tmp_path, raw):
    p = tmp_path / "bad.xml"
    p.write_bytes(raw)
    assert not summarize(p, 0)["accepted"]


def test_oversized_input_is_bounded(tmp_path, monkeypatch):
    import run_ci_tests

    monkeypatch.setattr(run_ci_tests, "MAX_XML_BYTES", 8)
    p = tmp_path / "large.xml"
    p.write_bytes(b"x" * 9)
    assert not summarize(p, 0)["accepted"]


def test_single_ctest_style_suite_and_input_immutability(tmp_path):
    p = tmp_path / "ctest.xml"
    raw = b'<testsuite tests="1"><testcase name="test"/></testsuite>'
    p.write_bytes(raw)
    assert summarize(p, 0)["accepted"]
    assert p.read_bytes() == raw


def test_unsupported_encoding_cannot_hide_entity_declarations(tmp_path):
    p = tmp_path / "utf16.xml"
    p.write_bytes('<!DOCTYPE testsuite [<!ENTITY x "x">]><testsuite/>'.encode("utf-16"))
    assert not summarize(p, 0)["accepted"]


@pytest.fixture
def tiny_repo(tmp_path):
    import subprocess

    for args in [
        ["init", "-q"],
        ["config", "user.name", "Synthetic Test"],
        ["config", "user.email", "synthetic@example.invalid"],
    ]:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "input.txt").write_text("original")
    subprocess.run(["git", "add", "input.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "synthetic fixture"], cwd=tmp_path, check=True)
    return tmp_path


def test_dirty_source_is_not_mislabeled_as_the_head_commit(tiny_repo):
    from run_ci_tests import source_snapshot

    before = source_snapshot(tiny_repo)
    (tiny_repo / "input.txt").write_text("changed input")
    after = source_snapshot(tiny_repo)
    assert before["commit"] == after["commit"]
    assert not before["worktree_dirty"] and after["worktree_dirty"]
    assert before["tree_sha256"] != after["tree_sha256"]


def test_snapshot_includes_new_and_deleted_source(tiny_repo):
    from run_ci_tests import source_snapshot

    (tiny_repo / "input.txt").unlink()
    (tiny_repo / "new.txt").write_text("new input")
    snapshot = source_snapshot(tiny_repo)
    assert snapshot["files"]["input.txt"] is None
    assert snapshot["files"]["new.txt"] == hashlib.sha256(b"new input").hexdigest()
    assert source_snapshot(tiny_repo) == snapshot


def test_github_context_is_allowlisted_and_absence_is_explicitly_empty():
    from run_ci_tests import github_context

    assert github_context({}) == {}
    context = github_context(
        {
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_SHA": "merge-sha",
            "GITHUB_HEAD_REF": "candidate",
            "GITHUB_BASE_REF": "main",
            "GITHUB_TOKEN": "must-not-be-copied",
            "UNRELATED": "private",
        }
    )
    assert context == {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_SHA": "merge-sha",
        "GITHUB_HEAD_REF": "candidate",
        "GITHUB_BASE_REF": "main",
    }
