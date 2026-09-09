#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Generate session JSON Schemas from the protobuf descriptor set.

Output is committed under schemas/session/jsonschema/. Never hand-edit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from google.protobuf import descriptor_pb2
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.message_factory import GetMessageClass

REPO_ROOT = Path(__file__).resolve().parents[1]
DESC_PATH = REPO_ROOT / "build" / "generated" / "capture_v1.desc"
OUT_DIR = REPO_ROOT / "schemas" / "session" / "jsonschema"

# Hand-maintained schemas (not from protobuf); never deleted by regen.
PRESERVE_SCHEMAS = frozenset(
    {
        "analysis_feature_schema.schema.json",
        "analysis_job.schema.json",
    }
)

# Messages that appear on disk / in session packages.
SESSION_MESSAGES = [
    "capture.v1.SessionManifest",
    "capture.v1.PhysicalDevice",
    "capture.v1.SourceInstance",
    "capture.v1.SensorInstance",
    "capture.v1.StreamDescriptor",
    "capture.v1.LogicalSlot",
    "capture.v1.Checkpoint",
    "capture.v1.Annotation",
    "capture.v1.SyncAnchor",
    "capture.v1.ClockMapping",
    "capture.v1.DeviceArray",
    "capture.v1.RadarArray",
    "capture.v1.PresetSnapshot",
    "capture.v1.IntegrityManifest",
    "capture.v1.IntegrityFileEntry",
    "capture.v1.GapEvent",
    "capture.v1.HealthSnapshot",
    "capture.v1.SessionIdentity",
    "capture.v1.TimingHeader",
]


def _proto_type_to_jsonschema(field) -> dict:
    from google.protobuf import descriptor as desc

    mapping = {
        desc.FieldDescriptor.TYPE_DOUBLE: {"type": "number"},
        desc.FieldDescriptor.TYPE_FLOAT: {"type": "number"},
        desc.FieldDescriptor.TYPE_INT64: {"type": "string", "pattern": "^-?[0-9]+$"},
        desc.FieldDescriptor.TYPE_UINT64: {"type": "string", "pattern": "^[0-9]+$"},
        desc.FieldDescriptor.TYPE_INT32: {"type": "integer"},
        desc.FieldDescriptor.TYPE_FIXED64: {"type": "string", "pattern": "^[0-9]+$"},
        desc.FieldDescriptor.TYPE_FIXED32: {"type": "integer"},
        desc.FieldDescriptor.TYPE_BOOL: {"type": "boolean"},
        desc.FieldDescriptor.TYPE_STRING: {"type": "string"},
        desc.FieldDescriptor.TYPE_BYTES: {"type": "string", "contentEncoding": "base64"},
        desc.FieldDescriptor.TYPE_UINT32: {"type": "integer", "minimum": 0},
        desc.FieldDescriptor.TYPE_SFIXED32: {"type": "integer"},
        desc.FieldDescriptor.TYPE_SFIXED64: {"type": "string", "pattern": "^-?[0-9]+$"},
        desc.FieldDescriptor.TYPE_SINT32: {"type": "integer"},
        desc.FieldDescriptor.TYPE_SINT64: {"type": "string", "pattern": "^-?[0-9]+$"},
    }
    if field.type == desc.FieldDescriptor.TYPE_ENUM:
        values = [v.name for v in field.enum_type.values]
        # protobuf JSON uses enum names
        return {"type": "string", "enum": values}
    if field.type == desc.FieldDescriptor.TYPE_MESSAGE:
        return {"$ref": f"{_schema_filename(field.message_type.full_name)}"}
    return mapping.get(field.type, {"type": "string"})


def _schema_filename(full_name: str) -> str:
    # capture.v1.SessionManifest -> session_manifest.schema.json
    short = full_name.split(".")[-1]
    snake = []
    for i, ch in enumerate(short):
        if ch.isupper() and i > 0:
            snake.append("_")
        snake.append(ch.lower())
    return "".join(snake) + ".schema.json"


def _message_to_schema(message_descriptor) -> dict:
    properties: dict = {}
    for field in message_descriptor.fields:
        # Prefer protobuf JSON names (camelCase) for on-disk compatibility.
        json_name = field.json_name
        schema = _proto_type_to_jsonschema(field)
        if field.label == field.LABEL_REPEATED:
            if field.type == field.TYPE_MESSAGE and field.message_type.GetOptions().map_entry:
                # map<K,V>
                value_field = field.message_type.fields_by_name["value"]
                schema = {
                    "type": "object",
                    "additionalProperties": _proto_type_to_jsonschema(value_field),
                }
            else:
                schema = {"type": "array", "items": schema}
        properties[json_name] = schema
        # proto3 fields are not required in JSON; keep schema open
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": _schema_filename(message_descriptor.full_name),
        "title": message_descriptor.full_name,
        "type": "object",
        "properties": properties,
        "additionalProperties": True,
        "unevaluatedProperties": True,
    }


def main() -> int:
    if not DESC_PATH.exists():
        print(f"Descriptor set missing: {DESC_PATH}", file=sys.stderr)
        print("Run tools/gen_protos.py first.", file=sys.stderr)
        return 1

    file_set = descriptor_pb2.FileDescriptorSet()
    file_set.ParseFromString(DESC_PATH.read_bytes())
    pool = DescriptorPool()
    for file_proto in file_set.file:
        pool.Add(file_proto)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Remove previous proto-generated schemas only.
    for old in OUT_DIR.glob("*.schema.json"):
        if old.name not in PRESERVE_SCHEMAS:
            old.unlink()

    written = []
    for full_name in SESSION_MESSAGES:
        try:
            msg_desc = pool.FindMessageTypeByName(full_name)
        except KeyError:
            print(f"WARNING: message not found: {full_name}", file=sys.stderr)
            continue
        # Ensure message class is registered (side effect for some protobuf versions)
        GetMessageClass(msg_desc)
        schema = _message_to_schema(msg_desc)
        out_path = OUT_DIR / _schema_filename(full_name)
        out_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8", newline="\n")
        written.append(out_path.name)

    preserved = sorted(name for name in PRESERVE_SCHEMAS if (OUT_DIR / name).is_file())
    all_files = sorted(set(written) | set(preserved))

    index = {
        "generated_from": "build/generated/capture_v1.desc",
        "messages": SESSION_MESSAGES,
        "files": all_files,
        "hand_maintained": preserved,
    }
    (OUT_DIR / "index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"Wrote {len(written)} schemas to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
