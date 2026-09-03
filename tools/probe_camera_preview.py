# SPDX-License-Identifier: GPL-3.0-only
"""Report which sources actually deliver preview frames during rehearsal.

Used to tell a UI rendering problem apart from a daemon that never publishes
camera preview in the first place.
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / "capture_protocol"),
]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import preview_pb2  # noqa: E402
from capture_protocol.generated.capture.v1.common_pb2 import MessageType  # noqa: E402


def payload_kind(frame: preview_pb2.PreviewFrame) -> str:
    for name in ("image", "trace", "matrix", "orientation", "waveform"):
        if frame.HasField(name):
            return name
    return frame.WhichOneof("payload") or "none"


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    only = sys.argv[2].lower() if len(sys.argv) > 2 else ""
    client = ControlClient()
    client.connect()

    sources = list(client.list_sources().sources)
    cams = [s for s in sources if s.source_type == "camera"]
    if only:
        cams = [s for s in cams if only in (s.alias or "").lower()]
    print(f"sources={len(sources)} cameras={len(cams)}")
    for s in cams:
        print(f"  camera {s.source_id} alias={s.alias!r} plugin={s.plugin_id!r}")

    ids = [s.source_id for s in cams]
    if not only:
        ids += [s.source_id for s in sources if s.source_id.startswith("radar.")]
    if not ids:
        print("no camera or radar sources")
        return 2
    print("selecting", ids)

    try:
        client.stop_rehearsal()
    except Exception:
        pass
    sess = client.create_session(f"preview-probe-{int(time.time())}")
    if sess.error.code:
        print("create_session", sess.error.code, sess.error.message)
        return 1
    client.subscribe_status(include_preview=True, health_interval_ms=1000)
    client.select_sources(ids)
    reh = client.start_rehearsal(ids)
    if reh.error.code:
        print("rehearsal", reh.error.code, reh.error.message)
        return 1

    counts: Counter[tuple[str, str]] = Counter()
    bytes_seen: Counter[str] = Counter()
    other: Counter[int] = Counter()
    deadline = time.time() + seconds
    while time.time() < deadline:
        event = client.poll_event(timeout_s=0.25)
        if event is None:
            continue
        mt, payload = event
        if mt != int(MessageType.MESSAGE_TYPE_PREVIEW_FRAME):
            other[mt] += 1
            continue
        frame = preview_pb2.PreviewFrame()
        frame.ParseFromString(payload)
        kind = payload_kind(frame)
        counts[(frame.source_id, kind)] += 1
        if kind == "image":
            bytes_seen[frame.source_id] += len(frame.image.data)

    print("other message types:", dict(other))
    try:
        view = client.get_session_view()
        print(f"state={view.state} rehearsal_active={view.rehearsal_active}")
        for a in list(view.alerts)[-15:]:
            print(f"  alert L{a.level} {a.source_id} {a.code}: {a.message}")
        for lane in view.lanes:
            if lane.source_id in ids:
                print(f"  lane {lane.source_id}: {lane}")
    except Exception as exc:  # noqa: BLE001
        print("session view unavailable:", exc)

    print(f"\npreview frames over {seconds:.0f}s:")
    if not counts:
        print("  NONE")
    for (sid, kind), n in sorted(counts.items()):
        extra = ""
        if kind == "image":
            extra = f" avg_bytes={bytes_seen[sid] // max(1, n)}"
        print(f"  {sid:<34} {kind:<12} {n:>4} ({n / seconds:.1f} Hz){extra}")

    missing = []
    for sid in [s.source_id for s in cams]:
        if not any(k[0] == sid for k in counts):
            print(f"\nMISSING camera preview for {sid}")
            missing.append(sid)

    client.stop_rehearsal()
    if missing:
        return 1
    # Prefer at least a few frames from the first selected camera.
    primary = cams[0].source_id if cams else ""
    primary_n = sum(n for (sid, kind), n in counts.items() if sid == primary and kind == "image")
    if cams and primary_n < 3:
        print(f"FAIL: only {primary_n} image frames from {primary}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
