# SPDX-License-Identifier: GPL-3.0-only
"""Short multi-camera soak: record, watch health, verify sealed artifacts."""

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
from capture_protocol.generated.capture.v1 import control_pb2, health_pb2  # noqa: E402
from capture_protocol.generated.capture.v1.common_pb2 import MessageType  # noqa: E402

# Default short soak; override with SOAK_SECONDS.
RECORD_S = float(__import__("os").environ.get("SOAK_SECONDS", "120"))
PREFERRED = ("MX Brio", "FHD Camera", "Camo")


def pick_cameras(sources, n: int = 2):
    cams = [s for s in sources if s.source_type == "camera" and s.enabled]
    chosen = []
    for name in PREFERRED:
        for s in cams:
            if name.casefold() in (s.alias or "").casefold() and s not in chosen:
                chosen.append(s)
                break
    for s in cams:
        if len(chosen) >= n:
            break
        if s not in chosen:
            chosen.append(s)
    return chosen[:n]


def main() -> int:
    n = int(__import__("os").environ.get("SOAK_CAMERAS", "2"))
    # Stop finalizes large MKVs (EOS + hash) per camera; allow headroom.
    client = ControlClient(timeout_s=180.0)
    client.connect()
    cams = pick_cameras(client.list_sources().sources, n=n)
    if len(cams) < 2:
        print(f"need >=2 cameras, found {len(cams)}")
        return 2
    ids = [c.source_id for c in cams]
    print(f"soak {RECORD_S:.0f}s with: " + ", ".join(c.alias for c in cams))

    sess = client.create_session(f"soak-{int(time.time())}")
    if sess.error.code:
        print("create_session", sess.error.code, sess.error.message)
        return 1
    package = Path(sess.package_path)
    for sid in ids:
        client.apply_config(
            sid,
            {
                "encoder_preference": "auto",
                "preview_enabled": True,
                "preview_max_rate_hz": 10,
            },
        )
    client.select_sources(ids)
    client.subscribe_status(include_preview=True, health_interval_ms=1000)
    start = client.start_selected()
    if start.error.code or start.state != control_pb2.SESSION_STATE_RECORDING:
        print("start failed", start.error.code, start.error.message, start.state)
        return 1

    health: dict[str, health_pb2.HealthSnapshot] = {}
    previews: dict[str, int] = {i: 0 for i in ids}
    alerts: list[str] = []
    t0 = time.time()
    last_report = t0
    while time.time() - t0 < RECORD_S:
        ev = client.poll_event(timeout_s=0.5)
        if ev is not None:
            mt, payload = ev
            if mt == int(MessageType.MESSAGE_TYPE_HEALTH_SNAPSHOT):
                h = health_pb2.HealthSnapshot()
                h.ParseFromString(payload)
                if h.source_id in ids:
                    health[h.source_id] = h
            elif mt == int(MessageType.MESSAGE_TYPE_PREVIEW_FRAME):
                from capture_protocol.generated.capture.v1 import preview_pb2

                f = preview_pb2.PreviewFrame()
                f.ParseFromString(payload)
                if f.source_id in ids:
                    previews[f.source_id] += 1
            elif mt == int(MessageType.MESSAGE_TYPE_ALERT):
                a = health_pb2.Alert()
                a.ParseFromString(payload)
                if a.source_id in ids or not a.source_id:
                    alerts.append(f"{a.level}:{a.code}:{a.message}")
        now = time.time()
        if now - last_report >= 15:
            elapsed = now - t0
            for sid in ids:
                h = health.get(sid)
                alias = next(c.alias for c in cams if c.source_id == sid)
                if h:
                    print(
                        f"  t={elapsed:5.0f}s {alias}: rate={h.measured_rate_hz:5.1f} "
                        f"drop={h.dropped_count} arriving={h.data_arriving} "
                        f"prev={previews[sid]} err={h.last_error.code}"
                    )
                else:
                    print(f"  t={elapsed:5.0f}s {alias}: (no health yet) prev={previews[sid]}")
            last_report = now

    token = client.request_stop().confirmation_token
    stop = client.stop_session(token)
    if stop.error.code or stop.state != control_pb2.SESSION_STATE_FINALIZED:
        print("stop failed", stop.error.code, stop.error.message, stop.state)
        return 1

    ok = True
    print("\nfinal health")
    for cam in cams:
        h = health.get(cam.source_id)
        if h is None:
            print(f"  {cam.alias}: NO HEALTH")
            ok = False
            continue
        print(
            f"  {cam.alias}: rate={h.measured_rate_hz:.1f} drop={h.dropped_count} "
            f"previews={previews[cam.source_id]} err={h.last_error.code}"
        )
        if h.measured_rate_hz < 5.0:
            print("    FAIL: measured rate too low")
            ok = False
        if previews[cam.source_id] < max(10, RECORD_S):
            print("    FAIL: too few preview frames")
            ok = False
        seg = package / "sources" / cam.source_id / "streams" / "video" / "segments"
        mkvs = list(seg.glob("*.mkv")) if seg.is_dir() else []
        timings = list(seg.glob("*.timing.mcap")) if seg.is_dir() else []
        mkv_b = sum(p.stat().st_size for p in mkvs)
        tim_b = sum(p.stat().st_size for p in timings)
        print(f"    artifacts mkv={mkv_b}B timing={tim_b}B")
        # Rough lower bound: ~100 KB/s soft floor for a real encode.
        if mkv_b < RECORD_S * 50_000:
            print("    FAIL: MKV smaller than expected for soak duration")
            ok = False
        if tim_b < 500:
            print("    FAIL: timing sidecar empty")
            ok = False

    integrity = package / "integrity.json"
    if integrity.is_file():
        files = json.loads(integrity.read_text(encoding="utf-8")).get("files", [])
        sealed = [
            e
            for e in files
            if e.get("status") == "sealed"
            and e.get("sourceId") in ids
            and str(e.get("path", "")).endswith((".mkv", ".timing.mcap"))
        ]
        print(f"integrity sealed camera artifacts: {len(sealed)}")
        if len(sealed) < len(cams) * 2:
            ok = False
    else:
        print("FAIL: no integrity.json")
        ok = False

    if alerts:
        print("alerts during soak:")
        for a in alerts[:20]:
            print(" ", a)

    client.close()
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
