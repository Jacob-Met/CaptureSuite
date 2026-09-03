# SPDX-License-Identifier: GPL-3.0-only
"""Smoke Fusion-style preview_view switching on a real TR13C."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / "capture_protocol"),
]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import preview_pb2  # noqa: E402
from capture_protocol.generated.capture.v1.common_pb2 import MessageType  # noqa: E402

VIEWS = [
    ("range_doppler", "matrix"),
    ("range_doppler_hd", "matrix"),
    ("range_spectrum", "trace"),
    ("range_spectrogram", "matrix"),
    ("time_domain", "trace"),
]


def main() -> int:
    client = ControlClient()
    client.connect()
    radars = [
        s
        for s in client.list_sources().sources
        if s.source_id.startswith("radar.") and "LTR11" not in (s.alias or "")
    ]
    if not radars:
        # fall back: any radar that isn't doppler modality
        radars = [
            s
            for s in client.list_sources().sources
            if s.source_id.startswith("radar.")
            and (s.streams[0].modality if s.streams else "") != "radar_doppler"
        ]
    if not radars:
        print("no FMCW radar.* source")
        return 2
    sid = radars[0].source_id
    print("target", radars[0].alias, sid)

    schema = client.get_config_schema(sid)
    print("schema_revision", schema.schema_revision)
    if schema.schema_revision != "radar.ifx/3":
        print("FAIL: expected radar.ifx/3")
        return 1

    try:
        client.stop_rehearsal()
    except Exception:
        pass

    sess = client.create_session(f"radar-views-{int(time.time())}")
    if sess.error.code:
        print("create_session", sess.error.code, sess.error.message)
        return 1
    client.subscribe_status(include_preview=True, health_interval_ms=1000)
    client.select_sources([sid])
    # Reset chirp geometry so view size expectations stay stable across runs.
    reset = client.apply_config(
        sid,
        {
            "num_chirps": 32,
            "num_samples": 128,
            "end_frequency_Hz": 61.5e9,
            "preview_view": "range_doppler",
        },
    )
    if reset.error.code:
        print("reset chirp", reset.error.code, reset.error.message)
        return 1
    reh = client.start_rehearsal([sid])
    if reh.error.code:
        print("rehearsal", reh.error.code, reh.error.message)
        return 1

    for view, expect in VIEWS:
        # Drain stale preview frames before switching.
        drain_deadline = time.time() + 0.4
        while time.time() < drain_deadline:
            client.poll_event(timeout_s=0.05)
        applied = client.apply_config(sid, {"preview_view": view})
        if applied.error.code:
            print("apply", view, applied.error.code, applied.error.message)
            return 1
        print(f"  applied {view} → {applied.effective_json}")
        saw = None
        detail = ""
        seen: list[str] = []
        deadline = time.time() + 5.0
        while time.time() < deadline:
            event = client.poll_event(timeout_s=0.3)
            if event is None:
                continue
            mt, payload = event
            if mt != int(MessageType.MESSAGE_TYPE_PREVIEW_FRAME):
                continue
            frame = preview_pb2.PreviewFrame()
            frame.ParseFromString(payload)
            if frame.source_id != sid:
                continue
            if frame.HasField("matrix"):
                seen.append(
                    f"matrix {frame.matrix.rows}x{frame.matrix.cols} "
                    f"{frame.matrix.row_axis}x{frame.matrix.col_axis}"
                )
            elif frame.HasField("trace"):
                seen.append(f"trace {list(frame.trace.channel_names)}")
            else:
                seen.append(f"other kind={frame.kind}")
            if expect == "matrix" and frame.HasField("matrix"):
                axes = f"{frame.matrix.row_axis}x{frame.matrix.col_axis}"
                if view.startswith("range_doppler") and axes != "rangexdoppler":
                    continue
                if view == "range_doppler_hd" and frame.matrix.rows != 128:
                    continue
                if view == "range_doppler" and frame.matrix.rows != 64:
                    continue
                if view == "range_spectrogram" and frame.matrix.row_axis != "time":
                    continue
                saw = "matrix"
                detail = f"{frame.matrix.rows}x{frame.matrix.cols} {axes}"
                break
            if expect == "trace" and frame.HasField("trace"):
                names = list(frame.trace.channel_names)
                if view == "range_spectrum" and names != ["range"]:
                    continue
                if view == "time_domain" and names != ["if"]:
                    continue
                saw = "trace"
                detail = f"pts={frame.trace.points_per_channel} ch={names}"
                break
        if saw != expect:
            print(f"FAIL: {view} expected {expect}, got {saw}")
            print(f"    frames seen: {seen[:12]}")
            return 1
        print(f"    got {saw} {detail}")

    client.stop_rehearsal()
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
