# SPDX-License-Identifier: GPL-3.0-only
"""Final-state admission against real native package files."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from capture_analysis.qc import collect_qc
from capture_analysis.qc_packages import create_qc_package_review

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mini_session"


def _inventory(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "directory"
        )
        for path in sorted(root.rglob("*"))
    }


@pytest.mark.parametrize(
    "invalid_manifest",
    [None, [], "finalized", {}, {"state": None}, {"state": ["finalized"]}, {"state": "preparing"}],
)
def test_manifest_must_explicitly_declare_a_finalized_state(
    tmp_path: Path, invalid_manifest: object,
) -> None:
    bad = tmp_path / "bad.mmsession"
    good = tmp_path / "good.mmsession"
    shutil.copytree(FIXTURE, bad)
    shutil.copytree(FIXTURE, good)
    (bad / "manifest.json").write_text(json.dumps(invalid_manifest), encoding="utf-8")
    before = {str(package): _inventory(package) for package in (bad, good)}
    expected = collect_qc(good).to_dict()

    review = create_qc_package_review([bad, good], tmp_path / "review")

    assert (review["packageCount"], review["collectedCount"], review["failedCount"]) == (2, 1, 1)
    refused, collected = review["packages"]
    assert refused["status"] == "failed" and refused["qc"] is None
    assert refused["error"]["type"] == "SessionPackageError"
    assert "explicitly" in refused["error"]["message"]
    assert collected["status"] == "collected" and collected["qc"] == expected
    assert before == {str(package): _inventory(package) for package in (bad, good)}


def test_unreadable_manifest_text_does_not_discard_later_native_report(tmp_path: Path) -> None:
    bad = tmp_path / "invalid-utf8.mmsession"
    good = tmp_path / "next.mmsession"
    shutil.copytree(FIXTURE, bad)
    shutil.copytree(FIXTURE, good)
    (bad / "manifest.json").write_bytes(b"\xff\xfe")
    before = {str(package): _inventory(package) for package in (bad, good)}

    review = create_qc_package_review([bad, good], tmp_path / "review")

    assert review["failedCount"] == 1 and review["collectedCount"] == 1
    assert review["packages"][0]["error"]["type"] == "UnicodeDecodeError"
    assert review["packages"][1]["qc"] == collect_qc(good).to_dict()
    assert before == {str(package): _inventory(package) for package in (bad, good)}


def test_recording_labels_distinguish_folders_without_merging_selections(tmp_path):
    from html.parser import HTMLParser
    from capture_analysis.qc_packages import create_qc_package_review

    class RecordingNames(HTMLParser):
        def __init__(self):
            super().__init__()
            self.headings = []
            self.inside = False

        def handle_starttag(self, tag, attrs):
            if tag == "th" and dict(attrs).get("class") == "recording-name":
                self.inside = True
                self.headings.append([])

        def handle_endtag(self, tag):
            if tag == "th":
                self.inside = False

        def handle_data(self, data):
            if self.inside:
                self.headings[-1].append(data)

    first = tmp_path / "site<&" / "day1" / "record.mmsession"
    second = tmp_path / "site-b" / "day1" / "record.mmsession"
    other = tmp_path / "day7" / "record.mmsession"
    unique = tmp_path / "unique.mmsession"
    out = tmp_path / "review"
    create_qc_package_review([first, second, other, first, unique], out)
    html = (out / "index.html").read_text()
    names = RecordingNames()
    names.feed(html)
    assert len(names.headings) == 5
    expected = [first.parent.relative_to(tmp_path), second.parent.relative_to(tmp_path),
                other.parent.name, first.parent.relative_to(tmp_path)]
    for label, folder in zip(names.headings[:4], expected, strict=True):
        assert label[:2] == ["record.mmsession", f"Folder: {folder}"]
    assert names.headings[0] == names.headings[3]
    assert names.headings[4] == ["unique.mmsession", "Could not collect this recording"]
    assert "site&lt;&amp;" in html
