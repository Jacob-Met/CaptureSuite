# SPDX-License-Identifier: GPL-3.0-only
"""Python structured logging matches OPERATIONS.md required fields."""

from __future__ import annotations

import json
from pathlib import Path

from capture_protocol.structured_log import StructuredLogger


def test_structured_log_json_fields(tmp_path: Path) -> None:
    log = StructuredLogger("desktop")
    log.configure(log_dir=tmp_path, also_stderr=False)
    log.set_session_id("sess-py")
    log.info("unit_test", "hello", source_id="sim.emg.main", note="x")

    path = tmp_path / "desktop.log"
    line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
    row = json.loads(line)
    assert row["event"] == "unit_test"
    assert row["msg"] == "hello"
    assert row["level"] == "info"
    assert row["component"] == "desktop"
    assert row["session_id"] == "sess-py"
    assert row["source_id"] == "sim.emg.main"
    assert row["note"] == "x"
    assert "ts_utc" in row
    assert isinstance(row["qpc_ns"], int)
    assert row["qpc_ns"] > 0
    assert "pid" in row
