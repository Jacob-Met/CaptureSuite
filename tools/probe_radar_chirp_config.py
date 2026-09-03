# SPDX-License-Identifier: GPL-3.0-only
"""Smoke radar.ifx/3 chirp geometry ApplyConfig + live preview sizing."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "libs" / "python" / "capture_protocol")]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import preview_pb2  # noqa: E402
from capture_protocol.generated.capture.v1.common_pb2 import MessageType  # noqa: E402


def wait_matrix(client: ControlClient, sid: str, *, rows: int, cols: int,
                timeout_s: float = 8.0) -> str:
    deadline = time.time() + timeout_s
    seen: list[str] = []
    while time.time() < deadline:
        event = client.poll_event(timeout_s=0.3)
        if event is None:
            continue
        mt, payload = event
        if mt != int(MessageType.MESSAGE_TYPE_PREVIEW_FRAME):
            continue
        frame = preview_pb2.PreviewFrame()
        frame.ParseFromString(payload)
        if frame.source_id != sid or not frame.HasField("matrix"):
            continue
        detail = f"{frame.matrix.rows}x{frame.matrix.cols}"
        seen.append(detail)
        if frame.matrix.rows == rows and frame.matrix.cols == cols:
            return detail
    raise RuntimeError(f"no {rows}x{cols} matrix; saw {seen[-8:]}")


def main() -> int:
    client = ControlClient()
    client.connect()
    radars = [
        s
        for s in client.list_sources().sources
        if s.source_id.startswith("radar.")
        and (s.streams[0].modality if s.streams else "") != "radar_doppler"
    ]
    if not radars:
        print("no FMCW radar")
        return 2
    sid = radars[0].source_id
    print("target", radars[0].alias, sid)

    schema = client.get_config_schema(sid)
    print("schema_revision", schema.schema_revision)
    if schema.schema_revision != "radar.ifx/3":
        print("FAIL: expected radar.ifx/3")
        return 1
    if "num_chirps" not in schema.schema_json:
        print("FAIL: schema missing num_chirps")
        return 1

    try:
        client.stop_rehearsal()
    except Exception:
        pass
    client.create_session(f"radar-chirp-{int(time.time())}")
    client.subscribe_status(include_preview=True, health_interval_ms=1000)
    client.select_sources([sid])

    # Higher-resolution geometry before rehearsal (connect applies sequence).
    hi = {
        "num_chirps": 64,
        "num_samples": 256,
        "start_frequency_Hz": 60e9,
        "end_frequency_Hz": 63e9,  # 3 GHz bandwidth
        "preview_view": "range_doppler",
    }
    applied = client.apply_config(sid, hi)
    if applied.error.code:
        print("apply", applied.error.code, applied.error.message)
        return 1
    print("effective", applied.effective_json)

    reh = client.start_rehearsal([sid])
    if reh.error.code:
        print("rehearsal", reh.error.code, reh.error.message)
        return 1

    # Standard preview uses range_fft=128 → 64 rows unless samples force larger.
    # With 256 samples, next_pow2_at_least(128, 256) = 256 → 128 range bins.
    # Doppler: next_pow2_at_least(64, 64) = 64 cols.
    detail = wait_matrix(client, sid, rows=128, cols=64)
    print("got matrix", detail)

    # Live geometry change while capturing must require restart.
    blocked = client.apply_config(sid, {"num_samples": 128})
    if blocked.error.code != "RESTART_REQUIRED":
        print("FAIL: expected RESTART_REQUIRED, got", blocked.error.code,
              blocked.error.message)
        return 1
    print("restart gate ok")

    client.stop_rehearsal()
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
