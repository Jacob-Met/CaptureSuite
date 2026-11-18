# SPDX-License-Identifier: GPL-3.0-only
"""Check the operator-visible evidence against a real partially timed recording."""

import json
from html.parser import HTMLParser

from capture_analysis.qc_packages import create_qc_package_review

from tests.analysis.test_payload_inspection_qc import _package, _write_batched_mcap


class CountLists(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lists = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "dl" and dict(attrs).get("class") == "observed-counts":
            self.current = []
            self.lists.append(self.current)

    def handle_data(self, data):
        if self.current is not None and data.strip():
            self.current.append(data.strip())

    def handle_endtag(self, tag):
        if tag == "dl":
            self.current = None


def test_decoded_counts_belong_to_the_stream_and_missing_clocks_stay_explicit(tmp_path):
    package = _package(tmp_path / "source")
    (package / "integrity.json").write_text(
        json.dumps({"files": [{"endSessionTimeNs": 19_000_000_000}]})
    )
    _write_batched_mcap(
        package,
        batches=[list(range(15)), list(range(6))],
        untimed_batch_indices=frozenset({1}),
    )
    expected = [
        "Sample frames checked",
        "21",
        "MCAP messages read",
        "2",
        "Segments checked",
        "1",
        "Frames without native timestamps",
        "6",
    ]
    for name, inspect in [("inspected", True), ("metadata", False)]:
        output = tmp_path / name
        create_qc_package_review([package], output, inspect_payloads=inspect)
        html = (output / "index.html").read_text()
        lists = CountLists()
        lists.feed(html)
        assert lists.lists == ([expected] if inspect else [])
        assert "19 s" in html


def test_structure_only_does_not_acquire_a_sample_count(tmp_path):
    package = _package(tmp_path / "source", schema="custom.force/1")
    _write_batched_mcap(package, batches=[[10, 20, 30]])
    output = tmp_path / "review"
    create_qc_package_review([package], output, inspect_payloads=True)
    lists = CountLists()
    lists.feed((output / "index.html").read_text())
    assert lists.lists == [["MCAP messages read", "1", "Segments checked", "1"]]
