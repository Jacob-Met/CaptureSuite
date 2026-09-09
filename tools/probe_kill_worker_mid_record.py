# SPDX-License-Identifier: GPL-3.0-only
"""Kill one external worker mid-record; survivors + DISCONNECT gap must hold."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "libs" / "python" / "capture_protocol")]

from capture_protocol.control_client import (  # noqa: E402
    ControlClient,
    parse_health_snapshot,
)
from capture_protocol.generated.capture.v1 import (  # noqa: E402
    control_pb2,
    health_pb2,
)
from capture_protocol.generated.capture.v1.common_pb2 import MessageType  # noqa: E402


def _pick_sources(client: ControlClient, kill_family: str):
    sources = list(client.list_sources().sources)
    cams = [s for s in sources if s.source_type == "camera" and "brio" in (s.alias or "").lower()]
    if not cams:
        cams = [s for s in sources if s.source_type == "camera"][:1]
    radars = [s for s in sources if s.source_id.startswith("radar.")]
    if not cams or not radars:
        raise RuntimeError("need at least one camera and one radar")
    ids = [cams[0].source_id] + [s.source_id for s in radars]
    if kill_family == "camera":
        victim = cams[0].source_id
        exe = "capture_worker_camera.exe"
    else:
        victim = radars[0].source_id
        exe = "capture_worker_radar.exe"
    survivors = [sid for sid in ids if sid != victim]
    return ids, radars, victim, survivors, exe


def _pids_for_source(exe: str, source_id: str) -> list[int]:
    """Match worker PIDs whose command line carries the source_id / worker-id."""
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='" + exe + "'\" | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        check=False,
    )
    raw = (proc.stdout or "").strip()
    if not raw:
        return []
    import json

    data = json.loads(raw)
    rows = data if isinstance(data, list) else [data]
    hits: list[int] = []
    needle = source_id
    for row in rows:
        cmd = row.get("CommandLine") or ""
        if needle in cmd or needle.replace(".", "_") in cmd:
            hits.append(int(row["ProcessId"]))
    if not hits:
        # Fall back: single instance of that exe.
        for row in rows:
            hits.append(int(row["ProcessId"]))
    return hits


def _kill_pids(pids: list[int]) -> None:
    for pid in pids:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )


def _finalize(client: ControlClient) -> None:
    tok = client.request_stop()
    if tok.error.code:
        raise RuntimeError(f"request_stop {tok.error.code} {tok.error.message}")
    stop = client.stop_session(tok.confirmation_token)
    if stop.error.code:
        raise RuntimeError(f"stop_session {stop.error.code} {stop.error.message}")
    if stop.state != control_pb2.SESSION_STATE_FINALIZED:
        raise RuntimeError(f"expected FINALIZED, got {stop.state}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--kill",
        choices=("camera", "radar"),
        default="camera",
        help="which worker family to kill",
    )
    ap.add_argument("--warmup-s", type=float, default=4.0)
    ap.add_argument("--wait-s", type=float, default=8.0)
    args = ap.parse_args()

    # Camera+dual-radar arm can exceed the default 10s RPC timeout.
    client = ControlClient(timeout_s=60.0)
    client.connect()
    ids, radars, victim, survivors, exe = _pick_sources(client, args.kill)
    print(f"recording {ids}; kill {victim} ({exe})")

    try:
        client.stop_rehearsal()
    except Exception:
        pass

    sess = client.create_session(f"kill-{args.kill}-{int(time.time())}")
    if sess.error.code:
        print("create_session", sess.error.code, sess.error.message)
        return 1
    package = Path(sess.package_path)
    print("package", package)

    client.subscribe_status(include_preview=False, health_interval_ms=500)
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
    if start.error.code:
        print("start_selected", start.error.code, start.error.message)
        return 1
    if start.state != control_pb2.SESSION_STATE_RECORDING:
        print("expected RECORDING, got", start.state)
        return 1

    survivors_ok = True
    fault_ok = False
    reopen_survivors_ok = True
    reopen_victim_ok = True
    try:
        time.sleep(args.warmup_s)
        before = {s.source_id: s.sample_count for s in client.get_recording_stats().streams}
        print("before", before)

        pids = _pids_for_source(exe, victim)
        if not pids:
            print(f"FAIL: no {exe} PID for {victim}")
            return 1
        print("killing PIDs", pids)
        _kill_pids(pids)

        saw_worker_exit = False
        saw_disconnect_alert = False
        saw_gap_event = False
        deadline = time.time() + args.wait_s
        while time.time() < deadline:
            event = client.poll_event(timeout_s=0.3)
            if event is None:
                continue
            mt, payload = event
            if mt == int(MessageType.MESSAGE_TYPE_HEALTH_SNAPSHOT):
                snap = parse_health_snapshot(payload)
                if snap.source_id != victim:
                    continue
                code = ""
                if snap.HasField("last_error"):
                    code = snap.last_error.code or ""
                if code == "WORKER_EXITED" or "WORKER" in code.upper():
                    saw_worker_exit = True
                    print("health", snap.source_id, code, snap.last_error.message)
                if snap.gap_count > 0 or snap.HasField("open_gap"):
                    saw_gap_event = True
            elif mt == int(MessageType.MESSAGE_TYPE_ALERT):
                alert = health_pb2.Alert()
                alert.ParseFromString(payload)
                if alert.source_id == victim and (
                    "DISCONNECT" in (alert.code or "")
                    or "DISCONNECT" in (alert.message or "").upper()
                    or "WORKER" in (alert.code or "").upper()
                ):
                    saw_disconnect_alert = True
                    print("alert", alert.code, alert.message)
            elif mt == int(MessageType.MESSAGE_TYPE_GAP_EVENT):
                gap = health_pb2.GapEvent()
                gap.ParseFromString(payload)
                if gap.source_id == victim:
                    saw_gap_event = True
                    print("gap", gap.source_id, gap.cause)

        view = client.get_session_view()
        for a in view.alerts:
            if a.source_id == victim and (
                "DISCONNECT" in (a.code or "") or "WORKER" in (a.code or "").upper()
            ):
                saw_disconnect_alert = True
                print("view_alert", a.code, a.message)

        after = {s.source_id: s.sample_count for s in client.get_recording_stats().streams}
        print("after", after)
        victim_gaps = next(
            (s.gap_count for s in client.get_recording_stats().streams if s.source_id == victim),
            0,
        )
        print(
            f"signals worker_exit={saw_worker_exit} alert={saw_disconnect_alert} "
            f"gap_event={saw_gap_event} gap_count={victim_gaps}"
        )

        for sid in survivors:
            if after.get(sid, 0) <= before.get(sid, 0):
                print("FAIL: survivor stalled", sid)
                survivors_ok = False

        fault_ok = victim_gaps >= 1 or saw_gap_event or saw_worker_exit or saw_disconnect_alert
        if not fault_ok:
            print("FAIL: no fault signal for victim after kill")
    finally:
        try:
            _finalize(client)
        except Exception as exc:
            print("WARN: finalize", exc)
            reopen_survivors_ok = False

    # Reopen: survivors must come back; victim failure is a USB/handle BLOCKER.
    # Rescan clears dead worker slots / rediscovers boards after a mid-session kill.
    try:
        client.stop_rehearsal()
    except Exception:
        pass
    try:
        resc = client.rescan_sources()
        if resc.error.code:
            print("WARN: rescan before reopen", resc.error.code, resc.error.message)
        else:
            print("rescanned sources before reopen")
    except Exception as exc:
        print("WARN: rescan before reopen", exc)
    time.sleep(1.0)
    sess2 = client.create_session(f"reopen-after-kill-{args.kill}-{int(time.time())}")
    if sess2.error.code:
        print("FAIL: reopen create_session", sess2.error.code, sess2.error.message)
        reopen_survivors_ok = False
        reopen_victim_ok = False
    else:
        try:
            client.select_sources(ids)
            start2 = client.start_selected()
            if start2.error.code or start2.state != control_pb2.SESSION_STATE_RECORDING:
                print(
                    "FAIL: reopen start",
                    start2.error.code,
                    start2.error.message,
                    start2.state,
                )
                reopen_survivors_ok = False
                reopen_victim_ok = False
            else:
                time.sleep(4.0)
                stats2 = client.get_recording_stats()
                live = {s.source_id: s.sample_count for s in stats2.streams}
                print("reopen samples", live)
                for sid in survivors:
                    if live.get(sid, 0) <= 0:
                        print("FAIL: survivor reopen sample_count stayed 0", sid)
                        reopen_survivors_ok = False
                if live.get(victim, 0) <= 0:
                    print(
                        "BLOCKER: victim did not reopen after kill (sticky USB/handle?) —",
                        victim,
                    )
                    reopen_victim_ok = False
        finally:
            try:
                _finalize(client)
            except Exception as exc:
                print("WARN: reopen finalize", exc)
                reopen_survivors_ok = False

    if not survivors_ok or not fault_ok or not reopen_survivors_ok:
        print("FAIL", package)
        return 1
    if not reopen_victim_ok:
        print("PASS_WITH_BLOCKER", package)
        return 0
    print("PASS", package)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
