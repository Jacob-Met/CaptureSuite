# SPDX-License-Identifier: GPL-3.0-only
"""Assert FMCW range-Doppler preview shows non-trivial energy (fan liveliness)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "libs" / "python" / "capture_protocol")]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import preview_pb2  # noqa: E402
from capture_protocol.generated.capture.v1.common_pb2 import MessageType  # noqa: E402


def _matrix_stats(values: list[float]) -> tuple[float, float, float]:
    """Return (mean, vmax, variance) for preview matrix float values."""
    if not values:
        return 0.0, 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    vmax = float(max(values))
    var = sum((float(v) - mean) ** 2 for v in values) / n
    return float(mean), vmax, float(var)


def main() -> int:
    client = ControlClient()
    client.connect()
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

    try:
        client.stop_rehearsal()
    except Exception:
        pass
    sess = client.create_session(f"doppler-live-{int(time.time())}")
    if sess.error.code:
        print("create_session", sess.error.code, sess.error.message)
        return 1
    client.subscribe_status(include_preview=True, health_interval_ms=1000)
    client.select_sources([sid])
    reh = client.start_rehearsal([sid])
    if reh.error.code:
        print("rehearsal", reh.error.code, reh.error.message)
        return 1

    applied = client.apply_config(sid, {"preview_view": "range_doppler"})
    if applied.error.code:
        print("apply", applied.error.code, applied.error.message)
        return 1

    best_var = 0.0
    best_max = 0.0
    frames = 0
    deadline = time.time() + 10.0
    while time.time() < deadline:
        event = client.poll_event(timeout_s=0.3)
        if event is None:
            continue
        mt, payload = event
        if mt != int(MessageType.MESSAGE_TYPE_PREVIEW_FRAME):
            continue
        frame = preview_pb2.PreviewFrame()
        frame.ParseFromString(payload)
        if frame.source_id != sid or not frame.HasField("matrix"):
            continue
        m = frame.matrix
        if m.row_axis != "range" or m.col_axis != "doppler":
            continue
        mean, vmax, var = _matrix_stats(list(m.values))
        frames += 1
        best_var = max(best_var, var)
        best_max = max(best_max, vmax)
        print(
            f"  frame {frames}: {m.rows}x{m.cols} mean={mean:.4g} "
            f"max={vmax:.4g} var={var:.4g}"
        )
        if frames >= 5 and (best_var > 1e-6 or best_max > 0):
            break

    try:
        client.stop_rehearsal()
    except Exception:
        pass

    if frames < 3:
        print("FAIL: too few range_doppler frames", frames)
        return 1
    # Fan / clutter: any non-zero peak or variance counts as liveliness.
    if best_max <= 0 and best_var <= 0:
        print("FAIL: matrix energy dead-flat (is the fan in FOV?)")
        return 1
    print(f"PASS frames={frames} best_max={best_max:.4g} best_var={best_var:.4g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
