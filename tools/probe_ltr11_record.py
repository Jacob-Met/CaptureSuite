# SPDX-License-Identifier: GPL-3.0-only
"""Short LTR11 Doppler record smoke: Start → MCAP RadarDopplerFrame → Stop."""

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
from capture_protocol.generated.capture.v1 import control_pb2  # noqa: E402
from capture_protocol.generated.capture.v1.data import radar_doppler_pb2  # noqa: E402

RECORD_S = 5.0


def _is_ltr11_source(source) -> bool:
    alias = (source.alias or "").upper()
    if "LTR11" in alias or "LTR-11" in alias:
        return True
    for key in ("modality", "record_stack", "sensor_type"):
        val = source.metadata.get(key, "").lower()
        if "ltr11" in val or "doppler" in val:
            return True
    for stream in source.streams:
        if stream.modality == "radar_doppler":
            return True
        if stream.data_schema_id == "radar.doppler/1":
            return True
    return False


def main() -> int:
    try:
        from mcap.reader import make_reader
    except ImportError:
        print(
            "mcap package missing — install with:\n"
            r'  & "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m pip install mcap',
            file=sys.stderr,
        )
        return 2

    client = ControlClient()
    client.connect()
    sources = client.list_sources().sources
    ltr11 = [s for s in sources if s.source_id.startswith("radar.") and _is_ltr11_source(s)]
    if not ltr11:
        print("no LTR11 radar source (look for radar_doppler / LTR11 in alias)")
        for s in sources:
            if s.source_id.startswith("radar."):
                print(f"  saw {s.source_id} alias={s.alias!r} meta={dict(s.metadata)}")
        return 2
    sid = ltr11[0].source_id
    stream_id = sid + ".frame"
    print(f"recording {ltr11[0].alias} ({sid}) for {RECORD_S:.0f}s")

    sess = client.create_session(f"ltr11-rec-{int(time.time())}")
    if sess.error.code:
        print("create_session:", sess.error.code, sess.error.message)
        return 1
    package = Path(sess.package_path)
    print("package:", package)

    sel = client.select_sources([sid])
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

    t0 = time.time()
    while time.time() - t0 < RECORD_S:
        stats = client.get_recording_stats()
        for stream in stats.streams:
            if stream.source_id == sid:
                print(f"  samples={stream.sample_count}")
        time.sleep(1.0)

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
    print("finalized")

    seg_dir = package / "sources" / sid / "streams" / stream_id / "segments"
    mcaps = sorted(seg_dir.glob("*.mcap")) if seg_dir.is_dir() else []
    print(f"segments: {len(mcaps)} under {seg_dir}")
    if not mcaps:
        client.close()
        return 3

    count = 0
    encoding = ""
    payload0 = 0
    num_samples = 0
    with mcaps[0].open("rb") as f:
        reader = make_reader(f)
        for _schema, _channel, message in reader.iter_messages():
            frame = radar_doppler_pb2.RadarDopplerFrame()
            frame.ParseFromString(message.data)
            count += 1
            if count == 1:
                encoding = frame.sample_encoding
                payload0 = len(frame.payload)
                num_samples = frame.num_samples

    expected = num_samples * 2 * 4  # complex float32 I,Q
    ok = (
        count >= int(RECORD_S * 5)
        and encoding == "complex_float32_le"
        and payload0 == expected
        and expected > 0
    )
    print(
        f"messages={count} encoding={encoding} "
        f"num_samples={num_samples} payload={payload0} (expect {expected})"
    )
    print("PASS" if ok else "FAIL")
    client.close()
    return 0 if ok else 4


if __name__ == "__main__":
    raise SystemExit(main())
