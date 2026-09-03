# SPDX-License-Identifier: GPL-3.0-only
"""Rehearse each camera in turn and report whether preview frames arrive."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / "capture_protocol"),
    str(ROOT / "libs" / "python" / "capture_session"),
]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import health_pb2, preview_pb2  # noqa: E402
from capture_protocol.generated.capture.v1.common_pb2 import MessageType  # noqa: E402

WINDOW_S = 5.0


def main() -> int:
    client = ControlClient()
    client.connect()
    sources = client.list_sources()
    cameras = [s for s in sources.sources if s.source_type == "camera"]
    print(f"{len(cameras)} camera(s) enumerated\n")

    session = client.create_session(f"cams-{int(time.time())}")
    if session.error.code:
        print("create_session failed:", session.error.message)
        return 1
    client.subscribe_status(include_preview=True, health_interval_ms=1000)

    results = []
    for cam in cameras:
        sid = cam.source_id
        print(f"--- {cam.alias} ({sid})")
        client.select_sources([sid])
        reh = client.start_rehearsal([sid])
        if reh.error.code:
            print(f"    rehearsal refused: {reh.error.code}: {reh.error.message}")
            results.append((cam.alias, 0, 0.0, reh.error.message))
            continue

        frames = 0
        last_bytes = 0
        dims = ""
        rate = 0.0
        error = ""
        deadline = time.time() + WINDOW_S
        while time.time() < deadline:
            event = client.poll_event(timeout_s=0.3)
            if event is None:
                continue
            message_type, payload = event
            if message_type == int(MessageType.MESSAGE_TYPE_PREVIEW_FRAME):
                frame = preview_pb2.PreviewFrame()
                frame.ParseFromString(payload)
                if frame.source_id == sid and frame.HasField("image"):
                    frames += 1
                    last_bytes = len(frame.image.data)
                    dims = f"{frame.image.width}x{frame.image.height}"
            elif message_type == int(MessageType.MESSAGE_TYPE_HEALTH_SNAPSHOT):
                snap = health_pb2.HealthSnapshot()
                snap.ParseFromString(payload)
                if snap.source_id == sid:
                    rate = snap.measured_rate_hz
                    if snap.last_error.code:
                        error = f"{snap.last_error.code}: {snap.last_error.message}"

        verdict = "OK" if frames else "NO PREVIEW"
        print(
            f"    {verdict}: {frames} frames in {WINDOW_S:.0f}s, "
            f"{dims or '-'} {last_bytes}B, record {rate:.1f} Hz {error}"
        )
        results.append((cam.alias, frames, rate, error))
        client.stop_rehearsal()
        time.sleep(0.5)

    print("\nSummary")
    for alias, frames, rate, error in results:
        status = "OK  " if frames else "FAIL"
        print(f"  [{status}] {alias:24} previews={frames:3d} record={rate:5.1f} Hz {error}")

    client.close()
    return 0 if any(f for _, f, _, _ in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
