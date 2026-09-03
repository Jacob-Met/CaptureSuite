# SPDX-License-Identifier: GPL-3.0-only
"""Verify device-reported capture modes end to end against a real camera.

Applies each requested mode, records briefly, and reports the caps the pipeline
actually negotiated plus the frame rate the device delivered. Achieved rate can
sit below the requested rate when the camera lowers its own frame rate for
exposure; that is a device decision, not a pipeline fault.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / "capture_protocol"),
    str(ROOT / "libs" / "python" / "capture_session"),
]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import health_pb2  # noqa: E402
from capture_protocol.generated.capture.v1.common_pb2 import MessageType  # noqa: E402

CAPS_RE = re.compile(
    r"format=\(string\)(\w+), width=\(int\)(\d+), height=\(int\)(\d+), "
    r"framerate=\(fraction\)([\d/]+)"
)


def negotiated_caps(package: Path) -> str:
    caps = ""
    for stream_json in package.rglob("stream.json"):
        doc = json.loads(stream_json.read_text(encoding="utf-8"))
        caps = doc.get("negotiated_caps") or caps
    return caps


def run_mode(client: ControlClient, source_id: str, key: str, seconds: float) -> bool:
    session = client.create_session("modeprobe-" + key.replace(":", "-").replace("/", "-"))
    package = Path(session.package_path)
    client.apply_config(
        source_id,
        {"capture_mode": key, "preview_enabled": True, "preview_max_rate_hz": 5},
    )
    client.select_sources([source_id])
    client.subscribe_status(include_preview=False, health_interval_ms=500)
    started = client.start_selected()
    if started.error.code:
        print(f"{key:24s} START FAILED {started.error.code} {started.error.message}")
        return False

    # The device is free to deliver below the requested rate (long exposure in
    # dim light), so report what it actually produced alongside the caps.
    rates: list[float] = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        event = client.poll_event(timeout_s=0.4)
        if event is None:
            continue
        message_type, payload = event
        if message_type != int(MessageType.MESSAGE_TYPE_HEALTH_SNAPSHOT):
            continue
        snapshot = health_pb2.HealthSnapshot()
        snapshot.ParseFromString(payload)
        if snapshot.source_id == source_id and snapshot.measured_rate_hz > 0:
            rates.append(snapshot.measured_rate_hz)

    stop_started = time.time()
    token = client.request_stop().confirmation_token
    client.stop_session(token)
    stop_seconds = time.time() - stop_started

    caps = negotiated_caps(package)
    match = CAPS_RE.search(caps)
    megabytes = sum(m.stat().st_size for m in package.rglob("*.mkv")) / 1e6
    measured = f"{statistics.median(rates):5.1f}" if rates else "    ?"

    want_w, want_rest = key.split("x", 1)
    want_h = want_rest.split("@", 1)[0]
    ok = bool(match) and match.group(2) == want_w and match.group(3) == want_h
    shape = "/".join(match.groups()) if match else caps[:60]
    print(
        f"{key:24s} {'ok ' if ok else 'BAD'} stop={stop_seconds:4.1f}s "
        f"{megabytes:6.1f}MB measured_hz={measured} {shape}"
    )
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alias", default="Brio", help="substring of the camera alias")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument(
        "--modes",
        nargs="*",
        help="capture_mode keys; defaults to the highest rate of each named resolution",
    )
    parser.add_argument("--list", action="store_true", help="print modes and exit")
    args = parser.parse_args()

    client = ControlClient(timeout_s=180.0)
    client.connect()
    try:
        source = next(
            s for s in client.list_sources().sources if args.alias.lower() in s.alias.lower()
        )
        schema = json.loads(client.get_config_schema(source.source_id).schema_json)
        prop = schema["properties"].get("capture_mode")
        if prop is None:
            print("device reports no capture modes")
            return 1
        enum = prop["enum"]
        labels = prop.get("x-capture-enum-labels", {})

        if args.list:
            print(f"{source.alias}: {len(enum)} modes, default {prop['default']}")
            for key in enum:
                print(f"  {key:26s} {labels.get(key, '')}")
            return 0

        modes = args.modes
        if not modes:
            modes = []
            for prefix in ("3840x2160", "2560x1440", "1920x1080", "1280x720"):
                modes.extend(k for k in enum if k.startswith(prefix + "@"))
                modes = modes[: len(modes)]
            seen_res = set()
            fastest = []
            for key in modes:
                res = key.split("@", 1)[0]
                if res not in seen_res:
                    seen_res.add(res)
                    fastest.append(key)
            modes = fastest

        failures = 0
        for key in modes:
            if key not in enum:
                print(f"{key:24s} NOT OFFERED by device")
                failures += 1
                continue
            if not run_mode(client, source.source_id, key, args.seconds):
                failures += 1
        return 1 if failures else 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
