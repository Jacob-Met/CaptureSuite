# SPDX-License-Identifier: GPL-3.0-only
"""Mid-record inject_fault(disconnect) on camera then one radar."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "libs" / "python" / "capture_protocol")]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import control_pb2  # noqa: E402


def _finalize(client: ControlClient) -> None:
    tok = client.request_stop()
    if tok.error.code:
        raise RuntimeError(f"request_stop {tok.error.code}")
    stop = client.stop_session(tok.confirmation_token)
    if stop.error.code:
        raise RuntimeError(f"stop_session {stop.error.code}")
    if stop.state != control_pb2.SESSION_STATE_FINALIZED:
        raise RuntimeError(f"expected FINALIZED, got {stop.state}")


def main() -> int:
    client = ControlClient(timeout_s=60.0)
    client.connect()
    sources = list(client.list_sources().sources)
    cams = [
        s
        for s in sources
        if s.source_type == "camera" and "brio" in (s.alias or "").lower()
    ]
    if not cams:
        cams = [s for s in sources if s.source_type == "camera"][:1]
    radars = [s for s in sources if s.source_id.startswith("radar.")]
    if not cams or not radars:
        print("need at least one camera and one radar")
        return 2
    ids = [cams[0].source_id] + [s.source_id for s in radars]
    victims = [cams[0].source_id, radars[0].source_id]
    print("recording", ids, "disconnect", victims)

    try:
        client.stop_rehearsal()
    except Exception:
        pass
    sess = client.create_session(f"inject-disconnect-{int(time.time())}")
    if sess.error.code:
        print("create_session", sess.error.code, sess.error.message)
        return 1
    package = Path(sess.package_path)
    print("package", package)

    client.select_sources(ids)
    for s in radars:
        mod = s.streams[0].modality if s.streams else ""
        if mod != "radar_doppler":
            client.apply_config(
                s.source_id,
                {
                    "num_chirps": 64,
                    "num_samples": 256,
                    "end_frequency_Hz": 63e9,
                },
            )
    start = client.start_selected()
    if start.error.code or start.state != control_pb2.SESSION_STATE_RECORDING:
        print("start_selected", start.error.code, start.error.message, start.state)
        return 1

    time.sleep(3.0)
    before = {s.source_id: s.sample_count for s in client.get_recording_stats().streams}

    for victim in victims:
        fault = client.inject_fault(victim, "disconnect")
        if fault.error.code:
            print("FAIL: inject_fault", victim, fault.error.code, fault.error.message)
            return 1
        print("injected disconnect", victim)
        time.sleep(1.0)

    after = {s.source_id: s.sample_count for s in client.get_recording_stats().streams}
    stats = client.get_recording_stats()
    gaps = {s.source_id: s.gap_count for s in stats.streams}
    print("before", before)
    print("after", after)
    print("gaps", gaps)

    ok = True
    for victim in victims:
        if gaps.get(victim, 0) < 1:
            print("FAIL: expected gap_count>=1 for", victim)
            ok = False
    # At least one non-victim radar (if dual) or survivors should still grow
    # after the first disconnect; camera+radar both disconnected so only
    # remaining radars count.
    remaining = [sid for sid in ids if sid not in victims]
    for sid in remaining:
        if after.get(sid, 0) <= before.get(sid, 0):
            print("FAIL: survivor stalled", sid)
            ok = False

    try:
        _finalize(client)
    except Exception as exc:
        print("FAIL: finalize", exc)
        return 1

    if not ok:
        print("FAIL", package)
        return 1
    print("PASS", package)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
