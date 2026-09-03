# SPDX-License-Identifier: GPL-3.0-only
"""Record both radar boards; check live sample counts and arrays.json."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / "capture_protocol"),
    str(ROOT / "libs" / "python" / "capture_session"),
]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import control_pb2  # noqa: E402

RECORD_S = 5.0


def main() -> int:
    client = ControlClient()
    client.connect()
    sources = [s for s in client.list_sources().sources if s.source_id.startswith("radar.")]
    if len(sources) < 2:
        print(f"need >=2 radar.* sources, found {len(sources)}")
        for s in sources:
            print(" ", s.source_id, s.alias, s.source_type)
        return 2

    ids = [s.source_id for s in sources]
    print("recording:", ", ".join(f"{s.alias}({s.source_id})" for s in sources))

    sess = client.create_session(f"dual-radar-{int(time.time())}")
    if sess.error.code:
        print("create_session:", sess.error.code, sess.error.message)
        return 1
    package = Path(sess.package_path)
    print("package:", package)

    sel = client.select_sources(ids)
    if sel.error.code:
        print("select:", sel.error.code, sel.error.message)
        return 1
    start = client.start_selected()
    if start.error.code:
        print("start_selected:", start.error.code, start.error.message)
        return 1
    if start.state != control_pb2.SESSION_STATE_RECORDING:
        print("expected RECORDING, got", start.state)
        return 1

    arrays_path = package / "arrays.json"
    if not arrays_path.is_file():
        print("FAIL: arrays.json missing")
        return 1
    arrays = json.loads(arrays_path.read_text(encoding="utf-8"))
    members = arrays.get("arrays", [{}])[0].get("members", [])
    member_ids = {m["sourceId"] for m in members}
    if set(ids) != member_ids:
        print("FAIL: arrays.json members", member_ids, "!=", set(ids))
        return 1
    mode = arrays["arrays"][0].get("timingMode")
    if mode != "SOFTWARE_COORDINATED":
        print("FAIL: timingMode", mode)
        return 1
    print("arrays.json OK:", len(members), "members,", mode)

    saw_live = {sid: False for sid in ids}
    t0 = time.time()
    while time.time() - t0 < RECORD_S:
        stats = client.get_recording_stats()
        parts = []
        for stream in stats.streams:
            if stream.source_id in saw_live:
                parts.append(f"{stream.source_id}={stream.sample_count}")
                if stream.sample_count > 0:
                    saw_live[stream.source_id] = True
        print("  samples:", ", ".join(parts) if parts else "(none)")
        time.sleep(1.0)

    missing = [sid for sid, ok in saw_live.items() if not ok]
    if missing:
        print("FAIL: live sample_count stayed 0 for", missing)
        return 1
    print("live sample counts OK")

    tok = client.request_stop()
    if tok.error.code:
        print("request_stop:", tok.error.code, tok.error.message)
        return 1
    stop = client.stop_session(tok.confirmation_token)
    if stop.error.code:
        print("stop:", stop.error.code, stop.error.message)
        return 1
    if stop.state != control_pb2.SESSION_STATE_FINALIZED:
        print("expected FINALIZED, got", stop.state)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
