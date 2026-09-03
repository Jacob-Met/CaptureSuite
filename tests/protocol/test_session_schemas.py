# SPDX-License-Identifier: GPL-3.0-only
"""Generated session JSON Schema validity and example validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from capture_protocol.generated.capture.v1 import events_pb2, storage_pb2
from google.protobuf.json_format import MessageToDict
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / "schemas" / "session" / "jsonschema"


def _registry() -> Registry:
    registry: Registry = Registry()
    for path in SCHEMA_DIR.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        # Resolve both bare filenames and $id values used as $ref targets.
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(path.name, resource)
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], resource)
    return registry


def test_schema_index_lists_committed_files() -> None:
    index = json.loads((SCHEMA_DIR / "index.json").read_text(encoding="utf-8"))
    assert index["files"]
    for name in index["files"]:
        assert (SCHEMA_DIR / name).is_file()


@pytest.mark.parametrize(
    "name",
    sorted(p.name for p in SCHEMA_DIR.glob("*.schema.json")),
)
def test_each_schema_is_draft2020(name: str) -> None:
    schema = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


def test_manifest_example_validates() -> None:
    schema = json.loads((SCHEMA_DIR / "session_manifest.schema.json").read_text(encoding="utf-8"))
    msg = storage_pb2.SessionManifest(
        session_schema_version="1.0.0",
        session_id="11111111-1111-1111-1111-111111111111",
        state="preparing",
        app_version="0.1.0",
        daemon_version="0.1.0",
    )
    msg.identity.session_id = msg.session_id
    instance = MessageToDict(msg, preserving_proto_field_name=False)
    Draft202012Validator(schema, registry=_registry()).validate(instance)


def test_checkpoint_example_validates() -> None:
    schema = json.loads((SCHEMA_DIR / "checkpoint.schema.json").read_text(encoding="utf-8"))
    msg = events_pb2.Checkpoint(
        checkpoint_id="cp-1",
        original_timestamp_ns=123,
        effective_timestamp_ns=123,
        name="Baseline",
    )
    instance = MessageToDict(msg, preserving_proto_field_name=False)
    Draft202012Validator(schema, registry=_registry()).validate(instance)
