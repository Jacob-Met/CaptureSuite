# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for the CONFIGURATION_UI.md JSON Schema subset helpers."""

from __future__ import annotations

from capture_protocol.config_schema import (
    dirty_summary,
    group_order,
    iter_fields,
    match_preset_to_schema,
    merge_current,
    validate_document,
)

SCHEMA = {
    "schema_revision": "test/1",
    "type": "object",
    "required": ["gain"],
    "properties": {
        "gain": {
            "type": "number",
            "minimum": 0.1,
            "maximum": 10,
            "default": 1.0,
            "title": "Gain",
            "x-capture-group": "Signal",
            "x-capture-order": 1,
        },
        "rate": {
            "type": "integer",
            "enum": [60, 100],
            "default": 100,
            "title": "Rate",
            "x-capture-group": "Stream",
            "x-capture-order": 1,
            "x-capture-restart-required": True,
        },
        "serial": {
            "type": "string",
            "default": "abc",
            "readOnly": True,
            "x-capture-group": "Device",
            "x-capture-order": 1,
        },
        "chirp": {
            "type": "number",
            "default": 2000,
            "x-capture-group": "RF",
            "x-capture-order": 1,
            "x-capture-advanced": True,
        },
    },
}


def test_iter_fields_groups_and_order():
    fields = iter_fields(SCHEMA)
    names = [f.name for f in fields]
    assert names.index("serial") < names.index("chirp")
    assert group_order(fields)[0] in {"Device", "Signal", "Stream", "RF"}


def test_merge_current_overrides_defaults():
    doc = merge_current(SCHEMA, {"gain": 2.5})
    assert doc["gain"] == 2.5
    assert doc["rate"] == 100


def test_validate_rejects_out_of_range_and_unknown():
    bad = validate_document(SCHEMA, {"gain": 99})
    assert not bad.ok
    assert any("maximum" in e for e in bad.errors)

    unknown = validate_document(SCHEMA, {"gain": 1.0, "nope": 1})
    assert not unknown.ok

    missing = validate_document(SCHEMA, {"rate": 100})
    assert not missing.ok


def test_validate_accepts_legal_document():
    ok = validate_document(SCHEMA, {"gain": 2.0, "rate": 60})
    assert ok.ok


def test_dirty_summary_flags_restart():
    baseline = merge_current(SCHEMA, None)
    current = dict(baseline)
    current["rate"] = 60
    changed, restart = dirty_summary(SCHEMA, baseline, current)
    assert "Rate" in changed
    assert restart


def test_match_preset_rejects_unknown_and_revision_mismatch():
    ok = match_preset_to_schema(
        SCHEMA,
        {
            "schema_revision": "test/1",
            "configuration": {"gain": 1.5, "rate": 60},
        },
    )
    assert ok.ok

    bad_rev = match_preset_to_schema(
        SCHEMA,
        {"schema_revision": "other/9", "configuration": {"gain": 1.0}},
    )
    assert not bad_rev.ok

    unknown = match_preset_to_schema(
        SCHEMA,
        {"schema_revision": "test/1", "configuration": {"gain": 1.0, "extra": 1}},
    )
    assert not unknown.ok
    assert any("unknown fields" in e for e in unknown.errors)
