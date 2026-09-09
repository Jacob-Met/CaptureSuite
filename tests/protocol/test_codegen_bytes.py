# SPDX-License-Identifier: GPL-3.0-only
"""Byte-level generation invariants; no evaluator newline normalization."""

import json

import gen_protos
import gen_session_schemas
from google.protobuf import descriptor_pb2


def test_rewritten_proto_imports_are_lf_and_idempotent(tmp_path):
    target = tmp_path / "example_pb2.py"
    target.write_bytes(b"from capture.v1 import control_pb2\nVALUE = 1\n")
    gen_protos._rewrite_imports(tmp_path)
    expected = b"from capture_protocol.generated.capture.v1 import control_pb2\nVALUE = 1\n"
    assert target.read_bytes() == expected
    gen_protos._rewrite_imports(tmp_path)
    assert target.read_bytes() == expected


def test_json_schema_generator_writes_canonical_lf_bytes(tmp_path, monkeypatch):
    source = descriptor_pb2.FileDescriptorSet()
    file = source.file.add(name="synthetic.proto", package="test", syntax="proto3")
    message = file.message_type.add(name="Item")
    message.field.add(name="value", number=1, type=9, label=1)
    descriptor = tmp_path / "input.desc"
    original = source.SerializeToString()
    descriptor.write_bytes(original)
    out = tmp_path / "generated"
    monkeypatch.setattr(gen_session_schemas, "DESC_PATH", descriptor)
    monkeypatch.setattr(gen_session_schemas, "OUT_DIR", out)
    monkeypatch.setattr(gen_session_schemas, "SESSION_MESSAGES", ["test.Item"])
    monkeypatch.setattr(gen_session_schemas, "PRESERVE_SCHEMAS", set())
    assert gen_session_schemas.main() == 0
    first = {f.name: f.read_bytes() for f in out.glob("*.json")}
    assert len(first) == 2
    for raw in first.values():
        assert b"\r" not in raw
        assert raw == (json.dumps(json.loads(raw), indent=2) + "\n").encode()
    assert gen_session_schemas.main() == 0
    assert {f.name: f.read_bytes() for f in out.glob("*.json")} == first
    assert descriptor.read_bytes() == original
