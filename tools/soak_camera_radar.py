# SPDX-License-Identifier: GPL-3.0-only
"""Record camera + both radars, stop, verify sealed package provenance."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "libs" / "python" / "capture_protocol")]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import control_pb2  # noqa: E402


def _stop_recording(client: ControlClient) -> bool:
    """Finalize or report refusal; never hide an exception from the capture loop."""
    tok = client.request_stop()
    if tok.error.code:
        print("request_stop", tok.error.code, tok.error.message)
        return False
    stop = client.stop_session(tok.confirmation_token)
    if stop.error.code:
        print("stop_session", stop.error.code, stop.error.message)
        return False
    if stop.state != control_pb2.SESSION_STATE_FINALIZED:
        print("expected FINALIZED, got", stop.state)
        return False
    return True


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    client = ControlClient(timeout_s=60.0)
    client.connect()
    sources = list(client.list_sources().sources)
    cams = [s for s in sources if s.source_type == "camera" and "brio" in (s.alias or "").lower()]
    if not cams:
        cams = [s for s in sources if s.source_type == "camera"][:1]
    radars = [s for s in sources if s.source_id.startswith("radar.")]
    if not cams or not radars:
        print("need at least one camera and one radar")
        return 2
    ids = [cams[0].source_id] + [s.source_id for s in radars]
    print("recording", ids, f"for {seconds:.0f}s")

    try:
        client.stop_rehearsal()
    except Exception:
        pass
    sess = client.create_session(f"soak-cam-radar-{int(time.time())}")
    if sess.error.code:
        print("create_session", sess.error.code, sess.error.message)
        return 1
    package = Path(sess.package_path)
    print("package", package)

    client.select_sources(ids)
    for s in radars:
        mod = s.streams[0].modality if s.streams else ""
        if mod != "radar_doppler":
            applied = client.apply_config(
                s.source_id,
                {
                    "num_chirps": 64,
                    "num_samples": 256,
                    "end_frequency_Hz": 63e9,
                },
            )
            if applied.error.code:
                print("apply", s.source_id, applied.error.code, applied.error.message)

    start = client.start_selected()
    if start.error.code:
        print("start_selected", start.error.code, start.error.message)
        return 1
    if start.state != control_pb2.SESSION_STATE_RECORDING:
        print("expected RECORDING, got", start.state)
        return 1

    saw_live = {sid: False for sid in ids}
    missing: list[str] = []
    try:
        if not (package / "arrays.json").is_file():
            print("FAIL: arrays.json missing at record start")
            return 1
        t0 = time.time()
        while time.time() - t0 < seconds:
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
    finally:
        stop_ok = _stop_recording(client)

    if not stop_ok:
        return 1

    if missing:
        print("FAIL: live sample_count stayed 0 for", missing)
        return 1

    integrity = package / "integrity.json"
    manifest = package / "manifest.json"
    if not integrity.is_file() or not manifest.is_file():
        print("FAIL: missing integrity/manifest after finalize")
        return 1
    integ = json.loads(integrity.read_text(encoding="utf-8"))
    entries = integ.get("files") or integ.get("file_entries") or integ.get("entries") or []
    hashed = 0
    if isinstance(entries, list):
        for ent in entries:
            if not isinstance(ent, dict):
                continue
            digest = (
                ent.get("hashBlake3Hex")
                or ent.get("hash_blake3_hex")
                or ent.get("blake3")
                or ent.get("hash")
            )
            if digest:
                hashed += 1
    stream_jsons = list(package.rglob("stream.json"))
    print(f"hashed_files={hashed} stream.json={len(stream_jsons)}")
    if hashed < len(ids):
        print("FAIL: expected >=", len(ids), "hashed integrity entries")
        return 1
    # Camera may not write stream.json; radars must.
    radar_streams = [p for p in stream_jsons if "radar." in str(p)]
    if len(radar_streams) < len(radars):
        print("FAIL: missing radar stream.json snapshots")
        return 1

    print("PASS", package)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
