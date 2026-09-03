# SPDX-License-Identifier: GPL-3.0-only
"""Probe whether the running daemon pushes PreviewFrame events."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "desktop"),
    str(ROOT / "libs" / "python" / "capture_protocol"),
    str(ROOT / "libs" / "python" / "capture_session"),
]

from capture_protocol.control_client import ControlClient, read_instance_file  # noqa: E402
from capture_protocol.generated.capture.v1 import health_pb2, preview_pb2  # noqa: E402
from capture_protocol.generated.capture.v1.common_pb2 import MessageType  # noqa: E402


def main() -> int:
    inst = read_instance_file()
    print("instance", inst)
    client = ControlClient()
    client.connect()
    print("connected", client.instance_id)

    srcs = client.list_sources()
    print("sources", len(srcs.sources))
    for s in srcs.sources:
        print(
            f"  {s.source_id:40} type={s.source_type:12} "
            f"plugin={s.plugin_id} enabled={s.enabled}"
        )

    sess = client.create_session(f"probe-{int(time.time())}")
    print("session", sess.session_id, "err", sess.error.code, sess.package_path)

    cams = [s.source_id for s in srcs.sources if s.source_type == "camera"]
    sims = [s.source_id for s in srcs.sources if s.source_type.startswith("sim.")]
    pick = (cams[:1] + sims[:2]) if cams else sims[:3]
    print("selecting", pick)
    sel = client.select_sources(pick)
    print("select err", sel.error.code, list(sel.selected_source_ids))

    sub = client.subscribe_status(
        include_preview=True, health_interval_ms=500, preview_rate_limit_hz=15
    )
    print("subscribe preview_included", sub.preview_included, "err", sub.error.code)

    reh = client.start_rehearsal(pick)
    print(
        "rehearsal err",
        reh.error.code if reh.error.code else "(ok)",
        reh.error.message,
    )

    previews: dict[str, tuple] = {}
    deadline = time.time() + 6.0
    while time.time() < deadline:
        ev = client.poll_event(timeout_s=0.4)
        if ev is None:
            continue
        mt, payload = ev
        if mt == int(MessageType.MESSAGE_TYPE_PREVIEW_FRAME):
            f = preview_pb2.PreviewFrame()
            f.ParseFromString(payload)
            previews[f.source_id] = (
                f.kind,
                f.sequence,
                f.HasField("image"),
                f.HasField("trace"),
                len(f.image.data) if f.HasField("image") else 0,
            )
            print(
                "PREVIEW",
                f.source_id,
                "kind",
                f.kind,
                "seq",
                f.sequence,
                "image_bytes",
                len(f.image.data) if f.HasField("image") else 0,
            )
        elif mt == int(MessageType.MESSAGE_TYPE_HEALTH_SNAPSHOT):
            h = health_pb2.HealthSnapshot()
            h.ParseFromString(payload)
            if h.source_id in pick:
                print(
                    "HEALTH",
                    h.source_id,
                    "life",
                    h.lifecycle_state,
                    "rate",
                    round(h.measured_rate_hz, 2),
                    "err",
                    h.last_error.code,
                    h.last_error.message,
                )

    print("summary previews", previews)
    try:
        client.stop_rehearsal()
    except Exception as exc:  # noqa: BLE001
        print("stop rehearsal", exc)
    client.close()
    return 0 if previews else 2


if __name__ == "__main__":
    raise SystemExit(main())
