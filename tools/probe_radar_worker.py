# SPDX-License-Identifier: GPL-3.0-only
"""List radar sources from the daemon and smoke-test preview on real hardware."""

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
    radar = [s for s in sources.sources if s.source_type == "radar" or s.source_id.startswith("radar.")]
    sim_radar = [s for s in sources.sources if s.source_id.startswith("sim.radar")]

    print(f"{len(radar)} real radar source(s), {len(sim_radar)} sim radar source(s)\n")
    for s in radar:
        print(f"  radar.*  {s.alias:30} {s.source_id}")
    for s in sim_radar:
        print(f"  sim      {s.alias:30} {s.source_id}")
    print()

    if not radar:
        print("No radar.* sources — board may be unplugged or Fusion GUI may hold the device.")
        client.close()
        return 2

    target = radar[0]
    sid = target.source_id
    print(f"--- smoke: {target.alias} ({sid})")

    session = client.create_session(f"radar-probe-{int(time.time())}")
    if session.error.code:
        print("create_session failed:", session.error.message)
        client.close()
        return 1

    client.subscribe_status(include_preview=True, health_interval_ms=1000)
    client.select_sources([sid])
    reh = client.start_rehearsal([sid])
    if reh.error.code:
        print(f"rehearsal refused: {reh.error.code}: {reh.error.message}")
        client.close()
        return 1

    frames = 0
    matrix_dims = ""
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
            if frame.source_id == sid and frame.HasField("matrix"):
                frames += 1
                matrix_dims = f"{frame.matrix.rows}x{frame.matrix.cols}"
        elif message_type == int(MessageType.MESSAGE_TYPE_HEALTH_SNAPSHOT):
            snap = health_pb2.HealthSnapshot()
            snap.ParseFromString(payload)
            if snap.source_id == sid:
                rate = snap.measured_rate_hz
                if snap.last_error.code:
                    error = f"{snap.last_error.code}: {snap.last_error.message}"

    verdict = "OK" if frames else "NO PREVIEW"
    print(
        f"    {verdict}: {frames} matrix frames in {WINDOW_S:.0f}s, "
        f"{matrix_dims or '-'}, record {rate:.1f} Hz {error}"
    )
    client.stop_rehearsal()
    client.close()
    return 0 if frames else 3


if __name__ == "__main__":
    raise SystemExit(main())
