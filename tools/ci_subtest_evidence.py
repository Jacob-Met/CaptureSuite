# SPDX-License-Identifier: GPL-3.0-only
"""Record the nested outcomes that pytest folds into their parent's JUnit testcase."""

import hashlib
import json
from pathlib import Path

import pytest
from _pytest.junitxml import bin_xml_escape, mangle_test_address


def pytest_configure(config):
    path = config.getoption("xmlpath")
    if path and not hasattr(config, "workerinput"):
        config.pluginmanager.register(SubtestRecorder(Path(path), config.getoption("junitprefix")))


def failure_sha256(report):
    if not report.failed:
        return None
    # Match XML 1.0 end-of-line normalization when reading pytest's traceback text.
    text = bin_xml_escape(str(report.longrepr)).replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SubtestRecorder:
    def __init__(self, xml, prefix):
        self.xml = xml
        self.prefix = prefix
        self.parents = {}

    def pytest_runtest_logreport(self, report):
        if report.when != "call":
            return
        if hasattr(report, "context") and type(report).__name__ in {
            "SubtestReport",
            "SubTestReport",
        }:
            names = mangle_test_address(report.nodeid)
            classname = ".".join(([self.prefix] if self.prefix else []) + names[:-1])
            group = self.parents.setdefault(
                report.nodeid,
                {
                    "classname": classname,
                    "name": bin_xml_escape(names[-1]),
                    "events": [],
                    "parent_outcome": None,
                    "nodeid": report.nodeid,
                },
            )
            events = group["events"]
            events.append(
                {
                    "ordinal": len(events) + 1,
                    "description": report.head_line,
                    "outcome": report.outcome,
                    "failure_sha256": failure_sha256(report),
                }
            )
        elif report.nodeid in self.parents:
            self.parents[report.nodeid]["parent_outcome"] = report.outcome
            self.parents[report.nodeid]["parent_failure_sha256"] = failure_sha256(report)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self):
        raw_hash = hashlib.sha256(self.xml.read_bytes()).hexdigest()
        target = self.xml.with_suffix(".subtests.json")
        target.write_text(
            json.dumps(
                {
                    "schema": "capturesuite.pytest-subtests.v1",
                    "junit_sha256": raw_hash,
                    "parents": list(self.parents.values()),
                },
                ensure_ascii=True,
            ),
            encoding="utf-8",
        )
