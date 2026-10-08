# SPDX-License-Identifier: GPL-3.0-only
"""Consequential record semantics; no GUI or replacement package parser."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from capture_desktop.review_events import checkpoint_time, events_from_summary, filter_events
from capture_session.package_reader import GapSummary, ReviewSummary, load_review_summary


def _summary(**values):
    return ReviewSummary("authored.mmsession", "authored", "finalized", **values)


@pytest.mark.parametrize("value", [None, True, False, 1.0, 1.25, "", "+1", "1e3", [], {}, "bad"])
def test_invalid_effective_time_is_not_replaced_with_original(value):
    row = {"effectiveTimestampNs": value, "originalTimestampNs": "77", "name": "authored"}
    time, basis = checkpoint_time(row)
    assert time is None
    assert basis == "Unavailable: invalid effectiveTimestampNs"
    event, = events_from_summary(_summary(checkpoints=[row]))
    assert event.time_ns is None
    assert json.loads(event.details.split("Loaded record:\n", 1)[1]) == row


@pytest.mark.parametrize("value,expected", [(0, 0), ("0", 0), ("-1", -1), ("0009", 9),
                                           ("9223372036854775807", 9223372036854775807)])
def test_exact_time_and_absent_preferred_field(value, expected):
    row = {"originalTimestampNs": value}
    assert checkpoint_time(row) == (expected, "originalTimestampNs")
    assert checkpoint_time({**row, "effectiveTimestampNs": "0"}) == (0, "effectiveTimestampNs")


def test_loaded_records_preserve_duplicates_unknowns_and_stable_time_order():
    summary = _summary(
        checkpoints=[
            {"checkpointId": "same", "name": "first", "effectiveTimestampNs": "0"},
            {"checkpointId": "same", "name": "second", "effectiveTimestampNs": "0"},
            {"checkpointId": "unknown-1"},
            {"checkpointId": "unknown-2", "effectiveTimestampNs": False},
        ],
        annotations=[
            {"annotationId": "big", "timestampNs": "9007199254740993", "text": "late"},
            {"annotationId": "before", "timestampNs": "-1", "text": "before"},
        ],
    )
    rows = events_from_summary(summary)
    assert [r.label for r in rows] == [
        "before", "first", "second", "late", "unknown-1", "unknown-2",
    ]
    assert [r.time_ns for r in rows] == [-1, 0, 0, 9007199254740993, None, None]
    assert len({r.position for r in rows}) == 6


def test_source_kind_and_literal_query_intersect_without_inferred_scope():
    rows = events_from_summary(_summary(
        checkpoints=[{"name": "Review", "tags": ["needle.*"], "originalTimestampNs": "0"}],
        annotations=[
            {"text": "<b>Needle.* 雪</b>", "sourceId": "A", "timestampNs": "1"},
            {"text": "needle.*", "sourceId": "a", "timestampNs": "2"},
            {"text": "needle.*", "sourceId": False, "timestampNs": "3"},
            {"text": "other", "sourceId": "A", "timestampNs": "4"},
        ],
    ))
    assert len(filter_events(rows, query=".*")) == 4
    assert len(filter_events(rows, query=".*", kind="Annotation", source_id="A")) == 1
    assert len(filter_events(rows, query="NEEDLE", source_id="a")) == 1
    assert len(filter_events(rows, source_id="")) == 2
    assert len(filter_events(rows, source_id="missing")) == 0
    assert len(filter_events(rows, query="雪")) == 1
    assert len(filter_events(rows, query="^.*$")) == 0
    assert '"sourceId": false' in filter_events(rows, kind="Annotation", source_id="")[0].details


def test_gap_closure_end_and_lost_count_are_separate_reported_facts():
    gaps = [
        GapSummary("s", "one", "disconnect", 5, 15, False, 9007199254740993),
        GapSummary("s", "two", "writer", 10, None, True, 0),
        GapSummary("s", "one", "disconnect", 5, 15, False, 9007199254740993),
    ]
    rows = events_from_summary(_summary(gaps=gaps))
    assert len(rows) == 3
    assert [r.label for r in rows] == ["Open · disconnect", "Open · disconnect", "Closed · writer"]
    first = json.loads(rows[0].details.split("Gap summary from package reader:\n", 1)[1])
    last = json.loads(rows[-1].details.split("Gap summary from package reader:\n", 1)[1])
    assert first["closed"] is False and first["endSessionTimeNs"] == 15
    assert first["estimatedLostCount"] == 9007199254740993
    assert last["closed"] is True and last["endSessionTimeNs"] is None


def test_full_record_is_immutable_snapshot_and_does_not_change_summary():
    record = {
        "checkpointId": "x", "originalTimestampNs": "9", "effectiveTimestampNs": "0",
        "notes": "<img src='https://invalid.example/x'> & 雪",
        "structuredFields": {"empty": "", "false": False, "null": None, "zero": 0},
        "revisionHistory": [{"originalTimestampNs": "9", "reason": "retained"}],
        "unknownFutureField": ["keep", {"deep": "value"}],
    }
    summary = _summary(checkpoints=[record])
    before = copy.deepcopy(summary)
    row, = events_from_summary(summary)
    assert summary == before
    assert json.loads(row.details.split("Loaded record:\n", 1)[1]) == record
    record["notes"] = "changed after loading"
    record["structuredFields"]["zero"] = 99
    assert "changed after loading" not in row.details
    assert '"zero": 0' in row.details


def test_real_package_reader_preserves_input_and_documents_its_loaded_subset(tmp_path):
    package = tmp_path / "sealed.mmsession"
    events = package / "events"
    health = package / "sources" / "folder-id" / "health"
    events.mkdir(parents=True)
    health.mkdir(parents=True)
    (package / "manifest.json").write_text(
        json.dumps({"sessionId": "authored", "state": "finalized_recovered"}), encoding="utf-8",
    )
    checkpoint = {"name": "零", "effectiveTimestampNs": "0", "originalTimestampNs": "99"}
    (events / "checkpoints.json").write_text(
        json.dumps([checkpoint, "not a record"]), encoding="utf-8",
    )
    (events / "annotations.json").write_text(
        json.dumps({"annotations": [{"timestampNs": "1", "text": "kept", "sourceId": "wire-id"}]}),
        encoding="utf-8",
    )
    (health / "gaps.jsonl").write_text(
        '{"sourceId":"wire-id","streamId":"s","startSessionTimeNs":"2","closed":false}\n'
        'not valid JSON\n',
        encoding="utf-8",
    )

    def snapshot():
        return {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in package.rglob("*") if p.is_file()}

    before = snapshot()
    loaded = load_review_summary(package)
    rows = events_from_summary(loaded)
    assert len(rows) == 3  # The unchanged reader omits a non-object and a malformed JSONL row.
    assert [r.time_ns for r in rows] == [0, 1, 2]
    assert len(filter_events(rows, source_id="wire-id")) == 2
    assert not filter_events(rows, source_id="folder-id")
    assert json.loads(rows[0].details.split("Loaded record:\n", 1)[1]) == checkpoint
    assert snapshot() == before
    assert all(not (package / name).exists() for name in ("processing", "exports"))


def test_missing_optional_files_produce_no_invented_records(tmp_path):
    package = tmp_path / "minimal.mmsession"
    package.mkdir()
    (package / "manifest.json").write_text('{"state":"finalized"}', encoding="utf-8")
    summary = load_review_summary(package)
    assert events_from_summary(summary) == ()
    assert filter_events((), query="anything") == ()


def test_long_session_projection_keeps_all_records_and_exact_search_result():
    records = [{"timestampNs": str(i), "text": f"authored event {i}", "sourceId": f"s{i % 3}"}
               for i in range(2000)]
    rows = events_from_summary(_summary(annotations=records))
    assert len(rows) == 2000
    found = filter_events(rows, source_id="s2", query="authored event 1997")
    assert len(found) == 1 and found[0].time_ns == 1997
