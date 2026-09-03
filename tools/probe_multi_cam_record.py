# SPDX-License-Identifier: GPL-3.0-only
"""Multi-camera record smoke: Start → MKV+timing → Stop → finalize."""

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

RECORD_S = 4.0
PREFERRED = ("MX Brio", "FHD Camera")


def pick_cameras(sources) -> list:
    cams = [s for s in sources if s.source_type == "camera" and s.enabled]
    chosen = []
    for name in PREFERRED:
        for s in cams:
            if name.casefold() in (s.alias or "").casefold() and s not in chosen:
                chosen.append(s)
                break
    for s in cams:
        if len(chosen) >= 2:
            break
        if s not in chosen:
            chosen.append(s)
    return chosen[:2]


def segment_files(package: Path, source_id: str) -> dict[str, list[Path]]:
    seg = package / "sources" / source_id / "streams" / "video" / "segments"
    if not seg.is_dir():
        return {"mkv": [], "timing": []}
    return {
        "mkv": sorted(seg.glob("*.mkv")),
        "timing": sorted(seg.glob("*.timing.mcap")),
    }


def main() -> int:
    client = ControlClient()
    client.connect()
    sources = client.list_sources().sources
    cams = pick_cameras(sources)
    if len(cams) < 2:
        print(f"need >=2 cameras, found {len(cams)}")
        client.close()
        return 2

    ids = [c.source_id for c in cams]
    print("recording:", ", ".join(f"{c.alias} ({c.source_id})" for c in cams))

    sess = client.create_session(f"multicam-{int(time.time())}")
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
    print(f"recording for {RECORD_S:.0f}s…")

    t0 = time.time()
    while time.time() - t0 < RECORD_S:
        stats = client.get_recording_stats()
        for stream in stats.streams:
            if stream.source_id in ids:
                print(
                    f"  stats {stream.source_id}: samples={stream.sample_count} "
                    f"rate={getattr(stream, 'measured_rate_hz', 0):.1f}"
                )
        time.sleep(1.0)

    stop_req = client.request_stop()
    if stop_req.error.code:
        print("request_stop:", stop_req.error.code, stop_req.error.message)
        return 1
    stop = client.stop_session(stop_req.confirmation_token)
    if stop.error.code:
        print("stop_session:", stop.error.code, stop.error.message)
        return 1
    if stop.state != control_pb2.SESSION_STATE_FINALIZED:
        print("expected FINALIZED, got", stop.state)
        return 1
    print("finalized")

    ok = True
    for cam in cams:
        files = segment_files(package, cam.source_id)
        mkv_bytes = sum(p.stat().st_size for p in files["mkv"])
        timing_bytes = sum(p.stat().st_size for p in files["timing"])
        stream_json = (
            package / "sources" / cam.source_id / "streams" / "video" / "stream.json"
        )
        encoder = "?"
        if stream_json.is_file():
            encoder = json.loads(stream_json.read_text(encoding="utf-8")).get(
                "encoder", "?"
            )
        print(
            f"  {cam.alias}: mkv={len(files['mkv'])} ({mkv_bytes} B) "
            f"timing={len(files['timing'])} ({timing_bytes} B) encoder={encoder}"
        )
        if not files["mkv"] or mkv_bytes < 10_000:
            print(f"    FAIL: missing/small MKV for {cam.alias}")
            ok = False
        if not files["timing"] or timing_bytes < 100:
            print(f"    FAIL: missing/small timing MCAP for {cam.alias}")
            ok = False

    integrity = package / "integrity.json"
    if integrity.is_file():
        data = json.loads(integrity.read_text(encoding="utf-8"))
        files = data.get("files", [])
        sealed = [e for e in files if isinstance(e, dict) and e.get("status") == "sealed"]
        cam_sealed = [
            e
            for e in sealed
            if any(e.get("sourceId") == cam.source_id for cam in cams)
            and str(e.get("path", "")).endswith((".mkv", ".timing.mcap"))
        ]
        print(f"integrity sealed camera artifacts: {len(cam_sealed)}")
        if len(cam_sealed) < len(cams) * 2:
            print("    FAIL: expected mkv+timing sealed per camera")
            ok = False
    else:
        print("FAIL: no integrity.json")
        ok = False

    client.close()
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
