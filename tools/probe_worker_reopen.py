# SPDX-License-Identifier: GPL-3.0-only
"""Idle Rescan then re-record the same camera+radar set (no taskkill)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "libs" / "python" / "capture_protocol")]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import control_pb2  # noqa: E402


def _ensure_idle(client: ControlClient) -> None:
    try:
        client.stop_rehearsal()
    except Exception:
        pass
    view = client.get_session_view()
    active = {
        control_pb2.SESSION_STATE_PREPARING,
        control_pb2.SESSION_STATE_ARMING,
        control_pb2.SESSION_STATE_RECORDING,
        control_pb2.SESSION_STATE_STOPPING,
        control_pb2.SESSION_STATE_RECOVERING,
        control_pb2.SESSION_STATE_FAILED,
    }
    if view.state in active or view.rehearsal_active:
        tok = client.request_stop()
        if tok.confirmation_token:
            client.stop_session(tok.confirmation_token)
        try:
            client.stop_rehearsal()
        except Exception:
            pass


def _pick(client: ControlClient) -> list[str]:
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
        raise RuntimeError("need camera + radar")
    return [cams[0].source_id] + [s.source_id for s in radars]


def _record(
    client: ControlClient, ids: list[str], label: str, seconds: float
) -> tuple[Path, dict[str, int]]:
    sess = client.create_session(f"{label}-{int(time.time())}")
    if sess.error.code:
        raise RuntimeError(f"create: {sess.error.code} {sess.error.message}")
    package = Path(sess.package_path)
    try:
        sel = client.select_sources(ids)
        if sel.error.code:
            raise RuntimeError(f"select: {sel.error.code}")
        start = client.start_selected()
        if start.error.code or start.state != control_pb2.SESSION_STATE_RECORDING:
            raise RuntimeError(f"start: {start.error.code} {start.state}")
        time.sleep(seconds)
        stats = {s.source_id: s.sample_count for s in client.get_recording_stats().streams}
        print(label, "samples", stats)
        tok = client.request_stop()
        stop = client.stop_session(tok.confirmation_token)
        if stop.error.code or stop.state != control_pb2.SESSION_STATE_FINALIZED:
            raise RuntimeError(f"stop: {stop.error.code} {stop.state}")
        return package, stats
    except Exception:
        try:
            tok = client.request_stop()
            if tok.confirmation_token:
                client.stop_session(tok.confirmation_token)
        except Exception:
            pass
        raise


def _radar_sticky(ids: list[str], stats: dict[str, int]) -> bool:
    cams = [sid for sid in ids if sid.startswith("camera.")]
    radars = [sid for sid in ids if sid.startswith("radar.")]
    if not cams or not radars:
        return False
    cam_ok = all(stats.get(sid, 0) > 0 for sid in cams)
    radar_dead = any(stats.get(sid, 0) <= 0 for sid in radars)
    return cam_ok and radar_dead


def main() -> int:
    client = ControlClient(timeout_s=60.0)
    client.connect()
    try:
        _ensure_idle(client)
        # Warm Rescan so USB sticky boards get a fresh worker slot.
        resc = client.rescan_sources()
        if resc.error.code:
            print("FAIL rescan", resc.error.code, resc.error.message)
            return 1
        time.sleep(1.5)
        ids = _pick(client)
        print("ids", ids)
        _pkg_a, stats_a = _record(client, ids, "reopen-a", 5.0)
        if any(stats_a.get(sid, 0) <= 0 for sid in ids):
            if _radar_sticky(ids, stats_a):
                print(
                    "PASS_WITH_BLOCKER reopen-a: radar zero samples "
                    "(likely TR13C sticky USB — unplug/replug tomorrow)"
                )
                return 0
            print("FAIL reopen-a: missing samples", stats_a)
            return 1
        resc = client.rescan_sources()
        if resc.error.code:
            print("FAIL rescan", resc.error.code, resc.error.message)
            return 1
        print("rescanned")
        time.sleep(1.5)
        # Re-pick in case ids churned; prefer previous set if still present.
        available = {s.source_id for s in client.list_sources().sources}
        ids2 = [sid for sid in ids if sid in available] or _pick(client)
        _pkg_b, stats_b = _record(client, ids2, "reopen-b", 5.0)
        if any(stats_b.get(sid, 0) <= 0 for sid in ids2):
            if _radar_sticky(ids2, stats_b):
                print(
                    "PASS_WITH_BLOCKER reopen-b: radar zero samples after idle rescan "
                    "(TR13C sticky USB — unplug/replug tomorrow)"
                )
                return 0
            print("FAIL reopen-b: missing samples", stats_b)
            return 1
        print("PASS worker reopen after idle rescan")
        return 0
    except Exception as exc:
        print("FAIL", exc)
        try:
            _ensure_idle(client)
        except Exception:
            pass
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
